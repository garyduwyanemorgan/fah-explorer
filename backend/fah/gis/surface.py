"""Risk surfaces (docs/13, principle 1 & 3).

Pipeline: interpolate continuous DRIVERS within the data hull → for every grid cell run the risk
engine on the interpolated drivers (categorical/geometry signals taken from the nearest borehole)
→ per-category score grids + a variance-based confidence grid. We never interpolate risk scores.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import numpy as np
from scipy.spatial import cKDTree
from sqlalchemy import select
from sqlalchemy.orm import Session

from fah.config import get_settings
from fah.db.models import Borehole, Project
from fah.gis import interpolate
from fah.gis.domains import MIN_BOREHOLES_FOR_SURFACE, build_grid
from fah.gis.geometry import metres_bbox_to_lonlat, working_xy
from fah.risk.context import RiskContext
from fah.risk.engine import assess_borehole, engine_version
from fah.risk.rules import get_risk_rules

logger = logging.getLogger("fah.gis.surface")

# Continuous drivers interpolated as fields. Names match RiskContext.numeric_var / lab keys.
_NUMERIC_DRIVERS = (
    "gwl_depth_m",
    "ground_level_m",
    "max_anisotropy",
    "cemented_or_lowkv_above_m",
    "surface_k_v",
)
_LAB_DRIVERS = ("chloride", "sulphate", "tds")


@dataclass
class SurfaceSet:
    bounds: tuple[float, float, float, float]   # south, west, north, east (WGS84)
    nx: int
    ny: int
    score_grids: dict[str, np.ndarray]          # category -> (ny, nx) float, NaN outside hull
    confidence_grid: np.ndarray
    method: str
    n_boreholes: int
    drivers_available: list[str] = field(default_factory=list)
    engine_version: str = ""
    # PNG bytes cached on first render; cleared by invalidate().
    _png_cache: dict[str, bytes] = field(default_factory=dict, repr=False)
    _conf_png: bytes | None = field(default=None, repr=False)


class CellContext:
    """Duck-typed RiskContext for one grid cell (interpolated numerics + nearest categoricals)."""

    def __init__(self, drivers: dict[str, float | None], labs: dict[str, float | None],
                 nearest: RiskContext, site: dict[str, Any]):
        self.gwl_depth_m = drivers.get("gwl_depth_m")
        self.ground_level_m = drivers.get("ground_level_m")
        self.max_anisotropy = drivers.get("max_anisotropy")
        self.cemented_or_lowkv_above_m = drivers.get("cemented_or_lowkv_above_m")
        self.surface_k_v = drivers.get("surface_k_v")
        self._labs = labs
        self._n = nearest
        self.site = site

    def numeric_var(self, name: str) -> float | None:
        return getattr(self, name)

    def has_lithology(self, code: str) -> bool:
        return self._n.has_lithology(code)

    def has_unit_type(self, unit_type: str) -> bool:
        return self._n.has_unit_type(unit_type)

    def lab(self, parameter: str) -> float | None:
        return self._labs.get(parameter.lower())

    @property
    def has_subsurface_model(self) -> bool:
        return self._n.has_subsurface_model

    @property
    def lowkv_unit_below_highk(self) -> bool:
        return self._n.lowkv_unit_below_highk

    @property
    def highk_over_lowkv(self) -> bool:
        return self._n.highk_over_lowkv

    @property
    def salinity_source(self) -> bool:
        if self._n.has_lithology("sabkha"):
            return True
        tds, cl = self.lab("tds"), self.lab("chloride")
        return (tds is not None and tds > 35000) or (cl is not None and cl > 5000)


def _sample(value_fn, contexts, xs, ys):
    """Collect (x, y, value) for boreholes where the driver value is present."""
    sx, sy, sv = [], [], []
    for ctx, x, y in zip(contexts, xs, ys):
        v = value_fn(ctx)
        if v is not None:
            sx.append(x); sy.append(y); sv.append(v)
    return np.array(sx), np.array(sy), np.array(sv)


def build_surfaces(
    db: Session, project_id: int, site: dict[str, Any] | None = None
) -> SurfaceSet | None:
    """Build risk surfaces for a project, or None if there is insufficient spatial data."""
    project = db.get(Project, project_id)
    if project is None:
        raise ValueError(f"Project {project_id} not found")
    crs_input = project.crs_input or get_settings().crs_input_default
    site = site or {}

    boreholes = list(db.scalars(select(Borehole).where(Borehole.project_id == project_id)))
    _xs: list[float] = []
    _ys: list[float] = []
    contexts: list[RiskContext] = []
    for bh in boreholes:
        xy = working_xy(bh.easting, bh.northing, bh.lon, bh.lat, crs_input)
        if xy is None:
            continue
        _xs.append(xy[0]); _ys.append(xy[1])
        contexts.append(RiskContext.from_borehole(bh, site))

    if len(contexts) < MIN_BOREHOLES_FOR_SURFACE:
        logger.info("Project %d has %d located boreholes (< %d) — no surface.",
                    project_id, len(contexts), MIN_BOREHOLES_FOR_SURFACE)
        return None

    xs: np.ndarray = np.array(_xs)
    ys: np.ndarray = np.array(_ys)
    grid = build_grid(xs, ys, resolution_m=10.0)
    if grid is None:
        return None

    # Interpolate each driver field.
    fields: dict[str, interpolate.InterpolatedField] = {}
    for name in _NUMERIC_DRIVERS:
        sx, sy, sv = _sample(lambda c, n=name: getattr(c, n) if n in ("gwl_depth_m", "ground_level_m")
                             else _ctx_numeric(c, n), contexts, xs, ys)
        if len(sv) >= 2:
            f = interpolate.interpolate_driver(sx, sy, sv, grid)
            if f:
                fields[name] = f
    lab_fields: dict[str, interpolate.InterpolatedField] = {}
    for param in _LAB_DRIVERS:
        sx, sy, sv = _sample(lambda c, p=param: c.lab(p), contexts, xs, ys)
        if len(sv) >= 2:
            f = interpolate.interpolate_driver(sx, sy, sv, grid)
            if f:
                lab_fields[param] = f

    # Confidence surface: from gwl kriging variance, else distance-decay.
    gwl = fields.get("gwl_depth_m")
    if gwl is not None and gwl.variance is not None:
        confidence = interpolate.variance_confidence(gwl, grid)
        method = gwl.method
    else:
        confidence = interpolate.distance_confidence(xs, ys, grid)
        method = gwl.method if gwl else "idw"

    # Run the risk engine per inside cell.
    rules = get_risk_rules()
    ny, nx = grid.inside.shape
    score_grids = {c.key: np.full((ny, nx), np.nan) for c in rules.categories}
    tree = cKDTree(np.column_stack([xs, ys]))

    iy_idx, ix_idx = np.where(grid.inside)
    for iy, ix in zip(iy_idx, ix_idx):
        cell_x, cell_y = grid.gx[ix], grid.gy[iy]
        drivers = {n: _grid_val(fields.get(n), iy, ix) for n in _NUMERIC_DRIVERS}
        labs = {p: _grid_val(lab_fields.get(p), iy, ix) for p in _LAB_DRIVERS}
        nearest = contexts[int(tree.query([cell_x, cell_y])[1])]
        cell = CellContext(drivers, labs, nearest, site)
        for cr in assess_borehole(cell, rules):  # type: ignore[arg-type]
            score_grids[cr.category][iy, ix] = cr.score

    south, west, north, east = metres_bbox_to_lonlat(
        grid.xmin, grid.ymin, grid.xmax, grid.ymax, crs_input
    )
    logger.info("Built surfaces for project %d (%dx%d, method=%s)", project_id, nx, ny, method)
    return SurfaceSet(
        bounds=(south, west, north, east),
        nx=nx, ny=ny,
        score_grids=score_grids,
        confidence_grid=confidence,
        method=method,
        n_boreholes=len(contexts),
        drivers_available=sorted([*fields, *(f"lab:{p}" for p in lab_fields)]),
        engine_version=engine_version(rules),
    )


# Simple per-process cache so the map can fetch metadata + PNG without rebuilding each time.
_SURFACE_CACHE: dict[int, "SurfaceSet | None"] = {}


def get_or_build(
    db: Session, project_id: int, site: dict[str, Any] | None = None, refresh: bool = False
) -> SurfaceSet | None:
    if refresh or project_id not in _SURFACE_CACHE:
        _SURFACE_CACHE[project_id] = build_surfaces(db, project_id, site)
    return _SURFACE_CACHE[project_id]


def invalidate(project_id: int) -> None:
    _SURFACE_CACHE.pop(project_id, None)


def _ctx_numeric(ctx: RiskContext, name: str) -> float | None:
    try:
        return ctx.numeric_var(name)
    except KeyError:
        return None


def _grid_val(field: interpolate.InterpolatedField | None, iy: int, ix: int) -> float | None:
    if field is None:
        return None
    v = field.values[iy, ix]
    return None if np.isnan(v) else float(v)

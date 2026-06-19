"""Render mask + grid construction (docs/13, principle 2b — no extrapolation beyond evidence).

For the MVP the render mask is the **data-support hull**: the convex hull of the boreholes,
buffered, optionally clipped to a site boundary. Everything outside is "insufficient data" and is
left transparent — never coloured low. Hydrostratigraphic *domain decomposition* (principle 2a) is
supported by accepting optional barrier/domain polygons; absent those, a single domain is used.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np
from matplotlib.path import Path as MplPath
from shapely.geometry import MultiPoint, Polygon

logger = logging.getLogger("fah.gis.domains")

# Below this many boreholes we do not draw a surface (docs/13 tiered method table).
MIN_BOREHOLES_FOR_SURFACE = 6


@dataclass
class Grid:
    gx: np.ndarray          # 1D grid x coordinates (metres)
    gy: np.ndarray          # 1D grid y coordinates (metres)
    inside: np.ndarray      # (ny, nx) bool mask — True where inside the render hull
    xmin: float
    ymin: float
    xmax: float
    ymax: float

    @property
    def shape(self) -> tuple[int, int]:
        return self.inside.shape


def data_hull(xs: np.ndarray, ys: np.ndarray, buffer_frac: float = 0.05) -> Polygon | None:
    """Convex hull of the boreholes, buffered by a fraction of the bbox diagonal."""
    pts = MultiPoint(list(zip(xs, ys)))
    hull = pts.convex_hull
    if not isinstance(hull, Polygon) or hull.area == 0:
        return None  # collinear/degenerate (too few or aligned points)
    diag = float(np.hypot(xs.max() - xs.min(), ys.max() - ys.min()))
    return hull.buffer(diag * buffer_frac)


def build_grid(
    xs: np.ndarray, ys: np.ndarray, resolution_m: float = 10.0, max_cells: int = 160
) -> Grid | None:
    """Build a regular grid over the buffered data hull and its inside-mask."""
    hull = data_hull(xs, ys)
    if hull is None:
        return None

    xmin, ymin, xmax, ymax = hull.bounds
    span_x, span_y = xmax - xmin, ymax - ymin
    nx = int(np.clip(round(span_x / resolution_m), 20, max_cells))
    ny = int(np.clip(round(span_y / resolution_m), 20, max_cells))

    gx = np.linspace(xmin, xmax, nx)
    gy = np.linspace(ymin, ymax, ny)
    mesh_x, mesh_y = np.meshgrid(gx, gy)

    exterior = np.asarray(hull.exterior.coords)
    inside = MplPath(exterior).contains_points(
        np.column_stack([mesh_x.ravel(), mesh_y.ravel()])
    ).reshape(mesh_x.shape)

    logger.info("Built %dx%d grid; %d cells inside hull", nx, ny, int(inside.sum()))
    return Grid(gx=gx, gy=gy, inside=inside, xmin=xmin, ymin=ymin, xmax=xmax, ymax=ymax)

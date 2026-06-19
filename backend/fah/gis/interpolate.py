"""Driver interpolation (docs/13, principle 1 & 4).

Interpolates a single continuous driver onto the grid, tiered by sample count:
kriging (with variance) when there are enough samples, else inverse-distance weighting.
We interpolate *drivers*, never risk scores. Anisotropy support is left to the kriging variogram
(future); the MVP uses isotropic models with honest masking + variance-based confidence.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np

from fah.gis.domains import Grid

logger = logging.getLogger("fah.gis.interpolate")

KRIGING_MIN_SAMPLES = 15


@dataclass
class InterpolatedField:
    values: np.ndarray            # (ny, nx), NaN outside hull
    variance: np.ndarray | None   # (ny, nx) kriging variance, or None for IDW
    method: str
    n_samples: int


def _idw(xs, ys, vals, grid: Grid, power: float = 2.0) -> np.ndarray:
    mesh_x, mesh_y = np.meshgrid(grid.gx, grid.gy)
    out = np.full(mesh_x.shape, np.nan)
    flat = grid.inside.ravel()
    gxp = mesh_x.ravel()[flat]
    gyp = mesh_y.ravel()[flat]

    dx = gxp[:, None] - xs[None, :]
    dy = gyp[:, None] - ys[None, :]
    dist = np.hypot(dx, dy)
    dist = np.where(dist < 1e-9, 1e-9, dist)
    w = 1.0 / dist**power
    est = (w * vals[None, :]).sum(axis=1) / w.sum(axis=1)

    res = out.ravel()
    res[flat] = est
    return res.reshape(mesh_x.shape)


def _kriging(xs, ys, vals, grid: Grid) -> tuple[np.ndarray, np.ndarray]:
    from pykrige.ok import OrdinaryKriging

    ok = OrdinaryKriging(
        xs, ys, vals, variogram_model="spherical", enable_plotting=False, verbose=False
    )
    z, ss = ok.execute("grid", grid.gx, grid.gy)  # both (ny, nx)
    z = np.asarray(z, dtype=float)
    ss = np.asarray(ss, dtype=float)
    z[~grid.inside] = np.nan
    ss[~grid.inside] = np.nan
    return z, ss


def interpolate_driver(
    xs: np.ndarray, ys: np.ndarray, vals: np.ndarray, grid: Grid
) -> InterpolatedField | None:
    """Interpolate one driver. Returns None if there are too few samples to interpolate."""
    n = len(vals)
    if n < 2:
        return None
    if n >= KRIGING_MIN_SAMPLES:
        try:
            z, ss = _kriging(xs, ys, vals, grid)
            return InterpolatedField(values=z, variance=ss, method="kriging", n_samples=n)
        except Exception as exc:  # pragma: no cover - variogram fit can fail
            logger.warning("Kriging failed (%s); falling back to IDW.", exc)
    return InterpolatedField(values=_idw(xs, ys, vals, grid), variance=None, method="idw", n_samples=n)


def distance_confidence(xs: np.ndarray, ys: np.ndarray, grid: Grid) -> np.ndarray:
    """Fallback spatial confidence (0-100) from distance to the nearest borehole."""
    mesh_x, mesh_y = np.meshgrid(grid.gx, grid.gy)
    out = np.full(mesh_x.shape, np.nan)
    flat = grid.inside.ravel()
    gxp, gyp = mesh_x.ravel()[flat], mesh_y.ravel()[flat]
    dmin = np.min(np.hypot(gxp[:, None] - xs[None, :], gyp[:, None] - ys[None, :]), axis=1)
    # Decay over the median inter-borehole spacing.
    spacing = _median_spacing(xs, ys)
    conf = 100.0 * np.exp(-dmin / max(spacing, 1.0))
    res = out.ravel()
    res[flat] = np.clip(conf, 0, 100)
    return res.reshape(mesh_x.shape)


def variance_confidence(field: InterpolatedField, grid: Grid) -> np.ndarray:
    """Confidence (0-100) from kriging variance, normalised to its in-hull maximum."""
    var = field.variance
    inside = grid.inside
    vmax = np.nanmax(var[inside]) if np.isfinite(var[inside]).any() else None
    out = np.full(var.shape, np.nan)
    if not vmax or vmax <= 0:
        out[inside] = 100.0
        return out
    out[inside] = np.clip(100.0 * (1.0 - var[inside] / vmax), 0, 100)
    return out


def _median_spacing(xs: np.ndarray, ys: np.ndarray) -> float:
    pts = np.column_stack([xs, ys])
    d = np.hypot(pts[:, None, 0] - pts[None, :, 0], pts[:, None, 1] - pts[None, :, 1])
    np.fill_diagonal(d, np.nan)
    nearest = np.nanmin(d, axis=1)
    return float(np.nanmedian(nearest))

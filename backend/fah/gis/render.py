"""Rasterise score / confidence grids into PNG overlays for Leaflet and KMZ.

Uses the Green/Yellow/Orange/Red ramp from settings; cells outside the data hull are fully
transparent ("insufficient data" — never coloured low).
"""

from __future__ import annotations

import io

import matplotlib

matplotlib.use("Agg")  # headless
import matplotlib.image as mpimg  # noqa: E402
import numpy as np  # noqa: E402

from fah.config import get_settings  # noqa: E402

_OVERLAY_ALPHA = 190  # 0-255


def _hex_to_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _level_ramp() -> tuple[np.ndarray, np.ndarray]:
    """Return (thresholds, colors) arrays for vectorised classification."""
    c = get_settings().colors
    entries = [
        (25.0,  _hex_to_rgb(c.get("low",      "#2ECC40"))),
        (50.0,  _hex_to_rgb(c.get("moderate", "#FFDC00"))),
        (75.0,  _hex_to_rgb(c.get("high",     "#FF851B"))),
        (100.0, _hex_to_rgb(c.get("critical", "#FF4136"))),
    ]
    thresholds = np.array([t for t, _ in entries], dtype=float)
    colors     = np.array([rgb for _, rgb in entries], dtype=np.uint8)
    return thresholds, colors


def score_grid_to_png(score_grid: np.ndarray) -> bytes:
    """Render a score grid (NaN outside hull) to RGBA PNG bytes, north at the top."""
    thresholds, colors = _level_ramp()
    inside = ~np.isnan(score_grid)

    # np.searchsorted: each inside cell gets the index of its colour band.
    idx = np.searchsorted(thresholds, np.where(inside, score_grid, 0.0), side="left")
    idx = np.clip(idx, 0, len(thresholds) - 1)

    ny, nx = score_grid.shape
    rgba = np.zeros((ny, nx, 4), dtype=np.uint8)
    rgba[..., :3] = colors[idx]
    rgba[..., 3]  = np.where(inside, _OVERLAY_ALPHA, 0).astype(np.uint8)

    rgba = np.flipud(rgba)  # grid row 0 = south; image row 0 = north
    buf = io.BytesIO()
    mpimg.imsave(buf, rgba, format="png")
    return buf.getvalue()


def confidence_grid_to_png(conf_grid: np.ndarray) -> bytes:
    """Render confidence (0-100, NaN outside) — low confidence shown as a darker veil."""
    inside = ~np.isnan(conf_grid)
    ny, nx = conf_grid.shape
    rgba = np.zeros((ny, nx, 4), dtype=np.uint8)

    alpha = np.where(inside, np.clip((100.0 - conf_grid) / 100.0 * 160, 0, 160), 0)
    rgba[..., :3] = 40  # dark grey veil colour
    rgba[..., 3]  = alpha.astype(np.uint8)

    rgba = np.flipud(rgba)
    buf = io.BytesIO()
    mpimg.imsave(buf, rgba, format="png")
    return buf.getvalue()

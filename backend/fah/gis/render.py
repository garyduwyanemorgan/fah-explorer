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


def _level_colours() -> list[tuple[float, tuple[int, int, int]]]:
    c = get_settings().colors
    # (inclusive upper score bound, rgb)
    return [
        (25.0, _hex_to_rgb(c.get("low", "#2ECC40"))),
        (50.0, _hex_to_rgb(c.get("moderate", "#FFDC00"))),
        (75.0, _hex_to_rgb(c.get("high", "#FF851B"))),
        (100.0, _hex_to_rgb(c.get("critical", "#FF4136"))),
    ]


def score_grid_to_png(score_grid: np.ndarray) -> bytes:
    """Render a score grid (NaN outside hull) to RGBA PNG bytes, north at the top."""
    ramp = _level_colours()
    ny, nx = score_grid.shape
    rgba = np.zeros((ny, nx, 4), dtype=np.uint8)

    for iy in range(ny):
        for ix in range(nx):
            s = score_grid[iy, ix]
            if np.isnan(s):
                continue
            rgb = next(rgb for ub, rgb in ramp if s <= ub)
            rgba[iy, ix, :3] = rgb
            rgba[iy, ix, 3] = _OVERLAY_ALPHA

    rgba = np.flipud(rgba)  # grid row 0 = south; image row 0 = north
    buf = io.BytesIO()
    mpimg.imsave(buf, rgba, format="png")
    return buf.getvalue()


def confidence_grid_to_png(conf_grid: np.ndarray) -> bytes:
    """Render confidence (0-100, NaN outside) — low confidence shown as a darker veil."""
    ny, nx = conf_grid.shape
    rgba = np.zeros((ny, nx, 4), dtype=np.uint8)
    for iy in range(ny):
        for ix in range(nx):
            v = conf_grid[iy, ix]
            if np.isnan(v):
                continue
            # Lower confidence -> more opaque dark veil.
            rgba[iy, ix, :3] = (40, 40, 40)
            rgba[iy, ix, 3] = int(np.clip((100 - v) / 100 * 160, 0, 160))
    rgba = np.flipud(rgba)
    buf = io.BytesIO()
    mpimg.imsave(buf, rgba, format="png")
    return buf.getvalue()

"""Coordinate geometry helpers.

For Sprint 2 this provides the single function the commit step needs: reproject UTM (or any source
CRS) to WGS84 lon/lat for mapping. If ``pyproj`` is not installed the function degrades gracefully
— it returns ``(None, None)`` and logs once — so commit still succeeds with UTM stored. Full GIS
(domains, interpolation, surfaces) arrives in Sprint 5; see docs/08 and docs/13.
"""

from __future__ import annotations

import logging
from functools import lru_cache

logger = logging.getLogger("fah.gis.geometry")


@lru_cache(maxsize=1)
def _pyproj_available() -> bool:
    try:
        import pyproj  # noqa: F401
    except Exception:
        logger.warning(
            "pyproj not installed - boreholes will be stored with UTM only (lon/lat null). "
            "Install pyproj to enable reprojection for mapping."
        )
        return False
    return True


@lru_cache(maxsize=8)
def _transformer(crs_input: str, crs_storage: str):  # type: ignore[no-untyped-def]
    from pyproj import Transformer

    return Transformer.from_crs(crs_input, crs_storage, always_xy=True)


def to_wgs84(
    easting: float | None,
    northing: float | None,
    crs_input: str,
    crs_storage: str = "EPSG:4326",
) -> tuple[float | None, float | None]:
    """Reproject (easting, northing) in ``crs_input`` to (lon, lat) in WGS84.

    Returns ``(None, None)`` if inputs are missing or pyproj is unavailable.
    """
    if easting is None or northing is None or not _pyproj_available():
        return None, None
    try:
        lon, lat = _transformer(crs_input, crs_storage).transform(easting, northing)
        return float(lon), float(lat)
    except Exception as exc:  # pragma: no cover - depends on CRS validity
        logger.warning("Reprojection failed for (%s, %s) from %s: %s", easting, northing, crs_input, exc)
        return None, None


def working_xy(
    easting: float | None,
    northing: float | None,
    lon: float | None,
    lat: float | None,
    crs_input: str,
) -> tuple[float, float] | None:
    """Best available planar (metre) coordinates for interpolation.

    Prefers source UTM easting/northing; otherwise projects lon/lat into ``crs_input``.
    Returns None if neither is usable.
    """
    if easting is not None and northing is not None:
        return float(easting), float(northing)
    if lon is not None and lat is not None and _pyproj_available():
        x, y = _transformer("EPSG:4326", crs_input).transform(lon, lat)
        return float(x), float(y)
    return None


def metres_bbox_to_lonlat(
    xmin: float, ymin: float, xmax: float, ymax: float, crs_input: str
) -> tuple[float, float, float, float]:
    """Convert a metric bounding box to (south, west, north, east) in WGS84 degrees."""
    if not _pyproj_available():
        raise RuntimeError("pyproj is required to convert grid bounds to lon/lat.")
    t = _transformer(crs_input, "EPSG:4326")
    west, south = t.transform(xmin, ymin)
    east, north = t.transform(xmax, ymax)
    return south, west, north, east

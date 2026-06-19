"""KMZ export — risk surface GroundOverlay + borehole placemarks (opens in Google Earth)."""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path

import numpy as np
import simplekml
from sqlalchemy.orm import Session

from fah.gis.layers import borehole_geojson
from fah.gis.render import score_grid_to_png
from fah.gis.surface import SurfaceSet, build_surfaces

logger = logging.getLogger("fah.gis.export")

# KML placemark colours (aabbggr hex) per level.
_KML_COLOUR = {
    "low": "ff40ce2e",
    "moderate": "ff00dcff",
    "high": "ff1b85ff",
    "critical": "ff3641ff",
}


def export_kmz(
    db: Session, project_id: int, category: str, out_dir: Path, surfaces: SurfaceSet | None = None
) -> Path:
    """Write a KMZ for one risk category. Includes the surface overlay when available."""
    out_dir.mkdir(parents=True, exist_ok=True)
    kml = simplekml.Kml(name=f"FAH Explorer — {category}")

    if surfaces is None:
        surfaces = build_surfaces(db, project_id)

    # Surface GroundOverlay.
    if surfaces is not None and category in surfaces.score_grids:
        grid = surfaces.score_grids[category]
        if np.isfinite(grid).any():
            png = score_grid_to_png(grid)
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                tmp.write(png)
                png_path = tmp.name
            ground = kml.newgroundoverlay(name=f"{category} risk surface")
            ground.icon.href = kml.addfile(png_path)
            south, west, north, east = surfaces.bounds
            ground.latlonbox.south = south
            ground.latlonbox.north = north
            ground.latlonbox.west = west
            ground.latlonbox.east = east
            ground.color = "c8ffffff"  # ~78% opaque

    # Borehole placemarks.
    folder = kml.newfolder(name="Boreholes")
    for feat in borehole_geojson(db, project_id, category)["features"]:
        lon, lat = feat["geometry"]["coordinates"]
        p = feat["properties"]
        pnt = folder.newpoint(name=p["bh_ref"], coords=[(lon, lat)])
        pnt.description = p.get("explanation", "")
        pnt.style.iconstyle.color = _KML_COLOUR.get(p.get("level", ""), "ff777777")

    out_path = out_dir / f"project{project_id}_{category}.kmz"
    kml.savekmz(str(out_path))
    logger.info("Wrote KMZ %s", out_path)
    return out_path

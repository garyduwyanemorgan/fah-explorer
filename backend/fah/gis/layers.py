"""Borehole GeoJSON layers per risk category (for map markers + popups)."""

from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from fah.config import get_settings
from fah.db.models import Borehole, Project, RiskResult
from fah.gis.geometry import to_wgs84

logger = logging.getLogger("fah.gis.layers")


def level_colour(level: str) -> str:
    c = get_settings().colors
    return c.get(level, "#777777")


def _lonlat(bh: Borehole, crs_input: str) -> tuple[float | None, float | None]:
    if bh.lon is not None and bh.lat is not None:
        return bh.lon, bh.lat
    return to_wgs84(bh.easting, bh.northing, crs_input)


def borehole_geojson(db: Session, project_id: int, category: str) -> dict[str, Any]:
    """FeatureCollection of boreholes carrying their risk result for one category."""
    project = db.get(Project, project_id)
    if project is None:
        raise ValueError(f"Project {project_id} not found")
    crs_input = project.crs_input or get_settings().crs_input_default

    boreholes = list(db.scalars(select(Borehole).where(Borehole.project_id == project_id)))
    features: list[dict[str, Any]] = []
    for bh in boreholes:
        lon, lat = _lonlat(bh, crs_input)
        if lon is None or lat is None:
            continue
        rr = db.scalar(
            select(RiskResult).where(
                RiskResult.borehole_id == bh.id, RiskResult.category == category
            )
        )
        props: dict[str, Any] = {"bh_ref": bh.bh_ref, "category": category}
        if rr is not None:
            props.update(
                score=rr.score, level=rr.level, confidence_pct=rr.confidence_pct,
                color=level_colour(rr.level), explanation=rr.explanation,
            )
        features.append(
            {"type": "Feature",
             "geometry": {"type": "Point", "coordinates": [lon, lat]},
             "properties": props}
        )
    return {"type": "FeatureCollection", "features": features}

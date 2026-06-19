"""Spatial routes — borehole GeoJSON, risk surface PNG overlays + metadata, KMZ export."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy.orm import Session

from fah.config import get_settings
from fah.db.session import get_db
from fah.gis import export, layers, render
from fah.gis.surface import get_or_build
from fah.reports import pdf_report
from fah.risk.rules import get_risk_rules

logger = logging.getLogger("fah.api.layers")
router = APIRouter(prefix="/projects", tags=["map"])


def _valid_category(category: str) -> None:
    keys = {c.key for c in get_risk_rules().categories}
    if category not in keys:
        raise HTTPException(404, detail=f"Unknown category '{category}'. One of: {sorted(keys)}")


@router.get("/{project_id}/layers/{category}.geojson")
def layer_geojson(project_id: int, category: str, db: Session = Depends(get_db)) -> JSONResponse:
    _valid_category(category)
    try:
        return JSONResponse(layers.borehole_geojson(db, project_id, category))
    except ValueError as exc:
        raise HTTPException(404, detail=str(exc)) from exc


@router.get("/{project_id}/surface/{category}/meta")
def surface_meta(project_id: int, category: str, db: Session = Depends(get_db)) -> dict:
    _valid_category(category)
    surfaces = get_or_build(db, project_id)
    if surfaces is None:
        return {
            "available": False,
            "reason": "Insufficient located boreholes for a surface (points only).",
        }
    south, west, north, east = surfaces.bounds
    return {
        "available": True,
        "category": category,
        "bounds": {"south": south, "west": west, "north": north, "east": east},
        "method": surfaces.method,
        "n_boreholes": surfaces.n_boreholes,
        "drivers_available": surfaces.drivers_available,
        "engine_version": surfaces.engine_version,
        "png_url": f"/projects/{project_id}/surface/{category}.png",
        "confidence_url": f"/projects/{project_id}/surface/{category}/confidence.png",
    }


@router.get("/{project_id}/surface/{category}.png")
def surface_png(project_id: int, category: str, db: Session = Depends(get_db)) -> Response:
    _valid_category(category)
    surfaces = get_or_build(db, project_id)
    if surfaces is None or category not in surfaces.score_grids:
        raise HTTPException(404, detail="No surface available for this project/category.")
    png = render.score_grid_to_png(surfaces.score_grids[category])
    return Response(content=png, media_type="image/png")


@router.get("/{project_id}/surface/{category}/confidence.png")
def confidence_png(project_id: int, category: str, db: Session = Depends(get_db)) -> Response:
    _valid_category(category)
    surfaces = get_or_build(db, project_id)
    if surfaces is None:
        raise HTTPException(404, detail="No surface available for this project.")
    png = render.confidence_grid_to_png(surfaces.confidence_grid)
    return Response(content=png, media_type="image/png")


@router.get("/{project_id}/export/kmz")
def export_kmz(
    project_id: int, category: str = Query(...), db: Session = Depends(get_db)
) -> FileResponse:
    _valid_category(category)
    surfaces = get_or_build(db, project_id)
    path = export.export_kmz(db, project_id, category, get_settings().exports_dir, surfaces)
    return FileResponse(path, media_type="application/vnd.google-earth.kmz", filename=path.name)


@router.get("/{project_id}/export/pdf")
def export_pdf(
    project_id: int, map_category: str = Query("rise"), db: Session = Depends(get_db)
) -> FileResponse:
    _valid_category(map_category)
    surfaces = get_or_build(db, project_id)
    try:
        path = pdf_report.build_report(
            db, project_id, get_settings().exports_dir, surfaces, map_category
        )
    except pdf_report.ReportError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return FileResponse(path, media_type="application/pdf", filename=path.name)

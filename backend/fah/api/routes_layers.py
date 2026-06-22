"""Spatial routes — borehole GeoJSON, risk surface PNG overlays + metadata, KMZ export."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy.orm import Session

from fah.api.deps import require_project
from fah.config import get_settings
from fah.db.models import Project
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
def layer_geojson(
    project_id: int,
    category: str,
    db: Session = Depends(get_db),
    project: Project = Depends(require_project),
) -> JSONResponse:
    _valid_category(category)
    return JSONResponse(layers.borehole_geojson(db, project.id, category))


@router.get("/{project_id}/surface/{category}/meta")
def surface_meta(
    project_id: int,
    category: str,
    db: Session = Depends(get_db),
    project: Project = Depends(require_project),
) -> dict:
    _valid_category(category)
    surfaces = get_or_build(db, project.id)
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


_PNG_HEADERS = {"Cache-Control": "private, max-age=300"}


@router.get("/{project_id}/surface/{category}.png")
def surface_png(
    project_id: int,
    category: str,
    db: Session = Depends(get_db),
    project: Project = Depends(require_project),
) -> Response:
    _valid_category(category)
    surfaces = get_or_build(db, project.id)
    if surfaces is None or category not in surfaces.score_grids:
        raise HTTPException(
            404,
            detail="No risk surface for this project/category — too few located boreholes. "
            "See /surface/{category}/meta for status.",
        )
    if category not in surfaces._png_cache:
        surfaces._png_cache[category] = render.score_grid_to_png(surfaces.score_grids[category])
    return Response(content=surfaces._png_cache[category], media_type="image/png", headers=_PNG_HEADERS)


@router.get("/{project_id}/surface/{category}/confidence.png")
def confidence_png(
    project_id: int,
    category: str,
    db: Session = Depends(get_db),
    project: Project = Depends(require_project),
) -> Response:
    _valid_category(category)
    surfaces = get_or_build(db, project.id)
    if surfaces is None:
        raise HTTPException(
            404,
            detail="No confidence surface for this project — too few located boreholes. "
            "See /surface/{category}/meta for status.",
        )
    if surfaces._conf_png is None:
        surfaces._conf_png = render.confidence_grid_to_png(surfaces.confidence_grid)
    return Response(content=surfaces._conf_png, media_type="image/png", headers=_PNG_HEADERS)


@router.get("/{project_id}/export/kmz")
def export_kmz(
    project_id: int,
    category: str = Query(...),
    db: Session = Depends(get_db),
    project: Project = Depends(require_project),
) -> FileResponse:
    _valid_category(category)
    surfaces = get_or_build(db, project.id)
    path = export.export_kmz(db, project.id, category, get_settings().exports_dir, surfaces)
    return FileResponse(path, media_type="application/vnd.google-earth.kmz", filename=path.name)


@router.get("/{project_id}/export/pdf")
def export_pdf(
    project_id: int,
    map_category: str = Query("rise"),
    db: Session = Depends(get_db),
    project: Project = Depends(require_project),
) -> FileResponse:
    _valid_category(map_category)
    surfaces = get_or_build(db, project.id)
    try:
        path = pdf_report.build_report(
            db, project.id, get_settings().exports_dir, surfaces, map_category
        )
    except pdf_report.ReportError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return FileResponse(path, media_type="application/pdf", filename=path.name)

"""Serves the interactive Leaflet map page."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from fah.config import PROJECT_ROOT
from fah.db.models import Borehole, Project
from fah.db.session import get_db
from fah.risk.rules import get_risk_rules

router = APIRouter(tags=["map"])
templates = Jinja2Templates(directory=str(PROJECT_ROOT / "frontend" / "templates"))


@router.get("/projects/{project_id}/map", response_class=HTMLResponse)
def project_map(project_id: int, request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(404, detail=f"Project {project_id} not found")
    categories = [{"key": c.key, "label": c.label} for c in get_risk_rules().categories]

    # Compute bounding box from located boreholes so the map opens centred on the site.
    row = db.execute(
        select(
            func.min(Borehole.lat), func.max(Borehole.lat),
            func.min(Borehole.lon), func.max(Borehole.lon),
        ).where(
            Borehole.project_id == project_id,
            Borehole.lat.is_not(None),
            Borehole.lon.is_not(None),
        )
    ).one()
    lat_min, lat_max, lon_min, lon_max = row
    if lat_min is not None:
        bounds = {
            "south": lat_min, "north": lat_max,
            "west": lon_min,  "east": lon_max,
            "lat": (lat_min + lat_max) / 2,
            "lon": (lon_min + lon_max) / 2,
        }
    else:
        bounds = None  # no located boreholes yet; JS falls back to world view

    return templates.TemplateResponse(
        request,
        "map.html",
        {
            "project_id": project_id,
            "project_name": project.name,
            "categories": categories,
            "bounds": bounds,
        },
    )

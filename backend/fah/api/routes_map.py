"""Serves the interactive Leaflet map page."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from fah.config import PROJECT_ROOT
from fah.db.models import Project
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
    return templates.TemplateResponse(
        request,
        "map.html",
        {"project_id": project_id, "project_name": project.name, "categories": categories},
    )

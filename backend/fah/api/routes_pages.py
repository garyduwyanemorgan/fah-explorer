"""Server-rendered workflow pages: dashboard, project workspace, extraction review."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from fah.config import PROJECT_ROOT
from fah.db.models import Borehole, HydroUnit, Project, RiskResult, SourceDocument
from fah.db.session import get_db
from fah.ingest import reviewer

router = APIRouter(tags=["pages"])
templates = Jinja2Templates(directory=str(PROJECT_ROOT / "frontend" / "templates"))


@router.get("/", response_class=HTMLResponse)
def dashboard(request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    projects = []
    for p in db.scalars(select(Project).order_by(Project.created_at.desc())):
        bh = db.scalar(select(func.count(Borehole.id)).where(Borehole.project_id == p.id))
        docs = db.scalar(select(func.count(SourceDocument.id)).where(SourceDocument.project_id == p.id))
        projects.append({"p": p, "boreholes": int(bh or 0), "documents": int(docs or 0)})
    return templates.TemplateResponse(request, "dashboard.html", {"projects": projects})


@router.get("/projects/{project_id}/workspace", response_class=HTMLResponse)
def workspace(project_id: int, request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(404, detail=f"Project {project_id} not found")
    documents = list(
        db.scalars(select(SourceDocument).where(SourceDocument.project_id == project_id)
                   .order_by(SourceDocument.upload_at.desc()))
    )
    counts = {
        "boreholes": db.scalar(select(func.count(Borehole.id)).where(Borehole.project_id == project_id)),
        "hydro_units": db.scalar(
            select(func.count(HydroUnit.id)).join(Borehole).where(Borehole.project_id == project_id)),
        "risk_results": db.scalar(
            select(func.count(RiskResult.id)).join(Borehole).where(Borehole.project_id == project_id)),
    }
    return templates.TemplateResponse(
        request, "workspace.html",
        {"project": project, "documents": documents, "counts": {k: int(v or 0) for k, v in counts.items()}},
    )


@router.get("/projects/{project_id}/documents/{document_id}/review", response_class=HTMLResponse)
def review_page(project_id: int, document_id: int, request: Request,
                db: Session = Depends(get_db)) -> HTMLResponse:
    document = db.get(SourceDocument, document_id)
    if document is None or document.project_id != project_id:
        raise HTTPException(404, detail="Document not found in project")

    ctx: dict = {"project_id": project_id, "document": document, "extracted": False,
                 "payload_json": "", "validation": None}
    try:
        view = reviewer.load_for_review(db, document_id)
        import json
        ctx.update(
            extracted=True,
            payload_json=json.dumps(view.payload, indent=2),
            validation=view.validation,
            model=view.model,
            approved=view.approved,
        )
    except reviewer.ReviewError:
        pass
    return templates.TemplateResponse(request, "review.html", ctx)

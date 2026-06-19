"""Project CRUD routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from fah.api.schemas import ProjectCreate, ProjectOut, ProjectSummary
from fah.db.models import Borehole, Project, SourceDocument
from fah.db.session import get_db

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("", response_model=ProjectOut, status_code=status.HTTP_201_CREATED)
def create_project(payload: ProjectCreate, db: Session = Depends(get_db)) -> Project:
    project = Project(**payload.model_dump())
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


@router.get("", response_model=list[ProjectOut])
def list_projects(db: Session = Depends(get_db)) -> list[Project]:
    return list(db.scalars(select(Project).order_by(Project.created_at.desc())))


@router.get("/{project_id}", response_model=ProjectSummary)
def get_project(project_id: int, db: Session = Depends(get_db)) -> ProjectSummary:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")

    bh_count = db.scalar(
        select(func.count(Borehole.id)).where(Borehole.project_id == project_id)
    )
    doc_count = db.scalar(
        select(func.count(SourceDocument.id)).where(SourceDocument.project_id == project_id)
    )
    return ProjectSummary(
        **ProjectOut.model_validate(project).model_dump(),
        borehole_count=int(bh_count or 0),
        document_count=int(doc_count or 0),
    )

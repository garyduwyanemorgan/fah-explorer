"""Shared FastAPI dependencies.

`require_project` is the single source of truth for "does this project exist?" — used by every
route that reads or writes project-scoped data so an unknown id returns a clean 404 instead of an
empty 200 (which a client cannot distinguish from "project exists but has no data").
"""

from __future__ import annotations

from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session

from fah.db.models import Project
from fah.db.session import get_db


def require_project(project_id: int, db: Session = Depends(get_db)) -> Project:
    """Resolve a project by id or raise 404. Returns the ORM object for reuse by the route."""
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")
    return project

"""Translation route — geotechnical layers → hydrostratigraphy (hydro_units)."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from fah.api.deps import require_project
from fah.db.models import Project
from fah.db.session import get_db
from fah.translate.pipeline import translate_project

logger = logging.getLogger("fah.api.translate")
router = APIRouter(prefix="/projects", tags=["translate"])


class TranslateResult(BaseModel):
    project_id: int
    boreholes: int
    hydro_units: int


@router.post("/{project_id}/translate", response_model=TranslateResult)
def translate(
    project_id: int,
    db: Session = Depends(get_db),
    project: Project = Depends(require_project),
) -> TranslateResult:
    try:
        counts = translate_project(db, project.id)
        db.commit()
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return TranslateResult(project_id=project.id, **counts)

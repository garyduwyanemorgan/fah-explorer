"""Risk routes — compute and read scored, explained risk."""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from fah.api.deps import require_project
from fah.db.models import Borehole, Project, RiskResult
from fah.db.session import get_db
from fah.risk.engine import assess_project

logger = logging.getLogger("fah.api.risk")
router = APIRouter(prefix="/projects", tags=["risk"])


class RiskRequest(BaseModel):
    site: dict = Field(
        default_factory=dict,
        description="Optional project-level site metadata (irrigated, tse_use, tidal_influence, ...).",
    )


class RiskRunResult(BaseModel):
    project_id: int
    boreholes: int
    risk_results: int


class RiskResultOut(BaseModel):
    borehole_ref: str
    category: str
    score: int
    level: str
    confidence_pct: int
    explanation: str
    evidence: list[dict]


@router.post("/{project_id}/risk", response_model=RiskRunResult)
def run_risk(
    project_id: int,
    body: RiskRequest | None = None,
    db: Session = Depends(get_db),
    project: Project = Depends(require_project),
) -> RiskRunResult:
    try:
        counts = assess_project(db, project.id, site=(body.site if body else {}))
        db.commit()
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    # Surfaces depend on risk results — drop any cached surface for this project.
    from fah.gis.surface import invalidate
    invalidate(project_id)
    return RiskRunResult(project_id=project_id, **counts)


@router.get("/{project_id}/risk", response_model=list[RiskResultOut])
def get_risk(
    project_id: int,
    db: Session = Depends(get_db),
    project: Project = Depends(require_project),
) -> list[RiskResultOut]:
    rows = db.scalars(
        select(RiskResult)
        .join(Borehole, RiskResult.borehole_id == Borehole.id)
        .where(Borehole.project_id == project.id)
        .order_by(Borehole.bh_ref, RiskResult.category)
    ).all()
    out: list[RiskResultOut] = []
    for r in rows:
        out.append(
            RiskResultOut(
                borehole_ref=r.borehole.bh_ref,
                category=r.category,
                score=r.score,
                level=r.level,
                confidence_pct=r.confidence_pct,
                explanation=r.explanation or "",
                evidence=json.loads(r.evidence_json) if r.evidence_json else [],
            )
        )
    return out

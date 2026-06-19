"""Extraction routes — run, review, and approve (the human gate)."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from fah.api.schemas import (
    ApproveRequest,
    CommitResult,
    ExtractionView,
    ValidationReport,
)
from fah.db.models import SourceDocument
from fah.db.session import get_db
from fah.ingest import reviewer
from fah.ingest.llm_extractor import LlmNotConfigured

logger = logging.getLogger("fah.api.extraction")
router = APIRouter(prefix="/projects", tags=["extraction"])


def _check_document(db: Session, project_id: int, document_id: int) -> SourceDocument:
    doc = db.get(SourceDocument, document_id)
    if doc is None or doc.project_id != project_id:
        raise HTTPException(404, detail=f"Document {document_id} not found in project {project_id}")
    return doc


def _to_report(v) -> ValidationReport:  # type: ignore[no-untyped-def]
    return ValidationReport(ok=v.ok, errors=v.errors, warnings=v.warnings)


@router.post("/{project_id}/extraction/{document_id}/extract", response_model=ExtractionView)
def run_extraction(project_id: int, document_id: int, db: Session = Depends(get_db)) -> ExtractionView:
    doc = _check_document(db, project_id, document_id)
    try:
        reviewer.run_extraction(db, doc)
        db.commit()
    except LlmNotConfigured as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except reviewer.ReviewError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    view = reviewer.load_for_review(db, document_id)
    return ExtractionView(
        document_id=view.document_id,
        extraction_status=view.extraction_status,
        model=view.model,
        prompt_version=view.prompt_version,
        approved=view.approved,
        payload=view.payload,
        validation=_to_report(view.validation),
    )


@router.get("/{project_id}/extraction/{document_id}", response_model=ExtractionView)
def get_extraction(project_id: int, document_id: int, db: Session = Depends(get_db)) -> ExtractionView:
    _check_document(db, project_id, document_id)
    try:
        view = reviewer.load_for_review(db, document_id)
    except reviewer.ReviewError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ExtractionView(
        document_id=view.document_id,
        extraction_status=view.extraction_status,
        model=view.model,
        prompt_version=view.prompt_version,
        approved=view.approved,
        payload=view.payload,
        validation=_to_report(view.validation),
    )


@router.post(
    "/{project_id}/extraction/{document_id}/approve",
    response_model=CommitResult,
    status_code=status.HTTP_201_CREATED,
)
def approve_extraction(
    project_id: int,
    document_id: int,
    body: ApproveRequest,
    db: Session = Depends(get_db),
) -> CommitResult:
    _check_document(db, project_id, document_id)
    try:
        counts = reviewer.approve_and_commit(
            db, document_id, reviewed_by=body.reviewed_by, corrected_payload=body.payload
        )
        db.commit()
    except reviewer.ReviewError as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return CommitResult(
        document_id=document_id,
        committed=True,
        boreholes=counts["boreholes"],
        layers=counts["layers"],
        lab_results=counts["lab_results"],
    )

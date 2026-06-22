"""Tests for data-integrity fixes: double-commit guard, lab→layer linking,
extraction_status flow, duplicate-upload rejection, _looks_cemented negation."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from fah.db.models import ExtractionRecord, LabResult, Layer, Project, SourceDocument
from fah.ingest.reviewer import ReviewError, _looks_cemented, approve_and_commit

FIXTURE = Path(__file__).parent / "fixtures" / "sample_extraction.json"


def _setup_doc(db: Session, payload: dict | None = None) -> tuple[Project, SourceDocument]:
    payload = payload or json.loads(FIXTURE.read_text())
    project = Project(name="Test Site", crs_input="EPSG:32640")
    db.add(project)
    db.flush()
    doc = SourceDocument(
        project_id=project.id,
        filename="report.pdf",
        file_hash="abc123",
        page_count=5,
        extraction_status="pending",
        stored_path="(test)",
    )
    db.add(doc)
    db.flush()
    db.add(ExtractionRecord(
        source_document_id=doc.id,
        raw_json=json.dumps(payload),
        model="claude-opus-4-8",
        prompt_version="extract-v1",
        approved=False,
    ))
    db.flush()
    return project, doc


# ---------------------------------------------------------------------------
# Double-commit guard
# ---------------------------------------------------------------------------

def test_double_commit_raises(db: Session) -> None:
    _, doc = _setup_doc(db)
    approve_and_commit(db, doc.id, reviewed_by="tester@fah.local")
    db.flush()
    with pytest.raises(ReviewError, match="already been committed"):
        approve_and_commit(db, doc.id, reviewed_by="tester@fah.local")


# ---------------------------------------------------------------------------
# Lab results linked to layers
# ---------------------------------------------------------------------------

def test_lab_results_linked_to_layers(db: Session) -> None:
    _, doc = _setup_doc(db)
    approve_and_commit(db, doc.id, reviewed_by="tester@fah.local")
    db.flush()

    # All lab results that have a depth should be linked to a layer.
    lab_results = db.query(LabResult).all()
    assert lab_results, "no lab results committed"
    for lr in lab_results:
        if lr.depth_m is not None:
            assert lr.layer_id is not None, (
                f"LabResult depth={lr.depth_m} parameter={lr.parameter} has no layer_id"
            )
            layer = db.get(Layer, lr.layer_id)
            assert layer is not None
            assert layer.top_depth_m <= lr.depth_m <= layer.bottom_depth_m


# ---------------------------------------------------------------------------
# extraction_status flow
# ---------------------------------------------------------------------------

def test_extraction_status_pending_after_commit_setup(db: Session) -> None:
    """Document starts as 'pending'; approve_and_commit sets it to 'committed'."""
    _, doc = _setup_doc(db)
    assert doc.extraction_status == "pending"
    approve_and_commit(db, doc.id, reviewed_by="tester@fah.local")
    db.flush()
    db.refresh(doc)
    assert doc.extraction_status == "committed"


# ---------------------------------------------------------------------------
# _looks_cemented negation
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("desc,expected", [
    ("Weakly cemented SANDSTONE / calcarenite", True),
    ("heavily cemented caprock", True),
    ("non-cemented sand", False),
    ("uncemented gravel", False),
    ("not cemented silt", False),
    ("Brown loose sand", False),
    (None, False),
])
def test_looks_cemented(desc: str | None, expected: bool) -> None:
    assert _looks_cemented(desc) is expected

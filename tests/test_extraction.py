"""Sprint 2 — extraction schemas, response parsing, prompt, and the commit gate.

No live API key is required: the network call is isolated in llm_extractor.extract_text, which is
not exercised here. We test the pure functions and the review/commit flow against a fixture.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from fah.db.models import Borehole, ExtractionRecord, LabResult, Layer, Project, SourceDocument
from fah.ingest import reviewer
from fah.ingest.llm_extractor import build_messages, parse_json_response
from fah.ingest.schemas import validate_payload

FIXTURE = Path(__file__).parent / "fixtures" / "sample_extraction.json"


@pytest.fixture()
def payload() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


# --- schemas / validation -------------------------------------------------

def test_valid_payload_passes(payload: dict) -> None:
    v = validate_payload(payload)
    assert v.ok and v.model is not None
    assert len(v.model.boreholes) == 2
    assert v.warnings == []  # fixture is contiguous, has coordinates


def test_non_monotonic_depth_rejected(payload: dict) -> None:
    bad = copy.deepcopy(payload)
    bad["boreholes"][0]["layers"][0]["bottom_depth_m"] = 0.0  # not > top (0.0)
    v = validate_payload(bad)
    assert not v.ok
    assert any("bottom_depth_m" in e for e in v.errors)


def test_layer_gap_is_warning_not_error(payload: dict) -> None:
    gapped = copy.deepcopy(payload)
    gapped["boreholes"][0]["layers"][1]["top_depth_m"] = 2.5  # gap 2.0->2.5
    gapped["boreholes"][0]["layers"][1]["bottom_depth_m"] = 3.5
    v = validate_payload(gapped)
    assert v.ok  # still commits
    assert any("gap" in w for w in v.warnings)


def test_missing_coordinates_warns(payload: dict) -> None:
    nocoord = copy.deepcopy(payload)
    for bh in nocoord["boreholes"]:
        bh["easting"] = bh["northing"] = None
    v = validate_payload(nocoord)
    assert v.ok
    assert any("no coordinates" in w for w in v.warnings)


def test_empty_boreholes_rejected() -> None:
    v = validate_payload({"name": "x", "boreholes": []})
    assert not v.ok


# --- llm_extractor pure functions ----------------------------------------

def test_parse_json_response_handles_fences_and_prose() -> None:
    fenced = 'Here is the data:\n```json\n{"name": "X", "boreholes": []}\n```\nDone.'
    assert parse_json_response(fenced) == {"name": "X", "boreholes": []}
    bare = '{"a": 1}'
    assert parse_json_response(bare) == {"a": 1}


def test_parse_json_response_rejects_garbage() -> None:
    with pytest.raises(ValueError):
        parse_json_response("no json here")


def test_build_messages_includes_text_and_schema() -> None:
    system, messages = build_messages("Borehole BH-01 ...")
    assert "JSON" in system
    assert "Borehole BH-01" in messages[0]["content"]
    assert messages[0]["role"] == "user"


# --- commit gate ----------------------------------------------------------

def _seed_doc_with_extraction(db: Session, raw: dict) -> SourceDocument:
    project = Project(name="P", crs_input="EPSG:32640")
    db.add(project)
    db.flush()
    doc = SourceDocument(
        project_id=project.id, filename="r.pdf", file_hash="abc", page_count=3,
        extraction_status="extracted", stored_path="/tmp/r.pdf",
    )
    db.add(doc)
    db.flush()
    db.add(
        ExtractionRecord(
            source_document_id=doc.id, raw_json=json.dumps(raw),
            model="claude-opus-4-8", prompt_version="extract-v1", approved=False,
        )
    )
    db.flush()
    return doc


def test_approve_and_commit_writes_records(db: Session, payload: dict) -> None:
    doc = _seed_doc_with_extraction(db, payload)

    counts = reviewer.approve_and_commit(db, doc.id, reviewed_by="hydrogeologist@example.com")
    db.commit()

    assert counts == {"boreholes": 2, "layers": 5, "lab_results": 3}
    assert db.scalar(select(func.count(Borehole.id))) == 2
    assert db.scalar(select(func.count(Layer.id))) == 5
    assert db.scalar(select(func.count(LabResult.id))) == 3

    # Provenance + status updated; gate flipped.
    refreshed = db.get(SourceDocument, doc.id)
    assert refreshed.extraction_status == "committed"
    rec = db.scalars(select(ExtractionRecord)).first()
    assert rec.approved is True and rec.reviewed_by == "hydrogeologist@example.com"

    # Cemented sandstone layer detected; gwl elevation derived (3.2 - 1.8 = 1.4).
    bh1 = db.scalars(select(Borehole).where(Borehole.bh_ref == "BH-01")).one()
    assert abs(bh1.gwl_elevation_m - 1.4) < 1e-6
    cemented = [l for l in bh1.layers if l.is_cemented]
    assert len(cemented) == 1 and "calcarenite" in cemented[0].raw_description.lower()


def test_commit_rejects_invalid_corrected_payload(db: Session, payload: dict) -> None:
    doc = _seed_doc_with_extraction(db, payload)
    broken = {"name": "x", "boreholes": []}  # fails validation
    with pytest.raises(reviewer.ReviewError):
        reviewer.approve_and_commit(db, doc.id, reviewed_by="x", corrected_payload=broken)
    # Nothing committed.
    assert db.scalar(select(func.count(Borehole.id))) == 0

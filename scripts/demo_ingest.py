"""Demo: the ingestion → commit → interpret path, end-to-end, with no API key required.

Simulates an LLM extraction from the bundled fixture, runs it through the human-review commit
gate, then translates and scores. Use this to exercise v1 without an Anthropic key.

Usage:  python scripts/demo_ingest.py
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from fah.config import configure_logging  # noqa: E402
from fah.db.models import ExtractionRecord, Project, SourceDocument  # noqa: E402
from fah.db.session import init_db, session_scope  # noqa: E402
from fah.ingest import reviewer  # noqa: E402
from fah.risk.engine import assess_project  # noqa: E402
from fah.translate.pipeline import translate_project  # noqa: E402

FIXTURE = ROOT / "tests" / "fixtures" / "sample_extraction.json"


def main() -> None:
    configure_logging()
    log = logging.getLogger("fah.scripts.demo_ingest")
    init_db()
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))

    with session_scope() as db:
        project = Project(name="Demo Ingest — Fontana Liri", location="Dubai Investment Park",
                          crs_input="EPSG:32640")
        db.add(project); db.flush()

        # Stand in for an uploaded + LLM-extracted document (no API key needed for the demo).
        doc = SourceDocument(project_id=project.id, filename="sample_report.pdf",
                             file_hash="demo", page_count=12, extraction_status="extracted",
                             stored_path="(demo — no file)")
        db.add(doc); db.flush()
        db.add(ExtractionRecord(source_document_id=doc.id, raw_json=json.dumps(payload),
                                model="claude-opus-4-8", prompt_version="extract-v1", approved=False))
        db.flush()

        # Human-review gate -> commit.
        committed = reviewer.approve_and_commit(db, doc.id, reviewed_by="demo@fah.local")
        log.info("Committed: %s", committed)

        # Interpret.
        log.info("Translation: %s", translate_project(db, project.id))
        log.info("Risk: %s", assess_project(db, project.id, site={"irrigated": True, "tse_use": True}))
        log.info("Workspace:  http://127.0.0.1:8000/projects/%d/workspace", project.id)
        log.info("Map:        http://127.0.0.1:8000/projects/%d/map", project.id)


if __name__ == "__main__":
    main()

"""Human-in-the-loop review gate and commit.

Nothing reaches the operational tables (boreholes/layers/lab_results) without explicit approval —
a forensic/legal requirement. This module:

* runs extraction for an archived document and stores the raw output (:func:`run_extraction`),
* loads an extraction for side-by-side review (:func:`load_for_review`),
* validates + commits an approved (optionally corrected) payload (:func:`approve_and_commit`).

See docs/07_PDF_EXTRACTION_WORKFLOW.md (stages 5-6).
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from fah.config import Settings, get_settings
from fah.db.models import (
    Borehole,
    ExtractionRecord,
    LabResult,
    Layer,
    Project,
    SourceDocument,
)
from fah.gis.geometry import to_wgs84
from fah.ingest import llm_extractor
from fah.ingest.pdf_reader import read_pdf
from fah.ingest.schemas import ExtractedProject, ExtractionValidation, validate_payload

logger = logging.getLogger("fah.ingest.reviewer")


class ReviewError(RuntimeError):
    """Raised when review/commit preconditions are not met."""


@dataclass
class ReviewView:
    """What the reviewer UI needs: the parsed payload, the validation report, and provenance."""

    document_id: int
    extraction_status: str
    model: str | None
    prompt_version: str | None
    approved: bool
    payload: dict
    validation: ExtractionValidation


def _latest_record(db: Session, document_id: int) -> ExtractionRecord | None:
    return db.scalar(
        select(ExtractionRecord)
        .where(ExtractionRecord.source_document_id == document_id)
        .order_by(ExtractionRecord.created_at.desc(), ExtractionRecord.id.desc())
    )


def run_extraction(
    db: Session, document: SourceDocument, settings: Settings | None = None
) -> ExtractionRecord:
    """Read the archived PDF, run the LLM extractor, persist the raw output (unapproved)."""
    settings = settings or get_settings()
    if not document.stored_path:
        raise ReviewError(f"Document {document.id} has no archived file path.")

    pdf = Path(document.stored_path)
    if not pdf.exists():
        raise ReviewError(
            f"Archived PDF for document {document.id} is missing at {pdf}."
        )
    read = read_pdf(pdf, ocr_enabled=settings.ocr_enabled, ocr_language=settings.ocr_language)
    if not read.full_text.strip():
        raise ReviewError(
            f"No extractable text in document {document.id} "
            f"({len(read.pages_needing_ocr)} page(s) need OCR)."
        )

    raw, parsed = llm_extractor.extract_text(read.full_text, model=settings.extraction_model)

    record = ExtractionRecord(
        source_document_id=document.id,
        raw_json=raw,
        model=settings.extraction_model,
        prompt_version=settings.extraction_prompt_version,
        approved=False,
    )
    db.add(record)
    document.extraction_status = "extracted"
    db.flush()
    logger.info("Stored extraction record %s for document %s", record.id, document.id)
    return record


def load_for_review(db: Session, document_id: int) -> ReviewView:
    """Load the latest extraction for a document, with its validation report."""
    document = db.get(SourceDocument, document_id)
    if document is None:
        raise ReviewError(f"Document {document_id} not found.")
    record = _latest_record(db, document_id)
    if record is None:
        raise ReviewError(f"No extraction has been run for document {document_id}.")

    payload = json.loads(record.raw_json) if record.raw_json else {}
    return ReviewView(
        document_id=document_id,
        extraction_status=document.extraction_status,
        model=record.model,
        prompt_version=record.prompt_version,
        approved=record.approved,
        payload=payload,
        validation=validate_payload(payload),
    )


def _commit_model(
    db: Session, project: Project, model: ExtractedProject, crs_input: str
) -> dict[str, int]:
    """Write validated boreholes/layers/lab_results, reprojecting coordinates."""
    counts = {"boreholes": 0, "layers": 0, "lab_results": 0}

    # Backfill project metadata if the report carried it and the project lacked it.
    if model.crs and not project.crs_input:
        project.crs_input = model.crs
    project.name = project.name or (model.name or project.name)

    for ebh in model.boreholes:
        lon, lat = ebh.lon, ebh.lat
        if lon is None or lat is None:
            lon, lat = to_wgs84(ebh.easting, ebh.northing, crs_input)
        gwl_elev = None
        if ebh.ground_level_m is not None and ebh.gwl_depth_m is not None:
            gwl_elev = ebh.ground_level_m - ebh.gwl_depth_m

        if lon is None or lat is None:
            logger.warning(
                "Borehole %s has no usable coordinates — it will be committed but will not "
                "appear on the map. Provide easting/northing or lon/lat in the extraction.",
                ebh.bh_ref,
            )

        bh = Borehole(
            project_id=project.id,
            bh_ref=ebh.bh_ref,
            easting=ebh.easting,
            northing=ebh.northing,
            lon=lon,
            lat=lat,
            ground_level_m=ebh.ground_level_m,
            gwl_depth_m=ebh.gwl_depth_m,
            gwl_elevation_m=gwl_elev,
            date_drilled=ebh.date_drilled,
        )
        db.add(bh)
        db.flush()
        counts["boreholes"] += 1

        committed_layers: list[Layer] = []
        for seq, elayer in enumerate(sorted(ebh.layers, key=lambda x: x.top_depth_m), start=1):
            layer = Layer(
                borehole_id=bh.id,
                seq=seq,
                top_depth_m=elayer.top_depth_m,
                bottom_depth_m=elayer.bottom_depth_m,
                raw_description=elayer.raw_description,
                spt_n=elayer.spt_n,
                moisture=elayer.moisture,
                density_desc=elayer.density_desc,
                is_cemented=_looks_cemented(elayer.raw_description),
            )
            db.add(layer)
            db.flush()  # materialise id so lab results can reference it
            committed_layers.append(layer)
            counts["layers"] += 1

        for elab in ebh.lab_results:
            db.add(
                LabResult(
                    borehole_id=bh.id,
                    layer_id=_match_layer_id(elab.depth_m, committed_layers),
                    depth_m=elab.depth_m,
                    parameter=elab.parameter,
                    value=elab.value,
                    unit=elab.unit,
                )
            )
            counts["lab_results"] += 1

    return counts


_CEMENTED_NEGATIONS = ("non-cemented", "non cemented", "uncemented", "not cemented")
_CEMENTED_TERMS = ("cemented", "caprock", "calcarenite", "calcisiltite")


def _looks_cemented(description: str | None) -> bool:
    if not description:
        return False
    d = description.lower()
    if any(t in d for t in _CEMENTED_NEGATIONS):
        return False
    return any(t in d for t in _CEMENTED_TERMS)


def _match_layer_id(depth_m: float | None, layers: list[Layer]) -> int | None:
    """Return the id of the layer whose interval contains depth_m, else None."""
    if depth_m is None or not layers:
        return None
    for layer in layers:
        if layer.top_depth_m <= depth_m <= layer.bottom_depth_m:
            return layer.id
    return None


def approve_and_commit(
    db: Session,
    document_id: int,
    reviewed_by: str,
    corrected_payload: dict | None = None,
    settings: Settings | None = None,
) -> dict[str, int]:
    """Validate and commit the reviewed payload to operational tables. The gate.

    ``corrected_payload`` (the reviewer's edited JSON) takes precedence over the stored raw output.
    Raises :class:`ReviewError` if validation fails — commit is all-or-nothing.
    """
    settings = settings or get_settings()
    document = db.get(SourceDocument, document_id)
    if document is None:
        raise ReviewError(f"Document {document_id} not found.")
    if document.extraction_status == "committed":
        raise ReviewError(
            f"Document {document_id} has already been committed. "
            "Upload the same report again to create a new document record if a re-extraction is needed."
        )
    record = _latest_record(db, document_id)
    if record is None:
        raise ReviewError(f"No extraction has been run for document {document_id}.")

    data = corrected_payload if corrected_payload is not None else json.loads(record.raw_json or "{}")
    validation = validate_payload(data)
    if not validation.ok or validation.model is None:
        raise ReviewError("Cannot commit — validation failed: " + "; ".join(validation.errors))

    project = db.get(Project, document.project_id)
    if project is None:  # pragma: no cover - FK guarantees this
        raise ReviewError(f"Project {document.project_id} not found.")

    crs_input = project.crs_input or settings.crs_input_default
    counts = _commit_model(db, project, validation.model, crs_input)

    record.approved = True
    record.reviewed_by = reviewed_by
    document.extraction_status = "committed"
    db.flush()
    logger.info(
        "Committed document %s by %s: %s (warnings: %d)",
        document_id, reviewed_by, counts, len(validation.warnings),
    )
    return counts

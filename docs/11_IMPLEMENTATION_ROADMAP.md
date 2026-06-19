# 11 — Implementation Roadmap (MVP Version 1)

Built sprint-by-sprint. Each sprint has a concrete **exit criterion**. Application code is gated:
nothing past Sprint 0 starts without sign-off, per the charter's "do not begin coding immediately".

## Sprint 0 — Design & scaffold  ✅ (this deliverable)
- Approve architecture.
- Write all design docs (`docs/00`–`12`).
- Create folder skeleton.
- Author config templates: `settings.yaml`, `translation_rules.yaml`, `risk_rules.yaml`.
- Draft the lithology dictionary.
- **Exit:** documentation + skeleton + rule templates exist; no runtime code yet.

## Sprint 1 — Data spine
- SQLAlchemy models (`db/models.py`) + `init_db.py`.
- Project CRUD API.
- PDF upload: archive + SHA-256 hash → `source_documents`.
- `pdf_reader.py`: pdfplumber text/tables + Tesseract OCR fallback.
- **Exit:** a PDF uploads, is archived & hashed, and text is extracted.

## Sprint 2 — Extraction
- `llm_extractor.py`: Claude → strict JSON (versioned prompt).
- `schemas.py`: pydantic validation (depth monotonicity, coord ranges).
- Review UI + `reviewer.py`: side-by-side PDF vs JSON; approve → commit.
- `extraction_records` audit trail.
- **Exit:** boreholes / layers / SPT / GWL / lab committed to DB from a real report after review.

## Sprint 3 — Translation engine (core IP)
- `translate/rules.py`: YAML loader + provenance.
- `lithology.py`: normalisation + modifier detection.
- `hydraulic.py`: K_h/K_v/anisotropy/storage assignment.
- `hydrostratigraphy.py`: aquifer/aquitard/barrier/perching classification.
- Unit tests (`tests/test_translation.py`).
- **Exit:** `hydro_units` generated for each borehole, with passing golden tests.

## Sprint 4 — Risk engine (core IP)
- `risk/calculators.py`: 10 category calculators from `risk_rules.yaml`.
- `confidence.py`: evidence-completeness scoring.
- `explain.py`: plain-language justification builder.
- `engine.py`: orchestration + persistence with `engine_version`.
- Unit tests (`tests/test_risk_engine.py`) incl. charter worked example.
- **Exit:** every borehole has scored, explained, confidence-rated risks.

## Sprint 5 — Map & frontend (boundary-constrained surfaces — see [doc 13](13_SPATIAL_INTERPOLATION.md))
- `gis/geometry.py` reprojection; `domains.py` (hydrostratigraphic domains, barriers, render mask).
- `interpolate.py`: boundary-constrained, anisotropic interpolation of **drivers** (tiered by N),
  producing value + variance grids.
- `surface.py`: run risk engine per grid cell → risk + confidence surfaces; `raster.py` rasterise.
- Surface + GeoJSON (contours/boundaries/boreholes) endpoints.
- Leaflet map on a **satellite base**: draped risk surfaces, layer toggles, confidence layer,
  legend (incl. "insufficient data" mask), borehole popups with explanations.
- Tests for domain-split (no smear across a barrier) and mask (no extrapolation beyond hull).
- **Exit:** continuous, geology-constrained risk surfaces render over imagery for the 7 charter
  layers, with a confidence layer and honest masking.

## Sprint 6 — Exports & polish
- `gis/export.py`: KMZ (simplekml).
- `reports/pdf_report.py`: forensic PDF report.
- `scripts/demo_ingest.py`; README finalisation.
- **Exit:** full charter loop — upload → extract → translate → score → map → export (KMZ + PDF).

## Suggested ordering rationale
Data spine before extraction (somewhere to put data); extraction before engines (engines need
real inputs); translation before risk (risk consumes hydro_units); engines before map (map renders
scores); exports last (they serialise finished results).

## Verification per the plan
- `pytest tests/` green (translation + risk + ingest + gis).
- `python scripts/demo_ingest.py` runs the end-to-end loop on a sample report.
- `python -m mypy backend/` clean.

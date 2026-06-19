# 07 — PDF Extraction Workflow

Turns uploaded geotechnical PDFs into validated structured data, with an explicit **human-review
gate** before anything touches the database. Code: `backend/fah/ingest/`.

## Pipeline

```
upload PDF
   │
   ▼
[1] archive + hash         data/uploads/  (immutable)  + SHA-256 → source_documents
   │
   ▼
[2] pdf_reader.py          pdfplumber: text + tables
   │   └─ page has no extractable text? ──► Tesseract OCR on rendered page image
   │                                        (ocr_used = true)
   ▼
[3] llm_extractor.py       Claude (text; vision for scanned pages)
   │                       versioned prompt → STRICT JSON
   ▼
[4] schemas.py             pydantic validation
   │                       (types, depth monotonicity, coord ranges, units)
   ▼
[5] reviewer.py            HUMAN-IN-THE-LOOP  ── side-by-side PDF vs parsed JSON
   │                       REQUIRED before commit (forensic/legal integrity)
   ▼
[6] commit                 boreholes / layers / lab_results
                           + extraction_records (raw_json, model, prompt_version)
```

## Stage detail

### [1] Archive + hash
Raw PDF copied to `data/uploads/` and **never mutated**. SHA-256 stored in `source_documents`.
This is the root of the chain of custody.

### [2] Read — `pdf_reader.py`
`pdfplumber` extracts text and tables per page. Pages with no extractable text (scanned images)
are rendered and passed through **Tesseract OCR**; `ocr_used` is flagged. If neither Tesseract
nor its language data is installed, the module fails with a clear, actionable message (it does not
silently skip pages).

### [3] Extract — `llm_extractor.py`
Page text (and page images for scans) → **Anthropic Claude** with a **versioned prompt**. The
model returns strict JSON only. Target schema:

```json
{
  "project": { "name": "...", "location": "...", "developer": "...", "report_date": "YYYY-MM-DD",
               "crs": "EPSG:32640" },
  "boreholes": [
    {
      "bh_ref": "BH-01",
      "easting": 512345.6, "northing": 2765432.1,
      "ground_level_m": 3.20, "gwl_depth_m": 1.80, "date_drilled": "YYYY-MM-DD",
      "layers": [
        { "top_depth_m": 0.0, "bottom_depth_m": 2.0,
          "raw_description": "Brown silty SAND, loose",
          "spt_n": 8, "moisture": "moist", "density_desc": "loose" }
      ],
      "lab_results": [
        { "depth_m": 1.5, "parameter": "chloride", "value": 4200, "unit": "mg/L" }
      ]
    }
  ]
}
```

The raw model output is stored verbatim in `extraction_records.raw_json` with the `model` and
`prompt_version` — so any extraction is **reproducible and defensible**.

### [4] Validate — `schemas.py`
Pydantic models enforce:
- types and required fields,
- **depth monotonicity** (`bottom_depth_m > top_depth_m`; layers contiguous/ordered),
- **coordinate ranges** (plausible UTM 40N easting/northing or lon/lat),
- unit sanity (e.g. mg/L ranges).

Failures surface as structured, field-level errors for the reviewer — they do not silently drop.

### [5] Review — `reviewer.py`  (REQUIRED GATE)
The UI shows the **source PDF page beside the parsed JSON**. A human corrects/confirms, then
approves. `extraction_records.approved` flips to true and records `reviewed_by`. **Nothing is
committed to the operational tables without this step** — a hard requirement for forensic/legal
integrity.

### [6] Commit
On approval, validated records are written to `boreholes`, `layers`, `lab_results`. Coordinates
are reprojected to WGS84 by [`gis/geometry.py`](08_GIS_ARCHITECTURE.md) (UTM 40N → EPSG:4326).
`source_documents.extraction_status` → `committed`.

## Reproducibility & defensibility

| Artefact | Stored where | Why |
|----------|--------------|-----|
| Raw PDF | `data/uploads/` (immutable) + hash | Source of truth |
| Raw LLM JSON | `extraction_records.raw_json` | Re-run / audit extraction |
| Model + prompt version | `extraction_records` | Reproduce exact extraction |
| Reviewer + approval | `extraction_records` | Accountability |
| Validation errors | extraction artefact (`data/extracted/`) | Audit trail |

## Failure handling

- **No `ANTHROPIC_API_KEY`** → clear error pointing to `.env.example`; pipeline stops at [3].
- **Tesseract missing** → clear error with install guidance; pipeline stops at [2] for scanned PDFs.
- **Validation fails** → routed to reviewer with field-level errors; never auto-committed.

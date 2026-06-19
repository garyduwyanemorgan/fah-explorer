# 03 — System Architecture

## Design principle

The **translation engine** and **risk engine** are the centre of gravity. They are pure-Python,
isolated, fully unit-testable, and driven by YAML rule files so domain experts can tune the logic
without touching code. Ingest, GIS, API, and frontend are thin layers around that core.

## Stack decisions

| Concern | Choice | Rationale |
|---------|--------|-----------|
| Backend | **Python 3.11+ / FastAPI** | Async API, pydantic validation, OpenAPI for free |
| Database | **SQLite (MVP)** → PostGIS later | Zero-setup MVP; schema is PostGIS-ready |
| ORM | **SQLAlchemy** | DB-agnostic; eases the PostGIS migration |
| GIS | **GeoPandas · Shapely · pyproj** | Reprojection, geometry, interpolation |
| Frontend | **FastAPI + Jinja2 + Leaflet.js** | Fewest moving parts to MVP; full map control |
| Static export | **Folium** (maps) · **simplekml** (KMZ) | One-off artefacts, not the live UI |
| PDF read | **pdfplumber** + **Tesseract** (OCR fallback) | Text PDFs fast; scanned pages covered |
| Extraction | **Anthropic Claude** (vision + text) | LLM-assisted parse to strict JSON |
| Reports | **reportlab / weasyprint** | Per-project forensic PDF |
| Config | **YAML** | Externalised, auditable rules |

## Component map

```
                    ┌─────────────────────────────────────────────┐
                    │                FRONTEND                      │
                    │  Jinja2 templates + Leaflet.js + vanilla JS  │
                    │  dashboard · interactive risk map · review   │
                    └───────────────────────┬─────────────────────┘
                                             │ HTTP / JSON · GeoJSON
                    ┌────────────────────────▼─────────────────────┐
                    │              FastAPI  (backend/fah/api)       │
                    │  projects · upload · translate · risk · export│
                    └───┬───────────┬───────────┬───────────┬───────┘
                        │           │           │           │
              ┌─────────▼──┐  ┌─────▼─────┐ ┌───▼────┐ ┌────▼─────┐
              │  INGEST    │  │ TRANSLATE │ │  RISK  │ │   GIS    │
              │ pdf→OCR→   │  │ lithology │ │ 10     │ │ geometry │
              │ Claude→    │  │ →hydraulic│ │ calcs  │ │ interp.  │
              │ review     │  │ →hydro-   │ │ +conf  │ │ layers   │
              │            │  │  strat    │ │ +explain│ │ export  │
              └─────┬──────┘  └─────┬─────┘ └───┬────┘ └────┬─────┘
                    │               │           │           │
                    └───────────────┴─────┬─────┴───────────┘
                                          │ SQLAlchemy ORM
                              ┌───────────▼────────────┐
                              │   DATABASE (SQLite)     │
                              │  projects · boreholes · │
                              │  layers · hydro_units · │
                              │  risk_results · source  │
                              └─────────────────────────┘
        ┌─────────────────┐                              ┌──────────────────┐
        │ config/*.yaml    │ ── rules ──► translate/risk  │ data/uploads (raw │
        │ (the IP)         │                              │ PDFs, immutable)  │
        └─────────────────┘                              └──────────────────┘
```

## End-to-end data flow

```
PDF upload
  → archive + hash (immutable)               [ingest/pdf_reader]
  → text / OCR extraction                     [ingest/pdf_reader]
  → Claude → strict JSON                       [ingest/llm_extractor]
  → pydantic validation                        [ingest/schemas]
  → HUMAN REVIEW (required gate)               [ingest/reviewer]
  → commit boreholes / layers / lab            [db]
  → TRANSLATE: lithology → K → hydrostrat      [translate/*]
  → RISK: 10 categories + confidence + why     [risk/*]
  → GIS: domains/barriers → interpolate DRIVERS
         (boundary-constrained) → risk per cell
         → confidence surface → rasterise        [gis/*, see doc 13]
  → MAP (surface draped on imagery) + KMZ + PDF [frontend, gis/export]
```

## Module responsibilities

| Package | Responsibility |
|---------|----------------|
| `backend/fah/db` | ORM models, session, reference-data seed |
| `backend/fah/ingest` | PDF → validated structured data, with review gate |
| `backend/fah/translate` | **Core IP** — geotech → hydrostratigraphy |
| `backend/fah/risk` | **Core IP** — hydrostratigraphy → scored, explained risk |
| `backend/fah/gis` | Geometry/reprojection, **domains & barriers**, boundary-constrained **interpolation of drivers**, per-cell risk **surface**, rasterise, layers, export ([doc 13](13_SPATIAL_INTERPOLATION.md)) |
| `backend/fah/api` | FastAPI route handlers |
| `backend/fah/reports` | Forensic PDF report generation |
| `frontend` | Jinja2 templates, Leaflet map, review UI |
| `config` | Externalised translation & risk rules (tunable IP) |

## Cross-cutting requirements

- **Type hints** on all public functions; `mypy`-checkable.
- **`pathlib`** for all paths — no hardcoded paths; paths come from `settings.yaml`.
- **`logging`** module, never `print`.
- **Reproducibility** — every output reconstructable from archived source + versioned rules
  (forensic/legal requirement).
- **Graceful degradation** — every module that needs an external engine (OCR, LLM) must handle
  its absence with a clear, actionable error.

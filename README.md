# FAH Explorer

**Forensic Asset Hydrogeology Explorer** — a decision-support platform that transforms archived
GCC geotechnical reports into groundwater behaviour and asset-risk intelligence.

> Core IP — the **translation layer**:
> `Geotechnical Data → Hydrostratigraphy → Groundwater Behaviour → Asset Risk`

FAH Explorer is **not** a groundwater model and **not** a geotechnical database. It is an
explainable decision-support system: every risk score it produces carries a **level**, a
**confidence score**, the **evidence used**, and a plain-language **hydrogeological explanation**.

## Status

🟢 **MVP built (Sprints 0–6 complete).** The full charter loop runs end-to-end — upload → extract
(Claude + OCR, human-reviewed) → translate → risk (10 explained, confidence-rated categories) →
interactive map (interpolated surfaces + confidence) → KMZ + forensic PDF export. **41 tests pass.**
Built sprint-by-sprint per the [implementation roadmap](docs/11_IMPLEMENTATION_ROADMAP.md).

```bash
cd fah-explorer
pip install -e .                          # or install the deps in pyproject.toml
python scripts/init_db.py                 # create schema + seed lithology dictionary
python scripts/demo_ingest.py             # ingest→commit→translate→risk (no API key needed)
python scripts/demo_surface.py            # build a multi-borehole project + surface + KMZ + PDF
uvicorn fah.main:app --app-dir backend    # then open http://127.0.0.1:8000/  (dashboard)
python -m pytest                          # 41 tests
```

The web UI starts at the **dashboard** (`/`): create a project → **workspace** (upload PDF, run
extraction, review &amp; approve, translate, score risk) → **map** (interpolated risk surfaces +
confidence + popups) → export KMZ / forensic PDF. Live LLM extraction needs `ANTHROPIC_API_KEY`
in `.env`; everything else runs without it.

## Documentation

Start at **[docs/00_INDEX.md](docs/00_INDEX.md)**. Highlights:

- [Project Vision](docs/01_PROJECT_VISION.md) · [Domain Knowledge](docs/02_DOMAIN_KNOWLEDGE_FAH.md)
- [System Architecture](docs/03_SYSTEM_ARCHITECTURE.md) · [Database Schema](docs/04_DATABASE_SCHEMA.md)
- [Hydrostratigraphic Translation](docs/05_HYDROSTRATIGRAPHIC_TRANSLATION.md) (core IP) ·
  [Risk Scoring Framework](docs/06_RISK_SCORING_FRAMEWORK.md) (core IP)
- [PDF Extraction Workflow](docs/07_PDF_EXTRACTION_WORKFLOW.md) ·
  [GIS Architecture](docs/08_GIS_ARCHITECTURE.md) · [API Design](docs/09_API_DESIGN.md)
- [MVP Requirements](docs/10_MVP_REQUIREMENTS.md) ·
  [Implementation Roadmap](docs/11_IMPLEMENTATION_ROADMAP.md) ·
  [Future Roadmap](docs/12_FUTURE_ROADMAP.md)

## Stack (planned for the MVP)

| Layer | Choice |
|-------|--------|
| Backend | Python 3.11+ · FastAPI |
| Database | SQLite (MVP) → PostGIS later · SQLAlchemy |
| GIS | GeoPandas · Shapely · pyproj · Leaflet.js (Folium/simplekml for export) |
| Extraction | pdfplumber · Tesseract OCR · Anthropic Claude |
| Reports | reportlab / weasyprint (PDF) · simplekml (KMZ) |

## The MVP loop

```
upload PDF → extract (LLM + OCR, human-reviewed) → store
           → translate (geotech → hydrostratigraphy)
           → score 10 risk categories (level + confidence + evidence + explanation)
           → interactive map (Green/Yellow/Orange/Red)
           → export KMZ + forensic PDF
```

## Layout

```
fah-explorer/
├── docs/         # design documentation (read 00_INDEX.md first)
├── config/       # externalised IP: translation_rules.yaml, risk_rules.yaml, settings.yaml
├── backend/fah/  # FastAPI app: db · ingest · translate · risk · gis · api · reports
├── frontend/     # Jinja2 templates + Leaflet map
├── data/         # uploads (immutable) · extracted · exports · SQLite db
├── scripts/      # init_db, lithology loader, demo_ingest
└── tests/        # translation · risk · gis · ingest
```

## Configuration

Copy [`.env.example`](.env.example) → `.env` and set `ANTHROPIC_API_KEY`. Runtime settings live in
[`config/settings.yaml`](config/settings.yaml). The domain rules — the platform's intellectual
property — live in [`config/translation_rules.yaml`](config/translation_rules.yaml) and
[`config/risk_rules.yaml`](config/risk_rules.yaml) and are tunable without code changes.

## License / use

Built for GCC forensic hydrogeology investigations. Outputs are designed to be reproducible and
defensible (forensic/legal requirement): raw reports are archived immutably and every derived
value is traceable to its source.

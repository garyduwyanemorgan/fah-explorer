# FAH Explorer — Documentation Index

**FAH Explorer** (Forensic Asset Hydrogeology Explorer) is a decision-support system that
transforms archived geotechnical reports into groundwater behaviour and asset-risk intelligence.

> Core IP — the **translation layer**:
> `Geotechnical Data → Hydrostratigraphy → Groundwater Behaviour → Asset Risk`

## Read in this order

| # | Document | What it covers |
|---|----------|----------------|
| 01 | [Project Vision](01_PROJECT_VISION.md) | Mission, what it is / is not |
| 02 | [Domain Knowledge (FAH)](02_DOMAIN_KNOWLEDGE_FAH.md) | FAH principle, GCC context, Dubai geology, TSE, Sabkha, Tasreef |
| 03 | [System Architecture](03_SYSTEM_ARCHITECTURE.md) | Components, data flow, stack decisions |
| 04 | [Database Schema](04_DATABASE_SCHEMA.md) | Tables, relationships, ERD, forensic traceability |
| 05 | [Hydrostratigraphic Translation](05_HYDROSTRATIGRAPHIC_TRANSLATION.md) | The core IP: lithology → hydraulic properties → hydrostratigraphy |
| 06 | [Risk Scoring Framework](06_RISK_SCORING_FRAMEWORK.md) | 10 risk categories, scoring, confidence, explanation |
| 07 | [PDF Extraction Workflow](07_PDF_EXTRACTION_WORKFLOW.md) | Upload → OCR → LLM → review → commit |
| 08 | [GIS Architecture](08_GIS_ARCHITECTURE.md) | Layers, colour scheme, interpolation, KMZ/PDF export |
| 09 | [API Design](09_API_DESIGN.md) | FastAPI endpoint contracts |
| 10 | [MVP Requirements](10_MVP_REQUIREMENTS.md) | Scope in / out for Version 1 |
| 11 | [Implementation Roadmap](11_IMPLEMENTATION_ROADMAP.md) | Sprint-by-sprint build plan |
| 12 | [Future Roadmap](12_FUTURE_ROADMAP.md) | v2 (MODFLOW/Hydrus/Rosetta/RS), v3 (insurance/portfolio) |
| 13 | [Spatial Interpolation](13_SPATIAL_INTERPOLATION.md) | **Core IP** — boundary-constrained, anisotropic surfaces from sparse boreholes; confidence as a surface |

## Configuration (the externalised IP)

| File | Purpose |
|------|---------|
| [`../config/translation_rules.yaml`](../config/translation_rules.yaml) | Lithology → hydraulic property rules |
| [`../config/risk_rules.yaml`](../config/risk_rules.yaml) | Risk category factors, weights, thresholds |
| [`../config/settings.yaml`](../config/settings.yaml) | Paths, CRS, model name, runtime settings |

## Project status

**MVP built (Sprints 0–6 complete).** The full charter loop runs end-to-end:
upload → extract (Claude + OCR, human-reviewed) → translate → risk (10 categories, scored/
explained/confidence-rated) → interactive map (interpolated surfaces + confidence) → KMZ + PDF
export. 41 tests pass. See the [roadmap](11_IMPLEMENTATION_ROADMAP.md) for per-sprint detail and
`scripts/demo_surface.py` for an end-to-end demonstration.

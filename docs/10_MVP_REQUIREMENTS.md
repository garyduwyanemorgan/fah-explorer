# 10 — MVP Requirements (Version 1)

> Charter constraint: **No MODFLOW. No calibration. No numerical modelling. Keep it simple.**

## In scope (the MVP must do)

1. **Upload** geotechnical reports (PDF).
2. **Extract** borehole information, groundwater levels, stratigraphy, SPT values, lab results,
   coordinates — via the [LLM-assisted pipeline](07_PDF_EXTRACTION_WORKFLOW.md) with human review.
3. **Store** in a structured database (SQLite).
4. **Translate** geotechnical data → hydrogeological interpretation (the
   [translation engine](05_HYDROSTRATIGRAPHIC_TRANSLATION.md)).
5. **Score** risk across the [10 categories](06_RISK_SCORING_FRAMEWORK.md), each with level,
   confidence, evidence, and explanation.
6. **Display** results spatially on an interactive [Leaflet map](08_GIS_ARCHITECTURE.md).
7. **Export** KMZ and PDF reports.

### Map layers (must render)

Groundwater Rise · Groundwater Mounding · Perching Potential · Salinity Risk · Asset Risk ·
Flood Susceptibility · Hydrostratigraphic Barriers — coloured Green/Yellow/Orange/Red.

### Risk philosophy (non-negotiable)

Every score shows **Risk Level + Confidence + Evidence Used + Hydrogeological Explanation**. The
platform explains *why*, it does not merely display data.

## Out of scope (Version 1)

- MODFLOW / SEAWAT / GWT numerical groundwater modelling
- HYDRUS-1D vadose modelling
- PEST++ calibration
- Rosetta PTF
- Remote sensing / satellite / InSAR
- Live groundwater monitoring feeds
- Insurance / portfolio / developer / municipality dashboards
- PostGIS (SQLite is sufficient for v1; schema is PostGIS-ready)
- Multi-user auth / roles (single-operator assumption for v1)

These belong to the [Future Roadmap](12_FUTURE_ROADMAP.md).

## Definition of done

The full charter loop runs end-to-end on a real geotechnical report:

```
upload PDF → extract → review/approve → translate → score → interactive map → KMZ + PDF export
```

…with every risk score carrying its level, confidence, evidence, and explanation, and full
provenance from raw PDF to score.

## Acceptance checks

- Charter worked example reproduces: GWL 1.8 m + cemented layer 3.5 m + irrigation + Sabkha →
  **Groundwater Rise = High**, confidence ≈ 84%.
- Lithology translation: loose sand → high K; cemented → low K_v + perching flag; sabkha →
  salinity flag.
- KMZ opens in Google Earth with correctly coloured, foldered placemarks.
- PDF report lists each borehole's risks with explanations.

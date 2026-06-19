# 09 — API Design (FastAPI)

Thin HTTP layer over the engines. JSON in/out; GeoJSON for map layers; file downloads for exports.
Code: `backend/fah/api/`. OpenAPI docs auto-served at `/docs`.

## Endpoints

| Method | Route | Purpose |
|--------|-------|---------|
| POST | `/projects` | Create a project |
| GET | `/projects` | List projects |
| GET | `/projects/{id}` | Project + borehole summary |
| POST | `/projects/{id}/upload` | Upload PDF → archive + hash + text/OCR |
| POST | `/projects/{id}/extraction/{doc}/extract` | Run LLM extraction (stores raw, unapproved) |
| GET | `/projects/{id}/extraction/{doc}` | Review parsed JSON + validation |
| POST | `/projects/{id}/extraction/{doc}/approve` | Commit reviewed data (the gate) |
| POST | `/projects/{id}/translate` | Run translation engine → `hydro_units` |
| POST | `/projects/{id}/risk` | Run risk scoring (optional `{site}`) → `risk_results` |
| GET | `/projects/{id}/risk` | List risk results |
| GET | `/projects/{id}/layers/{category}.geojson` | Borehole markers for a category |
| GET | `/projects/{id}/surface/{category}/meta` | Risk-surface metadata (bounds, method, drivers) |
| GET | `/projects/{id}/surface/{category}.png` | Risk-surface raster overlay |
| GET | `/projects/{id}/surface/{category}/confidence.png` | Confidence overlay |
| GET | `/projects/{id}/export/kmz?category=` | Download KMZ (GroundOverlay) |
| GET | `/projects/{id}/export/pdf?map_category=` | Download forensic PDF report |

### HTML pages (server-rendered, Jinja2 + Leaflet)

| Route | Page |
|-------|------|
| `/` | Dashboard — list / create projects |
| `/projects/{id}/workspace` | Upload, extract, review, translate, risk, export links |
| `/projects/{id}/documents/{doc}/review` | Human-review gate — editable JSON + validation + approve |
| `/projects/{id}/map` | Interactive risk map (surfaces + confidence + popups) |

## Route module mapping

| Module | Routes |
|--------|--------|
| `routes_projects.py` | create / list / get project |
| `routes_upload.py` | upload + archive + hash |
| `routes_extraction.py` | extract / review / approve (the gate) |
| `routes_translate.py` | translation engine |
| `routes_risk.py` | risk scoring + read |
| `routes_layers.py` | GeoJSON, surface PNG/meta, KMZ, PDF |
| `routes_map.py` · `routes_pages.py` | interactive map + dashboard/workspace/review pages |
| `routes_export.py` | KMZ, PDF |

## Representative payloads

### `POST /projects`
```json
{ "name": "Marina Plot 7", "location": "Dubai Marina", "developer": "ACME",
  "report_date": "2024-09-01", "crs_input": "EPSG:32640" }
```

### `GET /projects/{id}/layers/groundwater_rise.geojson`
```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "geometry": { "type": "Point", "coordinates": [55.140, 25.080] },
      "properties": {
        "bh_ref": "BH-03", "category": "rise",
        "score": 70, "level": "high", "confidence_pct": 84,
        "explanation": "Groundwater Rise Risk = High ...",
        "color": "#FF851B"
      }
    }
  ]
}
```

### `POST /projects/{id}/risk` → response
```json
{ "boreholes_scored": 12, "categories": 10, "engine_version": "rules-1.0+code-0.1" }
```

## Conventions

- **Validation** via pydantic request/response models (shared with ingest schemas where relevant).
- **Errors** as structured JSON (`{"detail": ...}`); 4xx for client/validation, 5xx with clear
  messages for missing engines (OCR/LLM) per the graceful-degradation rule.
- **Idempotency** — `translate` and `risk` recompute and replace derived rows, stamping
  `engine_version`.
- **Async** handlers; long-running extraction may run as a background task with status polled via
  `GET /projects/{id}/extraction/{doc}`.

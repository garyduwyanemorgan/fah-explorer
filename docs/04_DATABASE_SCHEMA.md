# 04 — Database Schema

SQLite for the MVP; the schema is **PostGIS-ready**. Geometry is stored as plain numeric
lon/lat (+ source easting/northing) columns now, swappable to native `geometry` columns later.
ORM lives in `backend/fah/db/models.py` (SQLAlchemy).

## Design rules

- **Provenance everywhere.** Every *derived* row records what it was `derived_from`, giving a
  chain of custody from raw PDF → risk score (forensic/legal requirement).
- **Raw is immutable.** Source PDFs and raw LLM output are archived and never mutated.
- **Reference data is seeded**, not user-entered (e.g. the lithology dictionary).

## ERD (logical)

```
projects ──1:*── source_documents ──1:*── extraction_records
   │
   └──1:*── boreholes ──1:*── layers ──1:*── lab_results
                 │
                 ├──1:*── hydro_units      (derived; derived_from → layer ids)
                 └──1:*── risk_results     (derived; evidence_json → inputs)

lithology_dictionary   (reference / seed; referenced by layers.lithology_code)
```

## Tables

### `projects`
| col | type | notes |
|-----|------|-------|
| id | INTEGER PK | |
| name | TEXT | |
| location | TEXT | site / emirate |
| developer | TEXT | |
| report_date | DATE | |
| crs_input | TEXT | e.g. `EPSG:32640` (UTM 40N) |
| created_at | TIMESTAMP | default now |

### `source_documents` — chain of custody
| col | type | notes |
|-----|------|-------|
| id | INTEGER PK | |
| project_id | FK → projects | |
| filename | TEXT | original name |
| file_hash | TEXT | SHA-256 of archived PDF |
| page_count | INTEGER | |
| upload_at | TIMESTAMP | |
| ocr_used | BOOLEAN | scanned pages encountered |
| extraction_status | TEXT | pending / extracted / reviewed / committed / rejected |

### `boreholes`
| col | type | notes |
|-----|------|-------|
| id | INTEGER PK | |
| project_id | FK → projects | |
| bh_ref | TEXT | e.g. `BH-01` |
| easting | REAL | source UTM (nullable) |
| northing | REAL | source UTM (nullable) |
| lon | REAL | WGS84 (reprojected) |
| lat | REAL | WGS84 (reprojected) |
| ground_level_m | REAL | mAOD/mDMD if given |
| gwl_depth_m | REAL | depth to groundwater below ground |
| gwl_elevation_m | REAL | derived: ground_level − gwl_depth |
| date_drilled | DATE | |

### `layers` — stratigraphy (one row per described interval)
| col | type | notes |
|-----|------|-------|
| id | INTEGER PK | |
| borehole_id | FK → boreholes | |
| seq | INTEGER | order within log |
| top_depth_m | REAL | |
| bottom_depth_m | REAL | bottom > top (validated) |
| raw_description | TEXT | verbatim from report |
| lithology_code | TEXT | normalised → `lithology_dictionary.code` |
| spt_n | INTEGER | nullable |
| moisture | TEXT | nullable |
| density_desc | TEXT | loose / medium dense / dense … |
| is_cemented | BOOLEAN | detected modifier |

### `lab_results`
| col | type | notes |
|-----|------|-------|
| id | INTEGER PK | |
| borehole_id | FK → boreholes | |
| layer_id | FK → layers | nullable |
| depth_m | REAL | |
| parameter | TEXT | chloride / sulphate / TDS / pH / … |
| value | REAL | |
| unit | TEXT | mg/L, % … |

### `hydro_units` — derived hydrostratigraphy (output of translation engine)
| col | type | notes |
|-----|------|-------|
| id | INTEGER PK | |
| borehole_id | FK → boreholes | |
| top_depth_m | REAL | |
| bottom_depth_m | REAL | |
| unit_type | TEXT | aquifer / aquitard / barrier / perching_layer |
| k_h_m_day | REAL | horizontal conductivity |
| k_v_m_day | REAL | vertical conductivity |
| anisotropy | REAL | k_h / k_v |
| storage_class | TEXT | low / moderate / high |
| derived_from | TEXT (JSON) | source layer ids + rule ids |

### `risk_results` — one row per (borehole × category)
| col | type | notes |
|-----|------|-------|
| id | INTEGER PK | |
| borehole_id | FK → boreholes | |
| category | TEXT (enum) | rise / mounding / perching / salinity / sulphate / chloride / asset_deterioration / flood / dewatering / liability |
| score | INTEGER | 0–100 |
| level | TEXT | low / moderate / high / critical |
| confidence_pct | INTEGER | 0–100 |
| explanation | TEXT | rendered plain-language "why" |
| evidence_json | TEXT (JSON) | structured factor list driving the score |
| engine_version | TEXT | rules/engine version for reproducibility |
| computed_at | TIMESTAMP | |

### `extraction_records` — raw LLM output (audit / reproducibility)
| col | type | notes |
|-----|------|-------|
| id | INTEGER PK | |
| source_document_id | FK → source_documents | |
| raw_json | TEXT | verbatim LLM output |
| model | TEXT | e.g. `claude-opus-4-8` |
| prompt_version | TEXT | versioned prompt id |
| reviewed_by | TEXT | reviewer identity |
| approved | BOOLEAN | gate before commit |

### `lithology_dictionary` — reference / seed
| col | type | notes |
|-----|------|-------|
| code | TEXT PK | canonical lithology code |
| canonical_name | TEXT | |
| synonyms_json | TEXT (JSON) | matching synonyms / keywords |
| default_k_h | REAL | default horizontal K |
| default_k_v | REAL | default vertical K |
| storage_class | TEXT | low / moderate / high |
| cemented_default | BOOLEAN | |
| salinity_flag | BOOLEAN | salinity source (e.g. sabkha) |

## Enumerations

- `risk_results.category` — the 10 categories listed above (see
  [Risk Scoring Framework](06_RISK_SCORING_FRAMEWORK.md)).
- `risk_results.level` / map colour — Low (green) · Moderate (yellow) · High (orange) ·
  Critical (red).
- `hydro_units.unit_type` — aquifer · aquitard · barrier · perching_layer.

## PostGIS migration note

When moving to PostGIS: convert `boreholes(lon, lat)` to a `geometry(Point, 4326)` column and add
spatial indexes; interpolated risk surfaces (see [GIS](08_GIS_ARCHITECTURE.md)) become
`geometry(Polygon, 4326)`. SQLAlchemy + GeoAlchemy2 keeps ORM changes minimal.

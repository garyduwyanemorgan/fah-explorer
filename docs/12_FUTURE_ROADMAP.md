# 12 — Future Roadmap

The MVP ([Version 1](10_MVP_REQUIREMENTS.md)) deliberately excludes numerical modelling. These
versions build on the same translation-layer IP and database.

## Version 2 — Physics & remote sensing

| Capability | Adds |
|------------|------|
| **MODFLOW integration** | Replace/augment qualitative groundwater behaviour with numerical flow simulation seeded from FAH hydrostratigraphy |
| **HYDRUS integration** | Vadose-zone (Richards' eq.) columns for perching/infiltration realism |
| **Rosetta PTF** | Pedotransfer functions: derive hydraulic params from texture/density rather than dictionary defaults → higher confidence |
| **Satellite / remote sensing** | InSAR displacement, land-use, irrigation extent to inform risk factors |
| **Groundwater monitoring** | Ingest time-series from monitoring wells to validate and update risk |
| **PostGIS migration** | Move geometry to native spatial columns + spatial indexing |

## Version 3 — Risk products & dashboards

| Capability | Adds |
|------------|------|
| **Insurance risk scoring** | Translate asset risk into insurability / premium signals |
| **Portfolio risk** | Aggregate risk across many sites for asset owners |
| **Developer asset risk scoring** | Per-development risk profiles for decision-making |
| **Municipality dashboard** | Region-wide groundwater & asset-risk intelligence (e.g. Tasreef planning support) |

## Guiding constraint

Every future capability must still answer the core question:

> *"What does this mean for groundwater behaviour and asset performance?"*

Numerical engines (MODFLOW/HYDRUS) **augment** the explainable translation layer; they do not
replace it. The forensic, "explain-why" character of every output is preserved across all versions.

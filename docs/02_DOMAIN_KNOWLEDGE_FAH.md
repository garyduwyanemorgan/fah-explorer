# 02 — Domain Knowledge (Forensic Asset Hydrogeology)

## Core principle

> **Geotechnical properties ≠ Hydrogeological behaviour.**

A geotechnical report describes *materials*. FAH Explorer infers *behaviour*. The platform's job
is to translate between them:

| Geotechnical input | Translates to |
|--------------------|---------------|
| Soils (lithology, density) | Hydraulic conductivity (K_h, K_v) |
| Stratigraphy (layer stack) | Flow pathways / hydrostratigraphic units |
| Groundwater levels | Storage capacity, saturation geometry |
| Chemistry (Cl, SO₄, TDS) | Salinity & chemical attack risk |
| **Combined** | **Asset risk** |

## GCC / Dubai context

### Geological layer structure (top to bottom)

1. **Engineered Fill** (0–2 m) — high-K imported material, often hydraulically connected to
   utilities.
2. **Natural Ground / Aeolian Sand** (2–5 m) — variable, often calcareous.
3. **Sabkha** (variable) — salt-cemented silts/sands. **The critical layer.** Dissolution →
   collapse; primary salinity source.
4. **Calcarenite / Caprock** — weathered, karstified in places.
5. **Dammam Formation** — regional Paleogene limestone aquifer; lower boundary.

Utility trenches cut through the shallow layers and create **preferential flow paths** (vadose
zone puncturing) — modelled conceptually as high-K corridors.

### Key terms

- **TSE** — Treated Sewage Effluent, TDS ~1,500 mg/L. A major source of shallow recharge
  ("Shadow Aquifer") driving groundwater rise where used for irrigation.
- **Sabkha** — salt-cemented coastal/inland flat. High salinity source, high evaporative
  concentration, high asset-attack potential.
- **Tasreef** — Dubai Municipality groundwater dewatering/drainage programme (multi-billion AED).
  A site's dewatering dependence is a liability signal.
- **Shallow groundwater** — the dominant driver of asset risk in the region.

## How a hydrogeologist reads a report (encoded in the engine)

- **Loose sand** → high hydraulic conductivity → water moves freely.
- **Dense sand** → moderate conductivity.
- **Cemented sand / sandstone** → reduced *vertical* conductivity → **perching** above it.
- **Sandstone** → hydrostratigraphic control layer.
- **Calcisiltite** → groundwater barrier potential.
- **Sabkha** → salinity source.
- **Shallow groundwater** → increased asset risk.

These narrative rules are formalised in the
[Hydrostratigraphic Translation engine](05_HYDROSTRATIGRAPHIC_TRANSLATION.md) and externalised in
[`translation_rules.yaml`](../config/translation_rules.yaml).

## Why "forensic"

Outputs must be **defensible**. Every derived value (hydraulic property, hydrostratigraphic unit,
risk score) is traceable back to the raw report it came from — a chain of custody from PDF to
conclusion. This requirement shapes the [database schema](04_DATABASE_SCHEMA.md) (provenance on
every derived row) and the [extraction workflow](07_PDF_EXTRACTION_WORKFLOW.md) (immutable source
archive, versioned prompts, human review).

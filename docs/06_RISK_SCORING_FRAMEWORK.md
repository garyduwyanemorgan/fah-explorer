# 06 — Risk Scoring Framework

Converts hydrostratigraphy + site context into **scored, explained, confidence-rated risk** for
every borehole. Driven by [`risk_rules.yaml`](../config/risk_rules.yaml).
Code: `backend/fah/risk/{engine,calculators,confidence,explain}.py`.

## Output contract (every score)

| Field | Meaning |
|-------|---------|
| **score** | 0–100 (additive weighted factors) |
| **level** | Low / Moderate / High / Critical |
| **confidence_pct** | evidence completeness & quality, 0–100 |
| **evidence_json** | structured list of factors that fired |
| **explanation** | plain-language "why" |

### Score → Level → Colour

| Score | Level | Map colour |
|-------|-------|-----------|
| 0–25 | Low | 🟢 Green |
| 26–50 | Moderate | 🟡 Yellow |
| 51–75 | High | 🟠 Orange |
| 76–100 | Critical | 🔴 Red |

## The 10 risk categories

1. Groundwater Rise
2. Groundwater Mounding
3. Perched Water
4. Salinity
5. Sulphate Attack
6. Chloride Attack
7. Asset Deterioration
8. Flood Susceptibility
9. Dewatering Dependence
10. Long-Term Liability

## Scoring model

**Additive weighted factors.** Each category defines contributing factors with point weights
(capped at 100). Factors draw from boreholes, layers, hydro_units, lab_results, and site metadata.

### Groundwater Rise (charter example)

| Factor | Points |
|--------|--------|
| Shallow water table (< 2 m) | +20 |
| Hard / cemented layer < 5 m | +25 |
| Irrigated / landscaped area | +20 |
| Sabkha influence | +15 |
| Pond / open water nearby | +10 |
| TSE use in area | +10 |

### Representative factors for other categories

| Category | Key factors (illustrative; full set in YAML) |
|----------|-----------------------------------------------|
| **Mounding** | Low-K layer below recharge zone; high-K over low-K_v contrast; local recharge source |
| **Perched Water** | Perching_layer present above regional table; high-K over cemented/clay; shallow saturation |
| **Salinity** | Sabkha present; high Cl/TDS lab values; evaporative setting; shallow saline table |
| **Sulphate Attack** | SO₄ in soil/groundwater above thresholds (BRE/ACI bands); shallow GW contact with foundations |
| **Chloride Attack** | Cl above corrosion thresholds; shallow GW; reinforced concrete exposure |
| **Asset Deterioration** | Composite of salinity + sulphate + chloride + shallow GW + cyclic wetting |
| **Flood Susceptibility** | Shallow table + low-permeability surface + low ground level + poor drainage |
| **Dewatering Dependence** | High-K aquifer + shallow table + deep excavation context |
| **Long-Term Liability** | Composite + Sabkha dissolution/collapse potential + reliance on Tasreef dewatering |

> Chemical-attack thresholds (sulphate/chloride) follow recognised exposure classes; exact bands
> are parameters in `risk_rules.yaml` so they can be aligned to the governing code.

## Confidence  (`confidence.py`)

Confidence reflects **how much of the required evidence was actually present and how reliable it
was**:

```
measured value      → weight 1.0   (e.g. logged GWL, lab Cl)
inferred value      → weight 0.7   (derived from description/SPT)
dictionary default  → weight 0.4   (no site-specific input)
missing             → weight 0.0
```

`confidence_pct = Σ(weight × factor_importance) / Σ(factor_importance) × 100`, rounded. A score
built mostly on measured inputs scores high; one leaning on defaults scores low — the charter's
84% in the worked example reflects mostly-measured evidence with one inferred factor.

## Explanation  (`explain.py`)

Renders the charter-style justification from `evidence_json`:

```
Groundwater Rise Risk = High (score 70, confidence 84%)
Reason:
 • Groundwater depth = 1.8 m            (measured, BH-03)
 • Cemented layer at 3.5 m              (derived, perching geometry)
 • Irrigated landscape                  (site metadata)
 • Sabkha influence                     (lithology BH-03 @ 4.2 m)
```

Each bullet names the factor, its value, and its **source/reliability tag** — so a reviewer can
trace it. This satisfies the charter's mandate that the platform **explain why**, not just show
data.

## Engine flow

```
for each borehole:
    gather inputs (borehole, layers, hydro_units, lab, site metadata)
    for each of the 10 categories:
        factors  = calculators.<category>(inputs)      # which factors fired + points
        score    = clamp(sum(points), 0, 100)
        level    = band(score)
        conf     = confidence(factors, inputs)
        text     = explain(category, score, level, conf, factors)
        persist risk_results(... engine_version ...)
```

`engine_version` (rules hash + code version) is stored on every row for reproducibility.

## Pointwise vs. surface evaluation

The same calculators run in two contexts:
- **Per borehole** — stored in `risk_results` (above), used for popups, tables, and the PDF report.
- **Per grid cell** — the identical engine runs on **interpolated driver surfaces** to produce the
  continuous risk map. The map is *not* an interpolation of point scores; it is the engine
  evaluated everywhere on geology-constrained driver fields, with a matching confidence surface.
  See [13 — Spatial Interpolation](13_SPATIAL_INTERPOLATION.md).

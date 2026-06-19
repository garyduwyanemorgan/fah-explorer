# 05 — Hydrostratigraphic Translation Engine (Core IP)

This is the heart of FAH Explorer. It converts described materials into hydrogeological
behaviour. All logic is **rule-driven from [`translation_rules.yaml`](../config/translation_rules.yaml)**
so it is auditable and tunable without code changes. **Every output carries provenance** — which
input layer and which rule produced it.

```
raw soil description  →  [A] lithology  →  [B] hydraulic props  →  [C] hydrostratigraphy
```

Code: `backend/fah/translate/{lithology,hydraulic,hydrostratigraphy,rules}.py`.

---

## Stage A — Lithology normalisation  (`lithology.py`)

Free-text soil descriptions → canonical `lithology_code` via the lithology dictionary
(synonym + keyword matching). Also detects **modifiers**:

- **Density** — loose / medium dense / dense / very dense (also inferred from SPT-N).
- **Cementation** — "cemented", "weakly cemented", "caprock" → `is_cemented`.
- **Moisture** — dry / moist / wet / saturated.
- **Salinity indicators** — sabkha, gypsum, halite, evaporite → salinity flag.

Example: *"Light brown, weakly cemented calcareous SAND, dense"* →
`lithology_code = sand`, `is_cemented = true`, `density = dense`.

---

## Stage B — Hydraulic property assignment  (`hydraulic.py`)

Each layer → **(K_h, K_v, anisotropy, storage class)** from dictionary defaults, adjusted by
modifiers. The charter translation rules, formalised:

| Lithology | K_h | K_v | Storage | Perching potential | Notes |
|-----------|-----|-----|---------|--------------------|-------|
| Loose sand | High | High | Moderate | Low | Free-draining; moderate GW-rise contribution |
| Dense sand | Moderate | Moderate | Low | Moderate | |
| Cemented sand / sandstone | Moderate | **Low** | Low | **High** | Vertical barrier → perching; hydrostratigraphic control |
| Calcarenite / caprock | Mod. (karst variable) | Low | Low | High | Karstification adds uncertainty → lowers confidence |
| Calcisiltite | Low | **Very low** | Low | High (barrier) | **Groundwater barrier potential** |
| Sabkha | Low | Low | Low | Moderate | **Salinity source**; evaporative concentration |
| Clay / silt | Very low | Very low | High | High (aquitard) | Classic aquitard |
| Engineered fill | High | High | Moderate | Low | Often connected to utilities → preferential path |

### Modifier adjustments

- **Density / SPT-N**: within a lithology, higher density (or SPT-N) → lower K. SPT-N refines K
  on a graded scale (e.g. very loose → very dense maps across ~1.5 orders of magnitude).
- **Cementation**: drops **K_v** sharply → raises **anisotropy** (k_h/k_v) → sets the
  **perching flag**.
- **Moisture/saturation**: informs the saturation geometry used downstream, not K itself.

Qualitative bands (High/Moderate/Low/Very low) map to numeric K ranges (m/day) defined in
`translation_rules.yaml`, so the engine produces both a class and a number.

---

## Stage C — Hydrostratigraphic model  (`hydrostratigraphy.py`)

The layer stack per borehole → classified **hydro-units**:

| unit_type | Definition |
|-----------|------------|
| **aquifer** | High-K, transmissive, water-bearing |
| **aquitard** | Low-K, retards vertical flow |
| **barrier** | Very-low-K, laterally continuous → controls/blocks flow |
| **perching_layer** | Low K_v beneath higher-K material → traps water above the regional table |

The stage identifies:

- **Perching geometry** — position of the water table relative to low-K_v layers (a high-K layer
  sitting on a cemented/clay layer above the regional water table → perched water).
- **Hydrostratigraphic barriers** — continuous low-K units (a dedicated map output layer).
- **Mounding potential** — vertical conductivity contrasts that trap or mound recharge.

Output is written to `hydro_units` and consumed by the [risk engine](06_RISK_SCORING_FRAMEWORK.md).

### No silent guessing

If an input is missing (e.g. no SPT, ambiguous description), the engine uses the dictionary
default **and records that it did so**. Missing/low-quality evidence **reduces the downstream
confidence score** rather than fabricating a precise value. Provenance (`derived_from`) records
the source layers and the rule ids applied.

---

## Provenance contract

Each `hydro_unit` records, in `derived_from`:

```json
{
  "source_layer_ids": [12, 13],
  "rules_applied": ["litho.sand", "modifier.cemented", "hydrostrat.perching_v_contrast"],
  "inputs_observed": {"spt_n": 38, "is_cemented": true},
  "defaults_used": ["k_v_default_for_sand"]
}
```

This is what makes the interpretation **forensic** — defensible back to the source report.

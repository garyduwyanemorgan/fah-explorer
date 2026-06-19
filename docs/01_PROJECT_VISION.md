# 01 — Project Vision

## Product

**FAH Explorer** — Forensic Asset Hydrogeology Explorer.

## Mission

Transform geotechnical information into **hydrogeological behaviour** and **asset-risk
intelligence**, and create a decision-support platform that explains *why* water is a risk —
not merely *that* it is.

## The problem

The GCC has accumulated thousands of geotechnical reports containing borehole logs, groundwater
levels, soil descriptions, SPT values, laboratory results and stratigraphy. These reports are
typically used once during design and then archived.

They contain hidden hydrogeological intelligence. Almost none of it is ever converted into:

- groundwater behaviour
- groundwater rise / mounding / perching susceptibility
- salinity risk
- asset degradation risk
- flood susceptibility
- dewatering dependence

## What FAH Explorer IS

A **decision-support system** built around a single piece of intellectual property — the
**translation layer**:

```
Geotechnical Data → Hydrostratigraphy → Groundwater Behaviour → Asset Risk
```

Every feature must answer one question:

> *"What does this mean for groundwater behaviour and asset performance?"*

## What FAH Explorer is NOT

- It is **NOT** a groundwater model (no MODFLOW/Hydrus numerical modelling in the MVP).
- It is **NOT** a geotechnical database (storage is a means, not the product).

The product is the **interpretation** — the translation from data to behaviour to risk.

## Risk philosophy

The platform must not simply show data; it must **explain why**. For every risk score it produces:

- **Risk Level** — Low / Moderate / High / Critical
- **Confidence Score** — a percentage reflecting evidence completeness and quality
- **Evidence Used** — the structured inputs that drove the score
- **Hydrogeological Explanation** — plain-language justification

### Worked example (charter)

```
Groundwater Rise Risk = High
Reason:
 • Groundwater depth = 1.8 m
 • Cemented layer at 3.5 m
 • Irrigated landscape
 • Sabkha influence
Confidence = 84%
```

## Outcome

A hydrogeological intelligence platform for the GCC that turns dormant geotechnical reports into
live groundwater and asset-risk intelligence — spatial, explainable, and exportable.

See [Domain Knowledge](02_DOMAIN_KNOWLEDGE_FAH.md) next.

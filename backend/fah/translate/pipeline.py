"""Translation orchestrator — runs Stages A→C per layer and persists hydro-units.

For each layer: normalise lithology → assign hydraulic properties → classify hydro-unit, then
backfill the layer's normalised ``lithology_code`` / ``is_cemented`` and write a ``HydroUnit``
with full provenance (``derived_from``). Idempotent per borehole/project (replaces prior units).
See docs/05 and docs/11 (Sprint 3).
"""

from __future__ import annotations

import json
import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from fah.db.models import Borehole, HydroUnit, Layer, Project
from fah.translate import hydraulic, hydrostratigraphy, lithology
from fah.translate.rules import TranslationRules, get_rules

logger = logging.getLogger("fah.translate.pipeline")


def _translate_layer(layer: Layer, rules: TranslationRules) -> HydroUnit:
    match = lithology.normalise(layer.raw_description, layer.spt_n, rules)
    hyd = hydraulic.assign(match, rules)
    unit_type, hs_rule = hydrostratigraphy.classify(match, hyd, rules)

    # Backfill the normalised interpretation onto the layer (translation is the authority).
    layer.lithology_code = match.code
    layer.is_cemented = match.is_cemented

    derived_from = {
        "source_layer_ids": [layer.id],
        "lithology_code": match.code,
        "matched_synonym": match.matched_synonym,
        "rules_applied": [*match.rules_applied, *hyd.rules_applied, hs_rule],
        "inputs_observed": {
            "spt_n": layer.spt_n,
            "density": match.density,
            "is_cemented": match.is_cemented,
            "moisture": match.moisture,
        },
        "defaults_used": hyd.defaults_used,
        "rules_version": rules.version,
    }

    return HydroUnit(
        borehole_id=layer.borehole_id,
        top_depth_m=layer.top_depth_m,
        bottom_depth_m=layer.bottom_depth_m,
        unit_type=unit_type,
        k_h_m_day=hyd.k_h_m_day,
        k_v_m_day=hyd.k_v_m_day,
        anisotropy=hyd.anisotropy,
        storage_class=hyd.storage_class,
        derived_from=json.dumps(derived_from),
    )


def translate_borehole(db: Session, borehole: Borehole, rules: TranslationRules | None = None) -> int:
    """(Re)generate hydro-units for one borehole. Returns the number of units created."""
    rules = rules or get_rules()

    # Idempotent: clear existing derived units first (query by id — do not trust the ORM
    # relationship collection, which may be stale across commits).
    existing = db.scalars(
        select(HydroUnit).where(HydroUnit.borehole_id == borehole.id)
    ).all()
    for unit in existing:
        db.delete(unit)
    db.flush()

    layers = sorted(borehole.layers, key=lambda x: x.top_depth_m)
    units = [_translate_layer(layer, rules) for layer in layers]
    db.add_all(units)
    db.flush()
    logger.info("Translated borehole %s: %d hydro-units", borehole.bh_ref, len(units))
    return len(units)


def translate_project(db: Session, project_id: int, rules: TranslationRules | None = None) -> dict[str, int]:
    """Translate every borehole in a project. Returns counts."""
    rules = rules or get_rules()
    project = db.get(Project, project_id)
    if project is None:
        raise ValueError(f"Project {project_id} not found")

    boreholes = list(db.scalars(select(Borehole).where(Borehole.project_id == project_id)))
    total_units = sum(translate_borehole(db, bh, rules) for bh in boreholes)
    return {"boreholes": len(boreholes), "hydro_units": total_units}

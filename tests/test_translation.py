"""Sprint 3 — the hydrostratigraphic translation engine (core IP).

Golden assertions tie the engine to the charter translation rules.
"""

from __future__ import annotations

import json

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from fah.db.models import Borehole, HydroUnit, Layer, Project
from fah.translate import hydraulic, hydrostratigraphy, lithology
from fah.translate.pipeline import translate_borehole, translate_project
from fah.translate.rules import get_rules


def _interpret(description: str, spt_n: int | None = None):
    rules = get_rules()
    m = lithology.normalise(description, spt_n, rules)
    h = hydraulic.assign(m, rules)
    unit, _ = hydrostratigraphy.classify(m, h, rules)
    return m, h, unit


# --- charter translation rules -------------------------------------------

def test_loose_sand_high_k_aquifer() -> None:
    m, h, unit = _interpret("Brown silty SAND, loose", spt_n=6)
    assert m.code == "sand"
    assert h.k_h_band == "high"        # charter: loose sand -> High
    assert unit == "aquifer"


def test_dense_sand_moderate_k() -> None:
    _, h, unit = _interpret("Pale calcareous SAND, dense", spt_n=32)
    assert h.k_h_band == "moderate"    # charter: dense sand -> Moderate
    assert unit == "aquifer"


def test_cemented_sand_low_kv_perching() -> None:
    m, h, unit = _interpret("Cemented SAND", spt_n=None)
    assert m.code == "sand" and m.is_cemented and m.cementation_extra
    assert h.perching_flag is True
    assert h.k_v_band in ("low", "very_low")   # vertical K suppressed
    assert h.anisotropy > 1.0                  # cementation raises anisotropy
    assert unit == "perching_layer"


def test_sandstone_is_perching_control() -> None:
    # Sandstone base K already encodes cementation; must NOT be double-shifted into a barrier.
    _, h, unit = _interpret("Weakly cemented SANDSTONE / calcarenite")
    assert h.k_v_band == "low"
    assert unit == "perching_layer"


def test_calcisiltite_is_barrier() -> None:
    m, h, unit = _interpret("Grey CALCISILTITE")
    assert m.code == "calcisiltite"
    assert h.k_v_band == "very_low"
    assert unit == "barrier"


def test_sabkha_salinity_source() -> None:
    m, _, unit = _interpret("Grey SABKHA, gypsiferous")
    assert m.code == "sabkha"
    assert m.salinity_flag is True     # charter: sabkha -> salinity source
    assert unit == "aquitard"


def test_clay_is_aquitard() -> None:
    _, _, unit = _interpret("Stiff CLAY")
    assert unit == "aquitard"


def test_unknown_lithology_flags_default() -> None:
    m, h, _ = _interpret("Unrecognisable description xyz")
    assert m.code is None
    assert "unknown_lithology_defaults" in h.defaults_used


# --- persistence + provenance --------------------------------------------

def _build_borehole(db: Session) -> Borehole:
    project = Project(name="P")
    db.add(project)
    db.flush()
    bh = Borehole(project_id=project.id, bh_ref="BH-01", gwl_depth_m=1.8)
    db.add(bh)
    db.flush()
    specs = [
        (0.0, 2.0, "Brown silty SAND, loose", 6),
        (2.0, 3.5, "Pale calcareous SAND, dense", 32),
        (3.5, 8.0, "Weakly cemented SANDSTONE / calcarenite", None),
    ]
    for i, (top, bot, desc, n) in enumerate(specs, start=1):
        db.add(Layer(borehole_id=bh.id, seq=i, top_depth_m=top, bottom_depth_m=bot,
                     raw_description=desc, spt_n=n))
    db.commit()
    return bh


def test_translate_borehole_persists_with_provenance(db: Session) -> None:
    bh = _build_borehole(db)
    n = translate_borehole(db, bh)
    db.commit()
    assert n == 3
    assert db.scalar(select(func.count(HydroUnit.id))) == 3

    units = db.scalars(select(HydroUnit).order_by(HydroUnit.top_depth_m)).all()
    types = [u.unit_type for u in units]
    assert types == ["aquifer", "aquifer", "perching_layer"]

    # Provenance is traceable back to the source layer + rules.
    prov = json.loads(units[2].derived_from)
    assert prov["lithology_code"] == "sandstone"
    assert prov["source_layer_ids"]
    assert any("hydrostrat" in r for r in prov["rules_applied"])
    assert prov["rules_version"]

    # Layer lithology_code was backfilled by translation.
    backfilled = db.scalars(select(Layer).order_by(Layer.seq)).all()
    assert backfilled[0].lithology_code == "sand"
    assert backfilled[2].is_cemented is True


def test_translate_is_idempotent(db: Session) -> None:
    bh = _build_borehole(db)
    translate_borehole(db, bh); db.commit()
    translate_borehole(db, db.get(Borehole, bh.id)); db.commit()
    # Re-running replaces rather than appends.
    assert db.scalar(select(func.count(HydroUnit.id))) == 3


def test_translate_project_counts(db: Session) -> None:
    bh = _build_borehole(db)
    counts = translate_project(db, bh.project_id)
    db.commit()
    assert counts == {"boreholes": 1, "hydro_units": 3}

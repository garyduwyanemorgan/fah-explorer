"""Sprint 4 — the risk engine: scoring, confidence, explanation, composites, persistence.

Includes the charter worked example for Groundwater Rise.
"""

from __future__ import annotations

import json

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from fah.db.models import Borehole, Layer, LabResult, Project, RiskResult
from fah.risk import calculators
from fah.risk.context import RiskContext
from fah.risk.engine import assess_borehole, assess_project
from fah.risk.rules import get_risk_rules
from fah.translate.pipeline import translate_borehole


# --- condition evaluator (unit) ------------------------------------------

def _bare_ctx(**kw) -> RiskContext:
    return RiskContext(borehole_ref="BH", gwl_depth_m=kw.get("gwl"), ground_level_m=kw.get("gl"),
                       site=kw.get("site", {}))


def test_evaluate_numeric_lab_site_flag_risk() -> None:
    ctx = _bare_ctx(gwl=1.8, site={"irrigated": True})
    assert calculators.evaluate({"var": "gwl_depth_m", "op": "lt", "value": 2.0}, ctx, {}) is True
    assert calculators.evaluate({"var": "gwl_depth_m", "op": "gt", "value": 2.0}, ctx, {}) is False
    assert calculators.evaluate({"site": "irrigated"}, ctx, {}) is True
    assert calculators.evaluate({"site": "tse_use"}, ctx, {}) is False
    # risk composite reads prior levels
    assert calculators.evaluate({"risk": "salinity", "level_in": ["high", "critical"]}, ctx,
                                {"salinity": "critical"}) is True
    # missing numeric -> False (never crashes)
    assert calculators.evaluate({"var": "gwl_depth_m", "op": "lt", "value": 2.0}, _bare_ctx(), {}) is False


def test_evaluate_lab_between() -> None:
    ctx = RiskContext(borehole_ref="BH", gwl_depth_m=None, ground_level_m=None,
                      lab_results=[LabResult(parameter="sulphate", value=2000)])
    assert calculators.evaluate({"lab": "sulphate", "op": "between", "min": 1500, "max": 3000}, ctx, {}) is True
    assert calculators.evaluate({"lab": "sulphate", "op": "gt", "value": 3000}, ctx, {}) is False


# --- full borehole assessment (integration) ------------------------------

def _charter_borehole(db: Session) -> Borehole:
    """gwl 1.8 m, sabkha at 2-3.5 m, cemented sandstone 3.5-8 m + aggressive chemistry."""
    project = Project(name="Charter")
    db.add(project); db.flush()
    bh = Borehole(project_id=project.id, bh_ref="BH-03", gwl_depth_m=1.8, ground_level_m=3.2)
    db.add(bh); db.flush()
    db.add(Layer(borehole_id=bh.id, seq=1, top_depth_m=0.0, bottom_depth_m=2.0,
                 raw_description="Brown silty SAND, loose", spt_n=6))
    db.add(Layer(borehole_id=bh.id, seq=2, top_depth_m=2.0, bottom_depth_m=3.5,
                 raw_description="Grey SABKHA, gypsiferous", spt_n=None))
    db.add(Layer(borehole_id=bh.id, seq=3, top_depth_m=3.5, bottom_depth_m=8.0,
                 raw_description="Weakly cemented SANDSTONE / calcarenite", spt_n=None))
    db.add(LabResult(borehole_id=bh.id, depth_m=1.5, parameter="chloride", value=6000, unit="mg/L"))
    db.add(LabResult(borehole_id=bh.id, depth_m=1.5, parameter="sulphate", value=4000, unit="mg/L"))
    db.add(LabResult(borehole_id=bh.id, depth_m=2.0, parameter="tds", value=48000, unit="mg/L"))
    db.commit()
    translate_borehole(db, bh); db.commit()
    return bh


def test_charter_groundwater_rise(db: Session) -> None:
    bh = _charter_borehole(db)
    # Site context known (all False) so confidence is high and Rise stays High (not Critical).
    site = {"irrigated": False, "tse_use": False, "open_water_nearby": False}
    results = {r.category: r for r in assess_borehole(RiskContext.from_borehole(bh, site))}

    rise = results["rise"]
    # shallow WT (20) + cemented layer <5 m (25) + sabkha (15) = 60 -> High
    assert rise.level == "high"
    assert 51 <= rise.score <= 75
    assert rise.confidence_pct >= 80          # mostly measured/known evidence (charter ~84%)
    assert "Sabkha influence" in rise.explanation
    assert "1.8" in rise.explanation          # groundwater depth value shown


def test_composite_categories_chain(db: Session) -> None:
    bh = _charter_borehole(db)
    results = {r.category: r for r in assess_borehole(RiskContext.from_borehole(bh, {}))}

    # Chemistry drives the attack categories high...
    assert results["salinity"].level in ("high", "critical")
    assert results["sulphate"].level in ("high", "critical")
    assert results["chloride"].level in ("high", "critical")
    # ...which the composite asset_deterioration consumes.
    asset = results["asset_deterioration"]
    assert asset.level in ("high", "critical")
    fired = {e["id"] for e in asset.evidence if e["fired"]}
    assert {"salinity_component", "sulphate_component", "chloride_component"} & fired
    # Liability composite consumes asset_deterioration + dewatering.
    assert results["liability"].score > 0


def test_low_confidence_when_evidence_missing(db: Session) -> None:
    # A borehole with no GWL, no labs, no translation -> salinity confidence should be low.
    project = Project(name="Sparse"); db.add(project); db.flush()
    bh = Borehole(project_id=project.id, bh_ref="BH-X")
    db.add(bh); db.commit()
    results = {r.category: r for r in assess_borehole(RiskContext.from_borehole(bh, {}))}
    assert results["salinity"].score == 0
    assert results["salinity"].confidence_pct < 40   # little reliable evidence


def test_assess_project_persists_and_idempotent(db: Session) -> None:
    bh = _charter_borehole(db)
    n_categories = len(get_risk_rules().categories)

    counts = assess_project(db, bh.project_id); db.commit()
    assert counts == {"boreholes": 1, "risk_results": n_categories}
    assert db.scalar(select(func.count(RiskResult.id))) == n_categories

    # Provenance stamped.
    row = db.scalars(select(RiskResult).where(RiskResult.category == "rise")).one()
    assert row.engine_version and "app" in row.engine_version
    assert json.loads(row.evidence_json)

    # Re-running replaces rather than appends.
    assess_project(db, bh.project_id); db.commit()
    assert db.scalar(select(func.count(RiskResult.id))) == n_categories

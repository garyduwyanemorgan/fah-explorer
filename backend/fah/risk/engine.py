"""Risk engine — orchestrates the 10 category calculators per borehole and persists results.

For each borehole it builds a :class:`RiskContext`, evaluates every category (in dependency order
so composites can reference earlier levels), computes score + level + confidence + explanation, and
writes one ``RiskResult`` per (borehole × category) with provenance. Idempotent per project.
See docs/06.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from fah.config import get_settings
from fah.db.models import Borehole, Project, RiskResult
from fah.risk import calculators, confidence, explain
from fah.risk.context import RiskContext
from fah.risk.rules import RiskRules, get_risk_rules

logger = logging.getLogger("fah.risk.engine")


@dataclass
class CategoryResult:
    category: str
    label: str
    score: int
    level: str
    confidence_pct: int
    explanation: str
    evidence: list[dict[str, Any]] = field(default_factory=list)


def engine_version(rules: RiskRules) -> str:
    return f"{rules.version}+app{get_settings().version}"


def assess_borehole(ctx: RiskContext, rules: RiskRules | None = None) -> list[CategoryResult]:
    """Run every category for one borehole. Returns results in rule order."""
    rules = rules or get_risk_rules()
    prior_levels: dict[str, str] = {}
    results: list[CategoryResult] = []

    for cat in rules.categories:
        conf_pct, reliabilities = confidence.category_confidence(
            cat.factors, ctx, prior_levels, rules
        )
        score = 0
        evidence: list[dict[str, Any]] = []
        fired: list[dict[str, Any]] = []
        for f in cat.factors:
            did_fire = calculators.evaluate(f.cond, ctx, prior_levels)
            value = calculators.explain_value(f.cond, ctx) if did_fire else None
            rec = {
                "id": f.id,
                "fired": did_fire,
                "points": f.points,
                "evidence": f.evidence,
                "reliability": reliabilities[f.id],
                "value": value,
            }
            evidence.append(rec)
            if did_fire:
                score += f.points
                fired.append(rec)
        score = min(score, 100)
        level = rules.level_for(score)
        prior_levels[cat.key] = level

        results.append(
            CategoryResult(
                category=cat.key,
                label=cat.label,
                score=score,
                level=level,
                confidence_pct=conf_pct,
                explanation=explain.build_explanation(cat.label, score, level, conf_pct, fired),
                evidence=evidence,
            )
        )
    return results


def assess_project(
    db: Session, project_id: int, site: dict[str, Any] | None = None, rules: RiskRules | None = None
) -> dict[str, int]:
    """Score every borehole in a project and persist results. Idempotent (replaces prior rows)."""
    rules = rules or get_risk_rules()
    project = db.get(Project, project_id)
    if project is None:
        raise ValueError(f"Project {project_id} not found")

    version = engine_version(rules)
    boreholes = list(db.scalars(select(Borehole).where(Borehole.project_id == project_id)))
    total = 0

    for bh in boreholes:
        # Idempotent replace.
        for old in db.scalars(select(RiskResult).where(RiskResult.borehole_id == bh.id)).all():
            db.delete(old)
        db.flush()

        ctx = RiskContext.from_borehole(bh, site)
        for cr in assess_borehole(ctx, rules):
            db.add(
                RiskResult(
                    borehole_id=bh.id,
                    category=cr.category,
                    score=cr.score,
                    level=cr.level,
                    confidence_pct=cr.confidence_pct,
                    explanation=cr.explanation,
                    evidence_json=json.dumps(cr.evidence),
                    engine_version=version,
                )
            )
            total += 1
        db.flush()
        logger.info("Assessed borehole %s: %d categories", bh.bh_ref, len(rules.categories))

    return {"boreholes": len(boreholes), "risk_results": total}

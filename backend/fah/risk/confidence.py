"""Confidence scoring — how much reliable evidence backed a category's assessment.

Confidence = importance-weighted mean of each factor's evidence reliability, over ALL factors in
the category (not just those that fired). A category assessed from measured inputs scores high even
when the outcome is "Low"; one leaning on absent inputs scores low. See docs/06.
"""

from __future__ import annotations

from fah.risk.context import RiskContext
from fah.risk.rules import Factor, RiskRules


def reliability(evidence: str, ctx: RiskContext, prior_levels: dict[str, str]) -> str:
    """Classify the reliability of a factor's evidence: measured | inferred | default | missing."""
    if evidence == "gwl":
        return "measured" if ctx.gwl_depth_m is not None else "missing"
    if evidence == "ground_level":
        return "measured" if ctx.ground_level_m is not None else "missing"
    if evidence in ("hydro", "litho", "anisotropy"):
        return "inferred" if ctx.has_subsurface_model else "missing"
    if evidence.startswith("lab:"):
        return "measured" if ctx.lab(evidence.split(":", 1)[1]) is not None else "missing"
    if evidence.startswith("site:"):
        # Knowing the value (true or false) counts as evidence; absence is a gap.
        return "measured" if evidence.split(":", 1)[1] in ctx.site else "missing"
    if evidence.startswith("risk:"):
        return "inferred" if evidence.split(":", 1)[1] in prior_levels else "missing"
    return "default"


def category_confidence(
    factors: tuple[Factor, ...],
    ctx: RiskContext,
    prior_levels: dict[str, str],
    rules: RiskRules,
) -> tuple[int, dict[str, str]]:
    """Return (confidence_pct, {factor_id: reliability})."""
    weights = rules.confidence_weights
    num = 0.0
    den = 0.0
    per_factor: dict[str, str] = {}
    for f in factors:
        rel = reliability(f.evidence, ctx, prior_levels)
        per_factor[f.id] = rel
        num += f.importance * weights.get(rel, 0.0)
        den += f.importance
    pct = round(100 * num / den) if den else 0
    return pct, per_factor

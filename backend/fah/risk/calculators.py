"""Condition evaluation for risk factors.

Conditions are structured dicts (see config/risk_rules.yaml). This module evaluates them against a
:class:`RiskContext` and the already-computed levels of other categories (for composites). It is a
small, closed, safe interpreter — no ``eval``.
"""

from __future__ import annotations

from typing import Any, Callable

from fah.risk.context import RiskContext

_NUMERIC_OPS: dict[str, Callable[[float, float], bool]] = {
    "lt": lambda a, b: a < b,
    "le": lambda a, b: a <= b,
    "gt": lambda a, b: a > b,
    "ge": lambda a, b: a >= b,
    "eq": lambda a, b: a == b,
}


def _cmp(value: float | None, op: str, target: float) -> bool:
    if value is None:
        return False
    return _NUMERIC_OPS[op](value, target)


def evaluate(cond: dict[str, Any], ctx: RiskContext, prior_levels: dict[str, str]) -> bool:
    """Evaluate one condition. Returns True if the factor fires."""
    # Boolean combinators
    if "any" in cond:
        return any(evaluate(c, ctx, prior_levels) for c in cond["any"])
    if "all" in cond:
        return all(evaluate(c, ctx, prior_levels) for c in cond["all"])

    # Numeric variable comparison
    if "var" in cond:
        value = ctx.numeric_var(cond["var"])
        if cond["op"] == "between":
            return value is not None and cond["min"] <= value <= cond["max"]
        return _cmp(value, cond["op"], cond["value"])

    # Lithology / unit-type membership
    if "fn" in cond:
        if cond["fn"] == "has_lithology":
            return ctx.has_lithology(cond["arg"])
        if cond["fn"] == "has_unit_type":
            return ctx.has_unit_type(cond["arg"])
        raise ValueError(f"Unknown fn in risk rules: {cond['fn']}")

    # Lab parameter comparison
    if "lab" in cond:
        value = ctx.lab(cond["lab"])
        if cond["op"] == "between":
            return value is not None and cond["min"] <= value <= cond["max"]
        return _cmp(value, cond["op"], cond["value"])

    # Site metadata flag (truthy)
    if "site" in cond:
        return bool(ctx.site.get(cond["site"]))

    # Derived boolean signal
    if "flag" in cond:
        return bool(getattr(ctx, cond["flag"]))

    # Composite: depends on another category's level
    if "risk" in cond:
        return prior_levels.get(cond["risk"]) in set(cond["level_in"])

    raise ValueError(f"Unrecognised condition: {cond}")


def explain_value(cond: dict[str, Any], ctx: RiskContext) -> Any:
    """Best-effort value to show in the explanation for a fired factor."""
    if "var" in cond:
        return ctx.numeric_var(cond["var"])
    if "lab" in cond:
        return ctx.lab(cond["lab"])
    if "fn" in cond:
        return cond.get("arg")
    return None

"""Loader for the externalised risk rules (config/risk_rules.yaml)."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

import yaml

from fah.config import get_settings

logger = logging.getLogger("fah.risk.rules")


@dataclass(frozen=True)
class Factor:
    id: str
    points: int
    importance: int
    evidence: str
    cond: dict[str, Any]


@dataclass(frozen=True)
class Category:
    key: str
    label: str
    factors: tuple[Factor, ...]


@dataclass(frozen=True)
class RiskRules:
    version: str
    levels: list[dict[str, Any]]            # [{max, level}], ascending
    confidence_weights: dict[str, float]
    categories: tuple[Category, ...]        # in dependency order

    def level_for(self, score: int) -> str:
        for band in self.levels:
            if score <= band["max"]:
                return band["level"]
        return self.levels[-1]["level"]


@lru_cache(maxsize=1)
def get_risk_rules() -> RiskRules:
    with get_settings().rules_risk.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}

    categories = tuple(
        Category(
            key=key,
            label=spec.get("label", key),
            factors=tuple(
                Factor(
                    id=f["id"],
                    points=int(f["points"]),
                    importance=int(f["importance"]),
                    evidence=str(f["evidence"]),
                    cond=f["cond"],
                )
                for f in spec.get("factors", [])
            ),
        )
        for key, spec in data.get("categories", {}).items()
    )

    rules = RiskRules(
        version=data.get("version", "rules-?"),
        levels=data.get("levels", []),
        confidence_weights=data.get("confidence_weights", {}),
        categories=categories,
    )
    logger.info("Loaded risk rules %s (%d categories)", rules.version, len(rules.categories))
    return rules

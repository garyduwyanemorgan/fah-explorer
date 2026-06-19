"""Stage A — lithology normalisation.

Free-text soil descriptions → canonical lithology code + modifiers (density, cementation,
moisture, salinity). Deterministic and provenance-carrying. See docs/05 (Stage A).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from fah.translate.rules import TranslationRules, get_rules

logger = logging.getLogger("fah.translate.lithology")

# Order matters: check multi-word/qualified terms before their substrings.
_DENSITY_KEYWORDS: tuple[tuple[str, str], ...] = (
    ("very loose", "very_loose"),
    ("very dense", "very_dense"),
    ("medium dense", "medium_dense"),
    ("loose", "loose"),
    ("dense", "dense"),
)
_CEMENT_KEYWORDS: tuple[str, ...] = ("cemented", "cementation", "indurated")
_MOISTURE_KEYWORDS: tuple[str, ...] = ("saturated", "wet", "moist", "damp", "dry")


@dataclass
class LithologyMatch:
    code: str | None                 # canonical lithology code, or None if unmatched
    canonical_name: str
    is_cemented: bool                # final (keyword OR lithology default)
    cementation_extra: bool          # cementation described beyond the base lithology
    density: str | None
    moisture: str | None
    salinity_flag: bool
    rules_applied: list[str] = field(default_factory=list)
    matched_synonym: str | None = None


def _detect_density(text: str, spt_n: int | None, rules: TranslationRules) -> tuple[str | None, str]:
    for kw, value in _DENSITY_KEYWORDS:
        if kw in text:
            return value, f"density.keyword:{value}"
    if spt_n is not None:
        d = rules.spt_density(spt_n)
        if d:
            return d, f"density.spt_n:{spt_n}->{d}"
    return None, "density.none"


def _match_lithology(text: str, rules: TranslationRules) -> tuple[str | None, str | None]:
    """Match by the longest synonym found in the text (most specific wins)."""
    best_code: str | None = None
    best_syn: str | None = None
    best_len = 0
    for code, spec in rules.lithologies.items():
        for syn in spec.get("synonyms", []):
            if syn in text and len(syn) > best_len:
                best_code, best_syn, best_len = code, syn, len(syn)
    return best_code, best_syn


def normalise(
    description: str | None, spt_n: int | None = None, rules: TranslationRules | None = None
) -> LithologyMatch:
    rules = rules or get_rules()
    text = (description or "").lower()

    code, syn = _match_lithology(text, rules)
    spec = rules.lithologies.get(code, {}) if code else {}

    density, density_rule = _detect_density(text, spt_n, rules)
    keyword_cemented = any(k in text for k in _CEMENT_KEYWORDS)
    base_cemented = bool(spec.get("cemented_default", False))
    cementation_extra = keyword_cemented and not base_cemented
    is_cemented = keyword_cemented or base_cemented
    moisture = next((m for m in _MOISTURE_KEYWORDS if m in text), None)

    applied = [f"litho.{code}" if code else "litho.unknown", density_rule]
    if cementation_extra:
        applied.append("modifier.cemented")

    return LithologyMatch(
        code=code,
        canonical_name=spec.get("canonical_name", "Unknown") if code else "Unknown",
        is_cemented=is_cemented,
        cementation_extra=cementation_extra,
        density=density,
        moisture=moisture,
        salinity_flag=bool(spec.get("salinity_flag", False)),
        rules_applied=applied,
        matched_synonym=syn,
    )

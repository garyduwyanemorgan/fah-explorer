"""Loader + helpers for the externalised translation rules (config/translation_rules.yaml).

Keeps the IP in YAML and out of code. Provides band arithmetic (rank, shift, numeric value)
used by the hydraulic stage. See docs/05_HYDROSTRATIGRAPHIC_TRANSLATION.md.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from fah.config import get_settings

logger = logging.getLogger("fah.translate.rules")

# Conductivity bands ordered from lowest to highest K.
BAND_ORDER: tuple[str, ...] = ("very_low", "low", "moderate", "high", "very_high")


@dataclass(frozen=True)
class TranslationRules:
    version: str
    k_bands: dict[str, list[float]]
    lithologies: dict[str, dict[str, Any]]
    density_modifiers: dict[str, dict[str, Any]]
    cementation_modifier: dict[str, Any]
    spt_to_density: list[dict[str, Any]]
    hydrostratigraphy: dict[str, Any]

    # --- band arithmetic ---
    def band_rank(self, band: str) -> int:
        return BAND_ORDER.index(band)

    def shift_band(self, band: str, n: int) -> str:
        """Shift a band by n steps (positive = higher K), clamped to the range."""
        idx = max(0, min(len(BAND_ORDER) - 1, self.band_rank(band) + n))
        return BAND_ORDER[idx]

    def band_numeric(self, band: str) -> float:
        """Representative K (m/day) = geometric mean of the band's range."""
        lo, hi = self.k_bands[band]
        return math.sqrt(lo * hi)

    def band_at_least(self, band: str, threshold: str) -> bool:
        return self.band_rank(band) >= self.band_rank(threshold)

    def spt_density(self, spt_n: int) -> str | None:
        """Map an SPT-N value to a density class via the configured buckets."""
        for bucket in self.spt_to_density:
            if spt_n <= bucket["max_n"]:
                return bucket["density"]
        return None


def _load(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


@lru_cache(maxsize=1)
def get_rules() -> TranslationRules:
    data = _load(get_settings().rules_translation)
    modifiers = data.get("modifiers", {})
    rules = TranslationRules(
        version=data.get("version", "rules-?"),
        k_bands=data.get("k_bands", {}),
        lithologies=data.get("lithologies", {}),
        density_modifiers=modifiers.get("density", {}),
        cementation_modifier=modifiers.get("cementation", {}).get("cemented", {}),
        spt_to_density=modifiers.get("spt_n_to_density", []),
        hydrostratigraphy=data.get("hydrostratigraphy", {}),
    )
    logger.info(
        "Loaded translation rules %s (%d lithologies)", rules.version, len(rules.lithologies)
    )
    return rules

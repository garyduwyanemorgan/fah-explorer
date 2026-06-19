"""Stage B — hydraulic property assignment.

A normalised lithology + modifiers → (K_h, K_v, anisotropy, storage, perching flag), in both
qualitative bands and representative numeric m/day. See docs/05 (Stage B).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from fah.translate.lithology import LithologyMatch
from fah.translate.rules import TranslationRules, get_rules

# Fallback bands when the lithology is unknown (conservative, flagged as a default).
_UNKNOWN_K_H = "moderate"
_UNKNOWN_K_V = "moderate"
_UNKNOWN_STORAGE = "moderate"


@dataclass
class HydraulicProps:
    k_h_band: str
    k_v_band: str
    k_h_m_day: float
    k_v_m_day: float
    anisotropy: float
    storage_class: str
    perching_flag: bool
    rules_applied: list[str] = field(default_factory=list)
    defaults_used: list[str] = field(default_factory=list)


def assign(match: LithologyMatch, rules: TranslationRules | None = None) -> HydraulicProps:
    rules = rules or get_rules()
    applied: list[str] = []
    defaults: list[str] = []

    spec = rules.lithologies.get(match.code, {}) if match.code else {}
    if not spec:
        k_h_band, k_v_band, storage = _UNKNOWN_K_H, _UNKNOWN_K_V, _UNKNOWN_STORAGE
        defaults.append("unknown_lithology_defaults")
    else:
        k_h_band = spec.get("k_h", _UNKNOWN_K_H)
        k_v_band = spec.get("k_v", _UNKNOWN_K_V)
        storage = spec.get("storage", _UNKNOWN_STORAGE)

    # Density modifier — shifts both K bands equally (preserves base anisotropy).
    if match.density and match.density in rules.density_modifiers:
        shift = int(rules.density_modifiers[match.density].get("k_shift", 0))
        if shift:
            k_h_band = rules.shift_band(k_h_band, shift)
            k_v_band = rules.shift_band(k_v_band, shift)
            applied.append(f"density.{match.density}.k_shift={shift:+d}")

    # Cementation — extra vertical-K suppression only when described beyond the base lithology.
    perching_flag = str(spec.get("perching_potential", "low")) == "high"
    if match.cementation_extra:
        kv_shift = int(rules.cementation_modifier.get("k_v_shift", 0))
        if kv_shift:
            k_v_band = rules.shift_band(k_v_band, kv_shift)
            applied.append(f"cementation.k_v_shift={kv_shift:+d}")
        if rules.cementation_modifier.get("set_perching"):
            perching_flag = True
            applied.append("cementation.set_perching")

    k_h = rules.band_numeric(k_h_band)
    k_v = rules.band_numeric(k_v_band)
    anisotropy = k_h / k_v if k_v > 0 else float("inf")

    return HydraulicProps(
        k_h_band=k_h_band,
        k_v_band=k_v_band,
        k_h_m_day=round(k_h, 5),
        k_v_m_day=round(k_v, 5),
        anisotropy=round(anisotropy, 3),
        storage_class=storage,
        perching_flag=perching_flag,
        rules_applied=applied,
        defaults_used=defaults,
    )

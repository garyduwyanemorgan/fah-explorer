"""Stage C — hydrostratigraphic classification.

Each layer's lithology + hydraulic properties → a hydro-unit type
(aquifer / aquitard / barrier / perching_layer). Priority order is explicit and provenance is
recorded. See docs/05 (Stage C).
"""

from __future__ import annotations

from fah.translate.hydraulic import HydraulicProps
from fah.translate.lithology import LithologyMatch
from fah.translate.rules import TranslationRules, get_rules


def classify(
    match: LithologyMatch, hyd: HydraulicProps, rules: TranslationRules | None = None
) -> tuple[str, str]:
    """Return (unit_type, rule_id). Priority is barrier > aquitard(litho) > perching > aquitard(K) > aquifer."""
    rules = rules or get_rules()
    spec = rules.lithologies.get(match.code, {}) if match.code else {}
    hs = rules.hydrostratigraphy

    barrier_max_kv = hs.get("barrier_max_k_v", "very_low")
    aquitard_max_kv = hs.get("aquitard_max_k_v", "low")
    aquifer_min_kh = hs.get("aquifer_min_k_h", "moderate")

    # 1. Explicit barrier lithology (laterally continuous very-low-K, e.g. calcisiltite).
    if spec.get("is_barrier"):
        return "barrier", "hydrostrat.barrier_lithology"
    # 2. Explicit aquitard lithology (e.g. clay/silt).
    if spec.get("is_aquitard"):
        return "aquitard", "hydrostrat.aquitard_lithology"
    # 3. Perching layer: perching flag + low vertical K.
    if hyd.perching_flag and rules.band_rank(hyd.k_v_band) <= rules.band_rank(aquitard_max_kv):
        return "perching_layer", "hydrostrat.perching_low_kv"
    # 4. Very-low vertical K with no perching role -> barrier.
    if rules.band_rank(hyd.k_v_band) <= rules.band_rank(barrier_max_kv):
        return "barrier", "hydrostrat.very_low_kv"
    # 5. Low vertical K -> aquitard.
    if rules.band_rank(hyd.k_v_band) <= rules.band_rank(aquitard_max_kv):
        return "aquitard", "hydrostrat.low_kv"
    # 6. Sufficiently transmissive -> aquifer.
    if rules.band_at_least(hyd.k_h_band, aquifer_min_kh):
        return "aquifer", "hydrostrat.transmissive"
    return "aquitard", "hydrostrat.default"

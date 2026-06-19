"""Per-borehole input context for the risk engine.

Assembles the borehole, its layers, derived hydro-units, lab results, and optional site metadata,
and exposes the derived signals the rule conditions reference (e.g. ``cemented_or_lowkv_above_m``,
``max_anisotropy``, ``salinity_source``). Pure / DB-free so it is trivially testable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from fah.db.models import Borehole, HydroUnit, LabResult, Layer

_LOW_KV_UNITS = {"barrier", "perching_layer"}


@dataclass
class RiskContext:
    borehole_ref: str
    gwl_depth_m: float | None
    ground_level_m: float | None
    layers: list[Layer] = field(default_factory=list)
    hydro_units: list[HydroUnit] = field(default_factory=list)
    lab_results: list[LabResult] = field(default_factory=list)
    site: dict[str, Any] = field(default_factory=dict)

    # --- constructors ---
    @classmethod
    def from_borehole(cls, bh: Borehole, site: dict[str, Any] | None = None) -> "RiskContext":
        return cls(
            borehole_ref=bh.bh_ref,
            gwl_depth_m=bh.gwl_depth_m,
            ground_level_m=bh.ground_level_m,
            layers=list(bh.layers),
            hydro_units=list(bh.hydro_units),
            lab_results=list(bh.lab_results),
            site=dict(site or {}),
        )

    # --- helpers used by conditions ---
    def has_lithology(self, code: str) -> bool:
        return any((l.lithology_code or "") == code for l in self.layers)

    def has_unit_type(self, unit_type: str) -> bool:
        return any(u.unit_type == unit_type for u in self.hydro_units)

    def lab(self, parameter: str) -> float | None:
        """Most conservative (max) value for a parameter, case-insensitive."""
        vals = [
            r.value for r in self.lab_results
            if r.value is not None and (r.parameter or "").lower() == parameter.lower()
        ]
        return max(vals) if vals else None

    @property
    def has_subsurface_model(self) -> bool:
        return bool(self.hydro_units or self.layers)

    @property
    def max_anisotropy(self) -> float | None:
        vals = [u.anisotropy for u in self.hydro_units if u.anisotropy is not None]
        return max(vals) if vals else None

    @property
    def cemented_or_lowkv_above_m(self) -> float | None:
        """Shallowest depth (m) to a cemented layer or a low-K_v hydro-unit."""
        tops = [l.top_depth_m for l in self.layers if l.is_cemented]
        tops += [u.top_depth_m for u in self.hydro_units if u.unit_type in _LOW_KV_UNITS]
        return min(tops) if tops else None

    @property
    def surface_k_v(self) -> float | None:
        """Vertical K of the shallowest hydro-unit (proxy for surface permeability)."""
        if not self.hydro_units:
            return None
        top_unit = min(self.hydro_units, key=lambda u: u.top_depth_m)
        return top_unit.k_v_m_day

    @property
    def lowkv_unit_below_highk(self) -> bool:
        """An aquifer overlying a low-K_v unit (mounding/perching geometry)."""
        aquifers = [u for u in self.hydro_units if u.unit_type == "aquifer"]
        lowkv = [u for u in self.hydro_units if u.unit_type in _LOW_KV_UNITS or u.unit_type == "aquitard"]
        return any(a.bottom_depth_m <= u.top_depth_m + 1e-6 for a in aquifers for u in lowkv)

    # Same geometric signal, named for the perching factor.
    highk_over_lowkv = lowkv_unit_below_highk

    @property
    def salinity_source(self) -> bool:
        if self.has_lithology("sabkha"):
            return True
        tds, cl = self.lab("tds"), self.lab("chloride")
        return (tds is not None and tds > 35000) or (cl is not None and cl > 5000)

    def numeric_var(self, name: str) -> float | None:
        """Resolve a named numeric variable used in {var,...} conditions."""
        if name == "gwl_depth_m":
            return self.gwl_depth_m
        if name == "ground_level_m":
            return self.ground_level_m
        if name == "max_anisotropy":
            return self.max_anisotropy
        if name == "cemented_or_lowkv_above_m":
            return self.cemented_or_lowkv_above_m
        if name == "surface_k_v":
            return self.surface_k_v
        raise KeyError(f"Unknown numeric variable in risk rules: {name}")

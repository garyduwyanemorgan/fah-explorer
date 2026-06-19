"""Strict extraction contracts (pydantic) + validation.

The LLM must return JSON matching :class:`ExtractedProject`. Hard structural errors (bad types,
non-monotonic depths, negative depths) are rejected by the models; softer concerns (layer
gaps/overlaps, missing or implausible coordinates) are surfaced as **warnings** for the human
reviewer rather than blocking. See docs/07_PDF_EXTRACTION_WORKFLOW.md (stages 3-4).
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field

from pydantic import BaseModel, Field, ValidationError, field_validator, model_validator


class ExtractedLab(BaseModel):
    depth_m: float | None = None
    parameter: str = Field(min_length=1)
    value: float | None = None
    unit: str | None = None


class ExtractedLayer(BaseModel):
    top_depth_m: float = Field(ge=0)
    bottom_depth_m: float = Field(gt=0)
    raw_description: str | None = None
    spt_n: int | None = Field(default=None, ge=0)
    moisture: str | None = None
    density_desc: str | None = None

    @model_validator(mode="after")
    def _depths_monotonic(self) -> "ExtractedLayer":
        if self.bottom_depth_m <= self.top_depth_m:
            raise ValueError(
                f"bottom_depth_m ({self.bottom_depth_m}) must be greater than "
                f"top_depth_m ({self.top_depth_m})"
            )
        return self


class ExtractedBorehole(BaseModel):
    bh_ref: str = Field(min_length=1)
    easting: float | None = None
    northing: float | None = None
    lon: float | None = None
    lat: float | None = None
    ground_level_m: float | None = None
    gwl_depth_m: float | None = None
    date_drilled: dt.date | None = None
    layers: list[ExtractedLayer] = Field(default_factory=list)
    lab_results: list[ExtractedLab] = Field(default_factory=list)


class ExtractedProject(BaseModel):
    name: str | None = None
    location: str | None = None
    developer: str | None = None
    report_date: dt.date | None = None
    crs: str | None = None
    boreholes: list[ExtractedBorehole] = Field(default_factory=list)

    @field_validator("boreholes")
    @classmethod
    def _at_least_one(cls, v: list[ExtractedBorehole]) -> list[ExtractedBorehole]:
        if not v:
            raise ValueError("extraction produced no boreholes")
        return v


@dataclass
class ExtractionValidation:
    """Outcome of validating an extraction payload."""

    ok: bool
    model: ExtractedProject | None = None
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


# Plausible bounds for UTM 40N (metres); used only to flag, never to block.
_EASTING_RANGE = (100_000.0, 900_000.0)
_NORTHING_RANGE = (0.0, 10_000_000.0)


def _coordinate_warnings(bh: ExtractedBorehole) -> list[str]:
    out: list[str] = []
    has_utm = bh.easting is not None and bh.northing is not None
    has_lonlat = bh.lon is not None and bh.lat is not None
    if not has_utm and not has_lonlat:
        out.append(f"{bh.bh_ref}: no coordinates extracted")
        return out
    if has_utm:
        if not (_EASTING_RANGE[0] <= bh.easting <= _EASTING_RANGE[1]):  # type: ignore[operator]
            out.append(f"{bh.bh_ref}: easting {bh.easting} outside plausible UTM range")
        if not (_NORTHING_RANGE[0] <= bh.northing <= _NORTHING_RANGE[1]):  # type: ignore[operator]
            out.append(f"{bh.bh_ref}: northing {bh.northing} outside plausible UTM range")
    return out


def _layer_warnings(bh: ExtractedBorehole) -> list[str]:
    out: list[str] = []
    ordered = sorted(bh.layers, key=lambda x: x.top_depth_m)
    for prev, nxt in zip(ordered, ordered[1:]):
        if abs(nxt.top_depth_m - prev.bottom_depth_m) > 1e-6:
            kind = "gap" if nxt.top_depth_m > prev.bottom_depth_m else "overlap"
            out.append(
                f"{bh.bh_ref}: stratigraphy {kind} between {prev.bottom_depth_m} m and "
                f"{nxt.top_depth_m} m"
            )
    return out


def validate_payload(data: dict) -> ExtractionValidation:
    """Validate a raw extraction dict. Returns a structured report (never raises)."""
    try:
        model = ExtractedProject.model_validate(data)
    except ValidationError as exc:
        errors = [
            f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in exc.errors()
        ]
        return ExtractionValidation(ok=False, errors=errors)

    warnings: list[str] = []
    for bh in model.boreholes:
        warnings.extend(_coordinate_warnings(bh))
        warnings.extend(_layer_warnings(bh))
    return ExtractionValidation(ok=True, model=model, warnings=warnings)

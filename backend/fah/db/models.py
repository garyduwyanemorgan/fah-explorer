"""SQLAlchemy ORM models — the full FAH Explorer schema (see docs/04_DATABASE_SCHEMA.md).

SQLite for the MVP; the schema is PostGIS-ready (geometry stored as numeric lon/lat now). Every
*derived* row carries provenance so risk scores are traceable back to the raw report.
"""

from __future__ import annotations

import datetime as dt
from typing import Optional

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Declarative base for all FAH models."""


# Controlled vocabularies (kept as module constants; stored as TEXT for SQLite simplicity).
RISK_CATEGORIES: tuple[str, ...] = (
    "rise",
    "mounding",
    "perching",
    "salinity",
    "sulphate",
    "chloride",
    "asset_deterioration",
    "flood",
    "dewatering",
    "liability",
)
RISK_LEVELS: tuple[str, ...] = ("low", "moderate", "high", "critical")
HYDRO_UNIT_TYPES: tuple[str, ...] = ("aquifer", "aquitard", "barrier", "perching_layer")
EXTRACTION_STATUSES: tuple[str, ...] = (
    "pending",
    "extracted",
    "reviewed",
    "committed",
    "rejected",
)


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    location: Mapped[Optional[str]] = mapped_column(String(255))
    developer: Mapped[Optional[str]] = mapped_column(String(255))
    report_date: Mapped[Optional[dt.date]] = mapped_column(Date)
    crs_input: Mapped[Optional[str]] = mapped_column(String(32))
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, server_default=func.now())

    source_documents: Mapped[list["SourceDocument"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    boreholes: Mapped[list["Borehole"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )


class SourceDocument(Base):
    """Provenance / chain of custody for an uploaded report."""

    __tablename__ = "source_documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    filename: Mapped[str] = mapped_column(String(512))
    file_hash: Mapped[str] = mapped_column(String(64), index=True)  # sha256 hex
    page_count: Mapped[Optional[int]] = mapped_column(Integer)
    upload_at: Mapped[dt.datetime] = mapped_column(DateTime, server_default=func.now())
    ocr_used: Mapped[bool] = mapped_column(Boolean, default=False)
    extraction_status: Mapped[str] = mapped_column(String(16), default="pending")
    stored_path: Mapped[Optional[str]] = mapped_column(String(1024))

    project: Mapped["Project"] = relationship(back_populates="source_documents")
    extraction_records: Mapped[list["ExtractionRecord"]] = relationship(
        back_populates="source_document", cascade="all, delete-orphan"
    )


class Borehole(Base):
    __tablename__ = "boreholes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    bh_ref: Mapped[str] = mapped_column(String(64))
    easting: Mapped[Optional[float]] = mapped_column(Float)   # source UTM
    northing: Mapped[Optional[float]] = mapped_column(Float)
    lon: Mapped[Optional[float]] = mapped_column(Float)        # WGS84 (reprojected)
    lat: Mapped[Optional[float]] = mapped_column(Float)
    ground_level_m: Mapped[Optional[float]] = mapped_column(Float)
    gwl_depth_m: Mapped[Optional[float]] = mapped_column(Float)
    gwl_elevation_m: Mapped[Optional[float]] = mapped_column(Float)
    date_drilled: Mapped[Optional[dt.date]] = mapped_column(Date)

    project: Mapped["Project"] = relationship(back_populates="boreholes")
    layers: Mapped[list["Layer"]] = relationship(
        back_populates="borehole", cascade="all, delete-orphan", order_by="Layer.seq"
    )
    lab_results: Mapped[list["LabResult"]] = relationship(
        back_populates="borehole", cascade="all, delete-orphan"
    )
    hydro_units: Mapped[list["HydroUnit"]] = relationship(
        back_populates="borehole", cascade="all, delete-orphan"
    )
    risk_results: Mapped[list["RiskResult"]] = relationship(
        back_populates="borehole", cascade="all, delete-orphan"
    )


class Layer(Base):
    """One described stratigraphic interval."""

    __tablename__ = "layers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    borehole_id: Mapped[int] = mapped_column(ForeignKey("boreholes.id", ondelete="CASCADE"))
    seq: Mapped[int] = mapped_column(Integer)
    top_depth_m: Mapped[float] = mapped_column(Float)
    bottom_depth_m: Mapped[float] = mapped_column(Float)
    raw_description: Mapped[Optional[str]] = mapped_column(Text)
    lithology_code: Mapped[Optional[str]] = mapped_column(String(64))
    spt_n: Mapped[Optional[int]] = mapped_column(Integer)
    moisture: Mapped[Optional[str]] = mapped_column(String(32))
    density_desc: Mapped[Optional[str]] = mapped_column(String(32))
    is_cemented: Mapped[bool] = mapped_column(Boolean, default=False)

    borehole: Mapped["Borehole"] = relationship(back_populates="layers")
    lab_results: Mapped[list["LabResult"]] = relationship(back_populates="layer")


class LabResult(Base):
    __tablename__ = "lab_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    borehole_id: Mapped[int] = mapped_column(ForeignKey("boreholes.id", ondelete="CASCADE"))
    layer_id: Mapped[Optional[int]] = mapped_column(ForeignKey("layers.id", ondelete="SET NULL"))
    depth_m: Mapped[Optional[float]] = mapped_column(Float)
    parameter: Mapped[str] = mapped_column(String(64))  # chloride / sulphate / TDS / pH ...
    value: Mapped[Optional[float]] = mapped_column(Float)
    unit: Mapped[Optional[str]] = mapped_column(String(32))

    borehole: Mapped["Borehole"] = relationship(back_populates="lab_results")
    layer: Mapped[Optional["Layer"]] = relationship(back_populates="lab_results")


class HydroUnit(Base):
    """Derived hydrostratigraphy — output of the translation engine (Sprint 3)."""

    __tablename__ = "hydro_units"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    borehole_id: Mapped[int] = mapped_column(ForeignKey("boreholes.id", ondelete="CASCADE"))
    top_depth_m: Mapped[float] = mapped_column(Float)
    bottom_depth_m: Mapped[float] = mapped_column(Float)
    unit_type: Mapped[str] = mapped_column(String(32))  # aquifer/aquitard/barrier/perching_layer
    k_h_m_day: Mapped[Optional[float]] = mapped_column(Float)
    k_v_m_day: Mapped[Optional[float]] = mapped_column(Float)
    anisotropy: Mapped[Optional[float]] = mapped_column(Float)
    storage_class: Mapped[Optional[str]] = mapped_column(String(16))
    derived_from: Mapped[Optional[str]] = mapped_column(Text)  # JSON: source layer ids + rule ids

    borehole: Mapped["Borehole"] = relationship(back_populates="hydro_units")


class RiskResult(Base):
    """One scored, explained risk per (borehole × category) — Sprint 4."""

    __tablename__ = "risk_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    borehole_id: Mapped[int] = mapped_column(ForeignKey("boreholes.id", ondelete="CASCADE"))
    category: Mapped[str] = mapped_column(String(32))  # see RISK_CATEGORIES
    score: Mapped[int] = mapped_column(Integer)
    level: Mapped[str] = mapped_column(String(16))     # see RISK_LEVELS
    confidence_pct: Mapped[int] = mapped_column(Integer)
    explanation: Mapped[Optional[str]] = mapped_column(Text)
    evidence_json: Mapped[Optional[str]] = mapped_column(Text)
    engine_version: Mapped[Optional[str]] = mapped_column(String(64))
    computed_at: Mapped[dt.datetime] = mapped_column(DateTime, server_default=func.now())

    borehole: Mapped["Borehole"] = relationship(back_populates="risk_results")


class ExtractionRecord(Base):
    """Raw LLM output kept verbatim for audit / reproducibility (Sprint 2)."""

    __tablename__ = "extraction_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_document_id: Mapped[int] = mapped_column(
        ForeignKey("source_documents.id", ondelete="CASCADE")
    )
    raw_json: Mapped[Optional[str]] = mapped_column(Text)
    model: Mapped[Optional[str]] = mapped_column(String(64))
    prompt_version: Mapped[Optional[str]] = mapped_column(String(32))
    reviewed_by: Mapped[Optional[str]] = mapped_column(String(128))
    approved: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, server_default=func.now())

    source_document: Mapped["SourceDocument"] = relationship(
        back_populates="extraction_records"
    )


class LithologyDictionary(Base):
    """Reference / seed data — lithology defaults from translation_rules.yaml."""

    __tablename__ = "lithology_dictionary"

    code: Mapped[str] = mapped_column(String(64), primary_key=True)
    canonical_name: Mapped[str] = mapped_column(String(128))
    synonyms_json: Mapped[Optional[str]] = mapped_column(Text)
    default_k_h: Mapped[Optional[str]] = mapped_column(String(16))  # qualitative band
    default_k_v: Mapped[Optional[str]] = mapped_column(String(16))
    storage_class: Mapped[Optional[str]] = mapped_column(String(16))
    cemented_default: Mapped[bool] = mapped_column(Boolean, default=False)
    salinity_flag: Mapped[bool] = mapped_column(Boolean, default=False)

"""Pydantic request/response models for the API."""

from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, ConfigDict, Field


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    location: str | None = None
    developer: str | None = None
    report_date: dt.date | None = None
    crs_input: str | None = Field(default=None, description="e.g. EPSG:32640 (UTM 40N)")


class ProjectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    location: str | None
    developer: str | None
    report_date: dt.date | None
    crs_input: str | None
    created_at: dt.datetime


class ProjectSummary(ProjectOut):
    borehole_count: int = 0
    document_count: int = 0


class SourceDocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    filename: str
    file_hash: str
    page_count: int | None
    upload_at: dt.datetime
    ocr_used: bool
    extraction_status: str


class UploadResult(BaseModel):
    document: SourceDocumentOut
    pages_with_text: int
    pages_needing_ocr: list[int]
    ocr_available: bool
    warning: str | None = None


class ValidationReport(BaseModel):
    ok: bool
    errors: list[str] = []
    warnings: list[str] = []


class ExtractionView(BaseModel):
    """Side-by-side review payload: parsed JSON + validation + provenance."""

    document_id: int
    extraction_status: str
    model: str | None
    prompt_version: str | None
    approved: bool
    payload: dict
    validation: ValidationReport


class ApproveRequest(BaseModel):
    reviewed_by: str = Field(min_length=1)
    payload: dict | None = Field(
        default=None, description="Reviewer-corrected JSON; if omitted, the stored extraction is used."
    )


class CommitResult(BaseModel):
    document_id: int
    committed: bool
    boreholes: int
    layers: int
    lab_results: int

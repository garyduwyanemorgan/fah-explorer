"""PDF upload route — archive + hash + register, then extract text (Sprint 1 data spine).

Extraction into structured boreholes/layers happens in Sprint 2 behind the review gate; here we
only land, fingerprint, and read the document so it is ready for the LLM extractor.
"""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from fah.api.schemas import SourceDocumentOut, UploadResult
from fah.config import get_settings
from fah.db.models import Project, SourceDocument
from fah.db.session import get_db
from fah.ingest.pdf_reader import archive_upload, read_pdf

logger = logging.getLogger("fah.api.upload")
router = APIRouter(prefix="/projects", tags=["upload"])

_MAX_UPLOAD_BYTES = 50 * 1024 * 1024  # 50 MB


@router.post(
    "/{project_id}/upload",
    response_model=UploadResult,
    status_code=status.HTTP_201_CREATED,
)
async def upload_pdf(
    project_id: int, file: UploadFile, db: Session = Depends(get_db)
) -> UploadResult:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")

    if not (file.filename or "").lower().endswith(".pdf"):
        raise HTTPException(status_code=415, detail="Only PDF uploads are supported.")

    settings = get_settings()
    settings.ensure_dirs()

    # Stream to temp file with a hard size cap.
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        tmp_path = Path(tmp.name)

    try:
        written = 0
        with tmp_path.open("wb") as out:
            while True:
                chunk = await file.read(65_536)
                if not chunk:
                    break
                written += len(chunk)
                if written > _MAX_UPLOAD_BYTES:
                    raise HTTPException(
                        status_code=413,
                        detail=f"File exceeds the {_MAX_UPLOAD_BYTES // (1024*1024)} MB upload limit.",
                    )
                out.write(chunk)

        # Validate PDF magic bytes (%PDF).
        with tmp_path.open("rb") as f:
            magic = f.read(4)
        if magic != b"%PDF":
            raise HTTPException(status_code=415, detail="File is not a valid PDF (bad magic bytes).")

        stored_path, digest = archive_upload(tmp_path, settings.uploads_dir)
        result = read_pdf(
            stored_path, ocr_enabled=settings.ocr_enabled, ocr_language=settings.ocr_language
        )
    finally:
        tmp_path.unlink(missing_ok=True)

    doc = SourceDocument(
        project_id=project_id,
        filename=file.filename or stored_path.name,
        file_hash=digest,
        page_count=result.page_count,
        ocr_used=result.ocr_used,
        extraction_status="pending",   # LLM extraction has NOT run yet
        stored_path=str(stored_path),
    )
    db.add(doc)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="This PDF has already been uploaded to this project (duplicate content hash).",
        )
    db.refresh(doc)

    logger.info(
        "Uploaded %s (%d pages, ocr_used=%s) to project %d",
        doc.filename, result.page_count, result.ocr_used, project_id,
    )

    return UploadResult(
        document=SourceDocumentOut.model_validate(doc),
        pages_with_text=sum(1 for p in result.pages if p.text),
        pages_needing_ocr=result.pages_needing_ocr,
        ocr_available=result.ocr_available,
        warning=result.ocr_unavailable_warning,
    )

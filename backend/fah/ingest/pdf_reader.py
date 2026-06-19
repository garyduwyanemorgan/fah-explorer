"""PDF reading — archive + hash, then per-page text with a graceful OCR fallback.

Sprint 1 scope (see docs/07_PDF_EXTRACTION_WORKFLOW.md, stages 1-2):

* archive the raw upload immutably and compute its SHA-256,
* extract text per page with ``pdfplumber``,
* for pages with no extractable text (scanned), attempt OCR via Tesseract **if available**.

Per the code standards, the absence of the OCR engine never crashes a text-PDF; it is reported.
"""

from __future__ import annotations

import hashlib
import logging
import shutil
from dataclasses import dataclass, field
from pathlib import Path

import pdfplumber

logger = logging.getLogger("fah.ingest.pdf_reader")

_CHUNK = 1 << 20  # 1 MiB


@dataclass
class PageText:
    """Extracted text for a single page."""

    number: int          # 1-based
    text: str
    needs_ocr: bool      # page had no extractable text layer
    ocr_applied: bool    # OCR was run and produced this text


@dataclass
class PdfReadResult:
    """Outcome of reading a PDF."""

    pages: list[PageText] = field(default_factory=list)
    ocr_used: bool = False             # OCR successfully applied to ≥1 page
    ocr_available: bool = False        # OCR toolchain importable
    pages_needing_ocr: list[int] = field(default_factory=list)
    ocr_unavailable_warning: str | None = None

    @property
    def page_count(self) -> int:
        return len(self.pages)

    @property
    def full_text(self) -> str:
        return "\n\n".join(p.text for p in self.pages if p.text)


def sha256_file(path: Path) -> str:
    """Stream a SHA-256 of the file contents."""
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(_CHUNK), b""):
            h.update(chunk)
    return h.hexdigest()


def archive_upload(src: Path, uploads_dir: Path) -> tuple[Path, str]:
    """Copy an uploaded PDF into the immutable archive under its content hash.

    Returns ``(stored_path, sha256)``. The stored filename is ``<hash>_<originalname>`` so the
    archive is content-addressed yet human-recognisable. Re-uploading identical content is a no-op.
    """
    uploads_dir.mkdir(parents=True, exist_ok=True)
    digest = sha256_file(src)
    stored = uploads_dir / f"{digest[:16]}_{src.name}"
    if not stored.exists():
        shutil.copy2(src, stored)
        logger.info("Archived upload %s -> %s", src.name, stored.name)
    else:
        logger.info("Upload already archived (hash match): %s", stored.name)
    return stored, digest


def _ocr_available() -> bool:
    try:
        import pdf2image  # noqa: F401
        import pytesseract  # noqa: F401
    except Exception:  # pragma: no cover - import guard
        return False
    return True


def _ocr_page(pdf_path: Path, page_number: int, language: str) -> str:
    """OCR a single page (1-based). Assumes the OCR toolchain is importable."""
    import pdf2image
    import pytesseract

    images = pdf2image.convert_from_path(
        str(pdf_path), first_page=page_number, last_page=page_number
    )
    if not images:
        return ""
    return pytesseract.image_to_string(images[0], lang=language) or ""


def read_pdf(
    pdf_path: Path, *, ocr_enabled: bool = True, ocr_language: str = "eng"
) -> PdfReadResult:
    """Extract text from every page, applying OCR to text-less (scanned) pages when possible.

    A missing OCR toolchain does not raise: scanned pages are returned with empty text and the
    result flags them, with a clear, actionable warning pointing to the install docs.
    """
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    result = PdfReadResult(ocr_available=_ocr_available())

    with pdfplumber.open(str(pdf_path)) as pdf:
        for i, page in enumerate(pdf.pages, start=1):
            text = (page.extract_text() or "").strip()
            if text:
                result.pages.append(PageText(number=i, text=text, needs_ocr=False, ocr_applied=False))
                continue

            # No text layer -> candidate for OCR.
            result.pages_needing_ocr.append(i)
            if ocr_enabled and result.ocr_available:
                try:
                    ocr_text = _ocr_page(pdf_path, i, ocr_language).strip()
                    result.ocr_used = result.ocr_used or bool(ocr_text)
                    result.pages.append(
                        PageText(number=i, text=ocr_text, needs_ocr=True, ocr_applied=True)
                    )
                    continue
                except Exception as exc:  # pragma: no cover - runtime/env dependent
                    logger.warning("OCR failed on page %d of %s: %s", i, pdf_path.name, exc)
            result.pages.append(PageText(number=i, text="", needs_ocr=True, ocr_applied=False))

    if result.pages_needing_ocr and not (result.ocr_available and ocr_enabled):
        result.ocr_unavailable_warning = (
            f"{len(result.pages_needing_ocr)} page(s) have no text layer and require OCR, "
            "but the OCR toolchain (pytesseract + pdf2image + the Tesseract binary) is not "
            "available. Install it to extract scanned pages — see docs/07_PDF_EXTRACTION_WORKFLOW.md."
        )
        logger.warning(result.ocr_unavailable_warning)

    return result

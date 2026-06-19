"""Sprint 1 — archiving, hashing, and PDF text extraction."""

from __future__ import annotations

from pathlib import Path

import pytest

from fah.ingest.pdf_reader import archive_upload, read_pdf, sha256_file


def test_sha256_and_archive_idempotent(tmp_path: Path) -> None:
    src = tmp_path / "report.pdf"
    src.write_bytes(b"%PDF-1.4 fake content for hashing")
    uploads = tmp_path / "uploads"

    stored1, digest1 = archive_upload(src, uploads)
    assert stored1.exists()
    assert digest1 == sha256_file(src)
    assert digest1[:16] in stored1.name  # content-addressed

    # Re-archiving identical content is a no-op (same destination, same hash).
    stored2, digest2 = archive_upload(src, uploads)
    assert stored2 == stored1
    assert digest2 == digest1
    assert sum(1 for _ in uploads.iterdir()) == 1


def _make_text_pdf(path: Path) -> bool:
    """Create a one-page PDF with extractable text; return False if reportlab is unavailable."""
    try:
        from reportlab.pdfgen import canvas
    except Exception:
        return False
    c = canvas.Canvas(str(path))
    c.drawString(72, 720, "Borehole BH-01 groundwater depth 1.8 m")
    c.showPage()
    c.save()
    return True


def test_read_text_pdf(tmp_path: Path) -> None:
    pdf = tmp_path / "log.pdf"
    if not _make_text_pdf(pdf):
        pytest.skip("reportlab not installed; cannot generate a test PDF")

    result = read_pdf(pdf, ocr_enabled=True)
    assert result.page_count == 1
    assert "BH-01" in result.full_text
    assert result.pages_needing_ocr == []   # text PDF needs no OCR
    assert result.ocr_used is False


def test_read_pdf_missing_file(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        read_pdf(tmp_path / "nope.pdf")

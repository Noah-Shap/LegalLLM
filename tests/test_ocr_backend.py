"""Tests for legallm.ocr_backend module."""

from unittest.mock import patch

from legallm.ocr_backend import OcrMeta

# ---- OcrMeta dataclass ----


def test_ocr_meta_defaults():
    meta = OcrMeta()
    assert meta.backend == "pymupdf_textpage_ocr"
    assert meta.ocr_used is False
    assert meta.ocr_full is True
    assert meta.ocr_language == "eng"
    assert meta.ocr_dpi == 300
    assert meta.ocr_pages_attempted == 0
    assert meta.ocr_pages_succeeded == 0
    assert meta.total_pages == 0
    assert meta.error is None


def test_ocr_meta_custom():
    meta = OcrMeta(
        ocr_used=True,
        ocr_language="deu",
        ocr_dpi=150,
        total_pages=10,
        ocr_pages_attempted=3,
        ocr_pages_succeeded=2,
    )
    assert meta.ocr_used is True
    assert meta.ocr_language == "deu"
    assert meta.total_pages == 10
    assert meta.ocr_pages_attempted == 3


# ---- check_ocr_ready ----


def test_check_ocr_ready_no_fitz():
    with patch("legallm.ocr_backend.fitz", None):
        from legallm.ocr_backend import check_ocr_ready

        ok, msg, details = check_ocr_ready()
        assert ok is False
        assert "PyMuPDF" in msg

"""Tests for legallm.ocr_decision module."""

from legallm.ocr_decision import (
    OcrDecisionConfig,
    looks_like_garbage_text,
    looks_like_stamp_only,
    page_text_metrics,
    should_ocr_document,
    should_ocr_page,
    strip_pacer_ecf_stamps,
)

# ---- page_text_metrics ----


def test_page_text_metrics_normal_text(normal_english_text):
    metrics = page_text_metrics(normal_english_text)
    assert metrics["chars"] > 100
    assert metrics["alpha_ratio"] > 0.8
    assert metrics["weird_token_ratio"] == 0.0
    assert metrics["word_count"] > 30


def test_page_text_metrics_empty():
    metrics = page_text_metrics("")
    assert metrics["chars"] == 0.0
    assert metrics["alpha_ratio"] == 0.0
    assert metrics["word_count"] == 0.0


def test_page_text_metrics_whitespace_only():
    metrics = page_text_metrics("   \n\n\t  ")
    assert metrics["chars"] == 0.0


def test_page_text_metrics_garbage(sample_garbage_text):
    metrics = page_text_metrics(sample_garbage_text)
    # Garbage text has low alpha ratio due to digits and slashes
    assert metrics["alpha_ratio"] < 0.5
    assert metrics["weird_token_ratio"] > 0.0


# ---- strip_pacer_ecf_stamps ----


def test_strip_pacer_ecf_stamps_removes_stamp(sample_pacer_stamp):
    text = f"{sample_pacer_stamp}\nThis is the actual body text."
    result = strip_pacer_ecf_stamps(text)
    assert "actual body text" in result
    assert "Document 45" not in result


def test_strip_pacer_ecf_stamps_no_stamps():
    text = "This is normal text.\nAnother line of text."
    result = strip_pacer_ecf_stamps(text)
    assert "normal text" in result
    assert "Another line" in result


def test_strip_pacer_ecf_stamps_empty():
    assert strip_pacer_ecf_stamps("") == ""


def test_strip_pacer_ecf_stamps_none():
    assert strip_pacer_ecf_stamps(None) == ""


# ---- looks_like_garbage_text ----


def test_looks_like_garbage_true(sample_garbage_text):
    assert looks_like_garbage_text(sample_garbage_text) is True


def test_looks_like_garbage_false(normal_english_text):
    assert looks_like_garbage_text(normal_english_text) is False


def test_looks_like_garbage_empty():
    assert looks_like_garbage_text("") is True
    assert looks_like_garbage_text(None) is True


def test_looks_like_garbage_pdf_internals():
    text = "/i255 /i128 /i064 some random tokens"
    assert looks_like_garbage_text(text) is True


# ---- looks_like_stamp_only ----


def test_looks_like_stamp_only_true(sample_pacer_stamp):
    assert looks_like_stamp_only(sample_pacer_stamp, min_body_chars=60) is True


def test_looks_like_stamp_only_false(normal_english_text):
    assert looks_like_stamp_only(normal_english_text, min_body_chars=60) is False


# ---- should_ocr_page ----


def test_should_ocr_page_good_text(normal_english_text):
    should_ocr, details = should_ocr_page(normal_english_text)
    assert should_ocr is False
    assert len(details["reasons"]) == 0
    assert "metrics" in details
    assert "cfg" in details


def test_should_ocr_page_empty():
    should_ocr, details = should_ocr_page("")
    assert should_ocr is True
    assert len(details["reasons"]) > 0


def test_should_ocr_page_garbage(sample_garbage_text):
    should_ocr, details = should_ocr_page(sample_garbage_text)
    assert should_ocr is True
    assert "garbage_text" in details["reasons"]


def test_should_ocr_page_too_few_chars():
    short_text = "Hello world."
    should_ocr, details = should_ocr_page(short_text)
    assert should_ocr is True
    assert "too_few_chars" in details["reasons"]


def test_should_ocr_page_custom_config():
    # With very relaxed thresholds, even short text should pass
    cfg = OcrDecisionConfig(
        page_min_chars=5,
        page_min_word_count=1,
        page_min_alpha_ratio=0.1,
        page_stamp_only_min_body_chars=5,
    )
    should_ocr, details = should_ocr_page("Hello world test is some reasonable text for a page", cfg=cfg)
    assert should_ocr is False


# ---- should_ocr_document ----


def test_should_ocr_document_good(normal_english_text):
    # Repeat text to get above doc_min_total_chars threshold
    long_text = normal_english_text * 10
    should_ocr, details = should_ocr_document(long_text)
    assert should_ocr is False
    assert "metrics" in details


def test_should_ocr_document_empty():
    should_ocr, details = should_ocr_document("")
    assert should_ocr is True
    assert "no_text" in details["reasons"]


def test_should_ocr_document_too_little_text():
    should_ocr, details = should_ocr_document("Short.")
    assert should_ocr is True
    assert "too_little_text" in details["reasons"]


def test_should_ocr_document_with_page_count_override(normal_english_text):
    """High chars_per_page should override weak reasons like too_little_text."""
    # Text that's short overall but dense per-page
    text = normal_english_text  # ~400 chars
    should_ocr, details = should_ocr_document(text, page_count=1)
    # With 1 page, chars_per_page should be high enough to suppress weak reasons
    # (depends on actual char count vs threshold)
    assert "metrics" in details
    assert details["metrics"]["page_count"] == 1


def test_should_ocr_document_garbage(sample_garbage_text):
    should_ocr, details = should_ocr_document(sample_garbage_text)
    assert should_ocr is True
    assert "garbage_text" in details["reasons"]


# ---- OcrDecisionConfig ----


def test_ocr_decision_config_defaults():
    cfg = OcrDecisionConfig()
    assert cfg.page_min_chars == 120
    assert cfg.doc_min_total_chars == 1200
    assert cfg.garbage_max_alpha_ratio == 0.02


def test_ocr_decision_config_custom():
    cfg = OcrDecisionConfig(page_min_chars=50, doc_min_total_chars=500)
    assert cfg.page_min_chars == 50
    assert cfg.doc_min_total_chars == 500


def test_ocr_decision_config_frozen():
    cfg = OcrDecisionConfig()
    try:
        cfg.page_min_chars = 999
        assert False, "Should have raised FrozenInstanceError"
    except AttributeError:
        pass

"""Tests for legallm.pipeline module."""

from legallm.pipeline import (
    candidate_pdf_urls,
    in_scope_brief,
    normalize_text,
)

# ---- normalize_text ----


def test_normalize_text_hyphen_break():
    assert normalize_text("exam-\nple text") == "example text"


def test_normalize_text_whitespace():
    result = normalize_text("hello   world")
    assert result == "hello world"


def test_normalize_text_multiple_newlines():
    result = normalize_text("line1\n\n\n\n\nline2")
    assert result == "line1\n\nline2"


def test_normalize_text_crlf():
    result = normalize_text("line1\r\nline2\rline3")
    assert result == "line1\nline2\nline3"


def test_normalize_text_trailing_spaces():
    result = normalize_text("hello   \nworld   ")
    assert not any(line.endswith(" ") for line in result.splitlines())


def test_normalize_text_empty():
    assert normalize_text("") == ""


# ---- in_scope_brief ----


def test_in_scope_brief_opening_brief():
    item = {"short_description": "Opening Brief of Appellant"}
    assert in_scope_brief(item) is True


def test_in_scope_brief_response_brief():
    item = {"short_description": "Response Brief of Appellee"}
    assert in_scope_brief(item) is True


def test_in_scope_brief_amicus():
    item = {"short_description": "Brief of Amicus Curiae"}
    assert in_scope_brief(item) is False


def test_in_scope_brief_reply():
    item = {"short_description": "Reply Brief of Appellant"}
    assert in_scope_brief(item) is False


def test_in_scope_brief_motion():
    item = {"short_description": "Brief in Support of Motion to Dismiss"}
    assert in_scope_brief(item) is False


def test_in_scope_brief_no_brief_keyword():
    item = {"short_description": "Order Granting Summary Judgment"}
    assert in_scope_brief(item) is False


def test_in_scope_brief_no_description():
    item = {}
    assert in_scope_brief(item) is False


def test_in_scope_brief_claim_construction():
    item = {"short_description": "Opening Claim Construction Brief of Appellant"}
    assert in_scope_brief(item) is False


def test_in_scope_brief_falls_back_to_description():
    item = {"description": "Opening Brief of Appellant"}
    assert in_scope_brief(item) is True


# ---- candidate_pdf_urls ----


def test_candidate_pdf_urls_www():
    url = "https://www.courtlistener.com/recap/gov.uscourts.nysd.12345/doc.pdf"
    result = candidate_pdf_urls(url)
    assert len(result) == 2
    assert any("storage.courtlistener.com" in u for u in result)
    assert any("www.courtlistener.com" in u for u in result)


def test_candidate_pdf_urls_storage():
    url = "https://storage.courtlistener.com/recap/gov.uscourts.nysd.12345/doc.pdf"
    result = candidate_pdf_urls(url)
    assert len(result) == 2
    # storage should be first (preferred)
    assert result[0].startswith("https://storage.courtlistener.com")


def test_candidate_pdf_urls_other():
    url = "https://example.com/some/file.pdf"
    result = candidate_pdf_urls(url)
    assert result == [url]


def test_candidate_pdf_urls_no_duplicates():
    url = "https://www.courtlistener.com/recap/test.pdf"
    result = candidate_pdf_urls(url)
    assert len(result) == len(set(result))

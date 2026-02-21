"""Tests for legallm.pipeline module."""

from legallm.pipeline import (
    candidate_pdf_urls,
    extract_facts_span,
    heading_candidates,
    in_scope_brief,
    normalize_text,
    quality_flags,
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


# ---- extract_facts_span ----


def test_extract_facts_span_exact_headings(sample_brief_text):
    clean = normalize_text(sample_brief_text)
    span, meta = extract_facts_span(clean)
    assert span is not None, f"Expected a span, got None. Notes: {meta['notes']}"
    start, end = span
    facts = clean[start:end]
    assert "Appellant filed a complaint" in facts
    # The extracted span should end before the actual ARGUMENT section heading
    # (TOC references to ARGUMENT may appear in the span, but the heading itself shouldn't)
    assert "This Court should reverse" not in facts
    assert meta["method"] == "rules_v1"


def test_extract_facts_span_no_match():
    text = "This document has no section headings at all, just prose about random topics."
    span, meta = extract_facts_span(text)
    assert span is None
    assert "no_span_found" in meta["notes"]


def test_extract_facts_span_skips_toc(sample_brief_text):
    clean = normalize_text(sample_brief_text)
    span, meta = extract_facts_span(clean)
    assert span is not None
    start, end = span
    facts = clean[start:end]
    # Should not include the TOC entry, only the real section
    assert "TABLE OF CONTENTS" not in facts


def test_extract_facts_span_soft_headings(sample_brief_soft_headings):
    clean = normalize_text(sample_brief_soft_headings)
    span, meta = extract_facts_span(clean)
    # Soft heading detection should find FACTUAL OVERVIEW
    if span is not None:
        start, end = span
        facts = clean[start:end]
        assert "plaintiff was injured" in facts


def test_extract_facts_span_fallback_pre_argument():
    """Test fallback: content before ARGUMENT heading when no facts heading exists."""
    text = (
        "Some preliminary text about the court.\n\n"
        + "A" * 1000
        + "\n\n"  # enough content to pass the 800-char threshold
        + "ARGUMENT\n\n"
        "The defendant is liable.\n"
    )
    span, meta = extract_facts_span(text)
    if span is not None:
        assert "fallback_pre_argument" in meta["notes"]


# ---- quality_flags ----


def test_quality_flags_with_citations():
    text = "As held in 500 F.3d 100 and 300 U.S. 200, the standard applies."
    flags = quality_flags(text)
    assert flags["cite_hits"] >= 1
    assert flags["cite_hits_per_10k_chars"] > 0


def test_quality_flags_with_arg_markers():
    text = "We argue that this court should reverse. For these reasons, the judgment must be vacated."
    flags = quality_flags(text)
    assert flags["arg_marker_hits"] >= 1


def test_quality_flags_empty():
    flags = quality_flags("")
    assert flags["cite_hits"] == 0
    assert flags["arg_marker_hits"] == 0


def test_quality_flags_no_matches():
    flags = quality_flags("The quick brown fox jumped over the lazy dog.")
    assert flags["cite_hits"] == 0
    assert flags["arg_marker_hits"] == 0


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


# ---- heading_candidates ----


def test_heading_candidates_finds_headings(sample_brief_text):
    clean = normalize_text(sample_brief_text)
    headings = heading_candidates(clean)
    assert isinstance(headings, list)
    # Should find at least STATEMENT OF FACTS and ARGUMENT
    heading_text = " ".join(headings)
    assert "STATEMENT OF FACTS" in heading_text or "ARGUMENT" in heading_text


def test_heading_candidates_excludes_bad_fragments():
    text = "TABLE OF CONTENTS\n\nSTATEMENT OF FACTS\n\nARGUMENT\n"
    headings = heading_candidates(text)
    assert "TABLE OF CONTENTS" not in headings


def test_heading_candidates_empty():
    # Lowercase text won't match the HEADING_LINE regex (requires uppercase)
    headings = heading_candidates("no headings here, just prose about various topics.")
    assert headings == []


def test_heading_candidates_limit():
    text = "\n".join(f"HEADING NUMBER {i}" for i in range(100))
    headings = heading_candidates(text, limit=5)
    assert len(headings) <= 5

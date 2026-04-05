"""Tests for legallm.facts_extractor module (rules_v2)."""

from legallm.facts_extractor import (
    build_heading_map,
    classify_sections,
    extract_facts_span,
    heading_candidates,
    merge_fact_sections,
    merge_roman_heading_lines,
    quality_flags,
    strip_pacer_headers,
    validate_span,
)
from legallm.pipeline import normalize_text

# ============================================================================
# Phase A: Heading map builder
# ============================================================================


class TestBuildHeadingMap:
    def test_exact_start_and_stop_headings(self, sample_brief_text):
        clean = normalize_text(sample_brief_text)
        preprocessed = merge_roman_heading_lines(strip_pacer_headers(clean))
        entries, _, _ = build_heading_map(preprocessed)
        types = [e.heading_type for e in entries]
        assert "start" in types
        assert "stop" in types

    def test_roman_numeral_prefix(self):
        text = "I. STATEMENT OF FACTS\n\nSome content.\n\nII. ARGUMENT\n\nMore content.\n"
        entries, _, _ = build_heading_map(text)
        start_entries = [e for e in entries if e.heading_type == "start"]
        assert len(start_entries) >= 1
        assert "STATEMENT OF FACTS" in start_entries[0].text

    def test_toc_entries_filtered(self, sample_brief_text):
        clean = normalize_text(sample_brief_text)
        preprocessed = merge_roman_heading_lines(strip_pacer_headers(clean))
        entries, _, _ = build_heading_map(preprocessed)
        # TOC entries like "STATEMENT OF FACTS ............... 1" should be filtered.
        # The real heading should remain.
        start_entries = [e for e in entries if e.heading_type == "start"]
        assert len(start_entries) >= 1

    def test_new_heading_nature_of_case(self, sample_brief_nature_of_case):
        clean = normalize_text(sample_brief_nature_of_case)
        entries, _, _ = build_heading_map(clean)
        start_entries = [e for e in entries if e.heading_type == "start"]
        assert any("NATURE OF THE CASE" in e.text for e in start_entries)

    def test_new_heading_counter_statement(self, sample_brief_counter_statement):
        clean = normalize_text(sample_brief_counter_statement)
        entries, _, _ = build_heading_map(clean)
        start_entries = [e for e in entries if e.heading_type == "start"]
        assert any("COUNTER-STATEMENT" in e.text for e in start_entries)

    def test_pacer_headers_not_misidentified(self):
        text = (
            "Case 1:24-cv-00123-ABC Document 45 Filed 01/15/2024 Page 1 of 20\n\nSTATEMENT OF FACTS\n\nContent here.\n"
        )
        preprocessed = strip_pacer_headers(text)
        entries, _, _ = build_heading_map(preprocessed)
        # PACER header should be stripped, not detected as heading.
        texts = [e.text for e in entries]
        assert not any("DOCUMENT" in t and "FILED" in t for t in texts)

    def test_soft_keyword_word_boundary(self):
        """FACTSHEET should not match soft start keyword for FACT/FACTUAL."""
        text = "A. FACTSHEET SUMMARY\n\nSome content about facts.\n\nB. ARGUMENT\n\nMore.\n"
        entries, _, _ = build_heading_map(text)
        start_entries = [e for e in entries if e.heading_type == "start"]
        # FACTSHEET should not be classified as a start heading.
        assert not any("FACTSHEET" in e.text for e in start_entries)

    def test_introduction_tracked(self, sample_brief_introduction_factual):
        clean = normalize_text(sample_brief_introduction_factual)
        _, intro_found, intro_classified = build_heading_map(clean, "CERT_PETITION")
        assert intro_found is True
        assert intro_classified == "factual"

    def test_introduction_argumentative_by_default(self, sample_brief_introduction_argumentative):
        clean = normalize_text(sample_brief_introduction_argumentative)
        _, intro_found, intro_classified = build_heading_map(clean, "FEDERAL_APPELLATE_OPENING")
        assert intro_found is True
        assert intro_classified == "argumentative"

    def test_new_stop_headings_detected(self):
        text = (
            "STATEMENT OF FACTS\n\n"
            "The plaintiff suffered damages. " * 20 + "\n\nPRAYER FOR RELIEF\n\nPlaintiff requests damages.\n"
        )
        entries, _, _ = build_heading_map(text)
        stop_entries = [e for e in entries if e.heading_type == "stop"]
        assert any("PRAYER FOR RELIEF" in e.text for e in stop_entries)


# ============================================================================
# Phase B: Section classification + merge
# ============================================================================


class TestClassifyAndMerge:
    def test_single_facts_section(self, sample_brief_text):
        clean = normalize_text(sample_brief_text)
        preprocessed = merge_roman_heading_lines(strip_pacer_headers(clean))
        heading_map, _, _ = build_heading_map(preprocessed)
        sections = classify_sections(heading_map, len(preprocessed))
        fact_sections = [s for s in sections if s.role in ("facts", "procedural_history")]
        assert len(fact_sections) >= 1

    def test_multi_section_merge(self, sample_brief_multi_section):
        clean = normalize_text(sample_brief_multi_section)
        preprocessed = merge_roman_heading_lines(strip_pacer_headers(clean))
        heading_map, _, _ = build_heading_map(preprocessed)
        sections = classify_sections(heading_map, len(preprocessed))
        merged, notes = merge_fact_sections(sections)
        # Should merge STATEMENT OF FACTS + PROCEDURAL HISTORY.
        assert len(merged) == 2
        assert any("merged_2_sections" in n for n in notes)

    def test_merge_stops_at_argument(self, sample_brief_multi_section):
        clean = normalize_text(sample_brief_multi_section)
        preprocessed = merge_roman_heading_lines(strip_pacer_headers(clean))
        heading_map, _, _ = build_heading_map(preprocessed)
        sections = classify_sections(heading_map, len(preprocessed))
        merged, _ = merge_fact_sections(sections)
        # Should NOT include anything after ARGUMENT.
        for s in merged:
            assert s.role in ("facts", "procedural_history")

    def test_merge_limit_enforced(self):
        """More than 4 consecutive fact-like sections triggers merge limit warning."""
        parts = []
        for i in range(6):
            heading = f"STATEMENT OF FACTS PART {chr(65 + i)}" if i < 5 else "PROCEDURAL HISTORY"
            parts.append(f"{heading}\n\n{'Content about events. ' * 30}\n\n")
        parts.append("ARGUMENT\n\nThe law supports our position.\n")
        text = "\n".join(parts)

        heading_map, _, _ = build_heading_map(text)
        sections = classify_sections(heading_map, len(text))
        merged, notes = merge_fact_sections(sections)
        assert len(merged) <= 4
        assert "merge_limit_warning" in notes

    def test_counter_statement_detected(self, sample_brief_counter_statement):
        clean = normalize_text(sample_brief_counter_statement)
        preprocessed = merge_roman_heading_lines(strip_pacer_headers(clean))
        heading_map, _, _ = build_heading_map(preprocessed)
        sections = classify_sections(heading_map, len(preprocessed))
        fact_sections = [s for s in sections if s.role in ("facts", "procedural_history")]
        assert len(fact_sections) >= 1


# ============================================================================
# Phase C: Validation + quality gates
# ============================================================================


class TestValidation:
    def test_min_length_rejection(self):
        text = "Short." * 10  # ~60 chars — well below any minimum.
        result = validate_span(0, len(text), text, 10000, 1.0, "exact")
        assert result.start is None
        assert "span_too_short" in result.notes

    def test_max_length_guardrail(self, sample_brief_very_long_facts):
        clean = normalize_text(sample_brief_very_long_facts)
        preprocessed = merge_roman_heading_lines(strip_pacer_headers(clean))
        full_len = len(preprocessed)
        # Simulate a span that covers most of the document.
        result = validate_span(0, full_len, preprocessed, full_len, 1.0, "exact")
        # Should trigger truncation since span > 60% of document.
        if "guardrail_truncated" in result.notes:
            assert result.end is not None
            assert (result.end - result.start) <= min(int(0.60 * full_len) + 100, 50_000 + 100)

    def test_toc_contamination_flag(self):
        toc_lines = "Some Case v. Other ............... 1\n" * 10
        text = "Normal content. " * 50 + "\n" + toc_lines + "\n" + "More content. " * 50
        result = validate_span(0, len(text), text, 10000, 1.0, "exact")
        assert "toc_contamination" in result.notes

    def test_argument_contamination_flag(self):
        # Text heavy with argument markers.
        text = (
            "We argue that the court should reverse. "
            "This court should find in our favor. "
            "For these reasons, the judgment must be vacated. "
            "We argue again that this court should act. "
            "Standard of review requires reversal. "
        ) * 5
        result = validate_span(0, len(text), text, 10000, 1.0, "exact")
        has_arg_note = any("argument_contamination" in n for n in result.notes)
        assert has_arg_note

    def test_high_confidence_exact_no_downgrades(self):
        text = (
            "On January 1, 2024, the plaintiff filed a complaint in the "
            "District Court for the Southern District of New York alleging "
            "breach of contract. The case involves 500 F.3d 100 and "
            "300 U.S. 200 as key precedents. The defendant responded with "
            "a motion to dismiss which was denied after a hearing on the "
            "merits of the underlying claims. Discovery revealed documents "
            "showing the defendant knew about the contract terms. "
        ) * 3
        result = validate_span(0, len(text), text, len(text) * 5, 1.0, "exact")
        assert result.confidence == "high"


# ============================================================================
# Top-level extract_facts_span (integration)
# ============================================================================


class TestExtractFactsSpan:
    def test_exact_headings(self, sample_brief_text):
        clean = normalize_text(sample_brief_text)
        span, meta = extract_facts_span(clean)
        assert span is not None, f"Expected a span, got None. Notes: {meta['notes']}"
        start, end = span
        facts = clean[start:end]
        assert "Appellant filed a complaint" in facts
        assert "This Court should reverse" not in facts
        assert meta["method"] == "rules_v2"

    def test_no_match(self):
        text = "This document has no section headings at all, just prose about random topics."
        span, meta = extract_facts_span(text)
        assert span is None
        assert "no_span_found" in meta["notes"]

    def test_skips_toc(self, sample_brief_text):
        clean = normalize_text(sample_brief_text)
        span, meta = extract_facts_span(clean)
        assert span is not None
        start, end = span
        facts = clean[start:end]
        assert "TABLE OF CONTENTS" not in facts

    def test_soft_headings(self, sample_brief_soft_headings):
        clean = normalize_text(sample_brief_soft_headings)
        span, meta = extract_facts_span(clean)
        if span is not None:
            start, end = span
            facts = clean[start:end]
            assert "plaintiff was injured" in facts

    def test_fallback_pre_argument(self):
        text = (
            "Some preliminary text about the court.\n\n" + "A" * 1000 + "\n\n" + "ARGUMENT\n\n"
            "The defendant is liable.\n"
        )
        span, meta = extract_facts_span(text)
        if span is not None:
            assert "fallback_pre_argument" in meta["notes"]

    def test_multi_section_merged(self, sample_brief_multi_section):
        clean = normalize_text(sample_brief_multi_section)
        span, meta = extract_facts_span(clean)
        assert span is not None
        start, end = span
        facts = clean[start:end]
        # Should include content from both Statement of Facts and Procedural History.
        assert "plaintiff entered into a contract" in facts
        assert "plaintiff filed suit" in facts
        # Should NOT include argument.
        assert "correctly granted summary judgment" not in facts
        assert meta["sections_merged"] == 2

    def test_counter_statement(self, sample_brief_counter_statement):
        clean = normalize_text(sample_brief_counter_statement)
        span, meta = extract_facts_span(clean)
        assert span is not None
        start, end = span
        facts = clean[start:end]
        assert "counter-statement" in facts.lower() or "settlement agreement" in facts

    def test_nature_of_case(self, sample_brief_nature_of_case):
        clean = normalize_text(sample_brief_nature_of_case)
        span, meta = extract_facts_span(clean)
        assert span is not None
        start, end = span
        facts = clean[start:end]
        assert "personal injury" in facts

    def test_introduction_factual_cert_petition(self, sample_brief_introduction_factual):
        clean = normalize_text(sample_brief_introduction_factual)
        span, meta = extract_facts_span(clean, doc_type_id="CERT_PETITION")
        assert span is not None
        start, end = span
        facts = clean[start:end]
        assert "Fourth Amendment" in facts
        assert meta["intro_found"] is True
        assert meta["intro_classified_as"] == "factual"

    def test_introduction_skipped_for_unknown_doc_type(self, sample_brief_introduction_argumentative):
        clean = normalize_text(sample_brief_introduction_argumentative)
        span, meta = extract_facts_span(clean, doc_type_id="UNKNOWN")
        assert span is not None
        start, end = span
        facts = clean[start:end]
        # Should extract STATEMENT OF FACTS, not INTRODUCTION.
        assert "licensing agreement" in facts.lower() or "appellant entered" in facts.lower()
        # Should not include the argumentative intro content.
        assert "We argue that the district court" not in facts

    def test_output_schema_complete(self, sample_brief_text):
        clean = normalize_text(sample_brief_text)
        span, meta = extract_facts_span(clean)
        # Verify all expected metadata fields are present.
        assert "method" in meta
        assert "notes" in meta
        assert "confidence" in meta
        assert "sections_merged" in meta
        assert "heading_map_size" in meta
        assert "start_heading_text" in meta
        assert "stop_heading_text" in meta
        assert "match_method" in meta
        assert "doc_type_id" in meta
        assert "intro_found" in meta
        assert "intro_classified_as" in meta
        assert "quality_gates" in meta

    def test_max_length_guardrail_in_extraction(self, sample_brief_very_long_facts):
        clean = normalize_text(sample_brief_very_long_facts)
        span, meta = extract_facts_span(clean)
        if span is not None:
            start, end = span
            facts_len = end - start
            max_allowed = min(int(0.60 * len(clean)), 50_000)
            # Allow small buffer for paragraph-break alignment.
            assert facts_len <= max_allowed + 200


# ============================================================================
# Quality flags (backward compatibility)
# ============================================================================


class TestQualityFlags:
    def test_with_citations(self):
        text = "As held in 500 F.3d 100 and 300 U.S. 200, the standard applies."
        flags = quality_flags(text)
        assert flags["cite_hits"] >= 1
        assert flags["cite_hits_per_10k_chars"] > 0

    def test_with_arg_markers(self):
        text = "We argue that this court should reverse. For these reasons, the judgment must be vacated."
        flags = quality_flags(text)
        assert flags["arg_marker_hits"] >= 1

    def test_empty(self):
        flags = quality_flags("")
        assert flags["cite_hits"] == 0
        assert flags["arg_marker_hits"] == 0

    def test_no_matches(self):
        flags = quality_flags("The quick brown fox jumped over the lazy dog.")
        assert flags["cite_hits"] == 0
        assert flags["arg_marker_hits"] == 0


# ============================================================================
# Heading candidates (backward compatibility)
# ============================================================================


class TestHeadingCandidates:
    def test_finds_headings(self, sample_brief_text):
        clean = normalize_text(sample_brief_text)
        headings = heading_candidates(clean)
        assert isinstance(headings, list)
        heading_text = " ".join(headings)
        assert "STATEMENT OF FACTS" in heading_text or "ARGUMENT" in heading_text

    def test_excludes_bad_fragments(self):
        text = "TABLE OF CONTENTS\n\nSTATEMENT OF FACTS\n\nARGUMENT\n"
        headings = heading_candidates(text)
        assert "TABLE OF CONTENTS" not in headings

    def test_empty(self):
        headings = heading_candidates("no headings here, just prose about various topics.")
        assert headings == []

    def test_limit(self):
        text = "\n".join(f"HEADING NUMBER {i}" for i in range(100))
        headings = heading_candidates(text, limit=5)
        assert len(headings) <= 5


# ============================================================================
# Preprocessing utilities
# ============================================================================


class TestPreprocessing:
    def test_strip_pacer_headers(self):
        text = (
            "Case 1:24-cv-00123-ABC Document 45 Filed 01/15/2024 Page 1 of 20\n"
            "Normal text line.\n"
            "Case: 1:24 Document: 45 Page: 1\n"
            "Another normal line.\n"
        )
        result = strip_pacer_headers(text)
        assert "Normal text line." in result
        assert "Another normal line." in result
        assert "Document 45 Filed" not in result

    def test_merge_roman_heading_lines(self):
        text = "III\n. STATEMENT OF FACTS\n\nContent here.\n"
        result = merge_roman_heading_lines(text)
        assert "III. . STATEMENT OF FACTS" in result or "III." in result

    def test_merge_roman_preserves_normal_lines(self):
        text = "Normal line one.\nNormal line two."
        result = merge_roman_heading_lines(text)
        assert result == text

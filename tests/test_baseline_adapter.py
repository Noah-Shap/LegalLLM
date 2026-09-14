"""Tests for legallm.baseline_adapter (C3)."""

from legallm.baseline_adapter import RULES_VERSION, extract_rules, preprocess_text
from legallm.facts_extractor import extract_facts_span
from legallm.schema import FactsExtraction
from legallm.validators import validate_extraction


class TestPreprocessText:
    def test_idempotent_on_fixtures(
        self,
        sample_brief_text,
        sample_brief_multi_section,
        sample_brief_counter_statement,
        sample_brief_soft_headings,
        sample_pacer_stamp,
    ):
        for raw in (
            sample_brief_text,
            sample_brief_multi_section,
            sample_brief_counter_statement,
            sample_brief_soft_headings,
            sample_pacer_stamp,
        ):
            once = preprocess_text(raw)
            assert preprocess_text(once) == once

    def test_strips_pacer_header(self):
        raw = "Case 1:23-cv-00001 Document 5 Filed 01/01/24 Page 1 of 10\nSTATEMENT OF FACTS\nfoo"
        out = preprocess_text(raw)
        assert "Document 5" not in out
        assert "STATEMENT OF FACTS" in out

    def test_merges_roman_heading_line(self):
        assert "III. STATEMENT OF FACTS" in preprocess_text("III\nSTATEMENT OF FACTS\nbody")


class TestExtractRules:
    def test_returns_schema_object(self, sample_brief_text):
        ex = extract_rules(preprocess_text(sample_brief_text))
        assert isinstance(ex, FactsExtraction)
        assert ex.extractor_version == RULES_VERSION
        assert ex.confidence in ("high", "medium", "low")
        assert ex.doc_type_id == "UNKNOWN"

    def test_span_matches_doc_text_and_validates(self, sample_brief_text):
        doc = preprocess_text(sample_brief_text)
        ex = extract_rules(doc)
        assert ex.facts_span is not None
        assert doc[ex.facts_span.start : ex.facts_span.end] == ex.facts_span.text
        assert "Appellant filed a complaint" in ex.facts_span.text
        assert "This Court should reverse" not in ex.facts_span.text
        report = validate_extraction(ex, doc)
        assert report.ok, report.flags

    def test_agrees_with_raw_extractor(self, sample_brief_multi_section):
        doc = preprocess_text(sample_brief_multi_section)
        span, meta = extract_facts_span(doc)
        ex = extract_rules(doc)
        assert span is not None and ex.facts_span is not None
        assert (ex.facts_span.start, ex.facts_span.end) == span
        assert ex.confidence == meta["confidence"]
        for n in meta["notes"]:
            assert n in ex.notes
        assert "preprocessing_not_idempotent" not in ex.notes

    def test_case_citations_verbatim_and_deduped(self, sample_brief_text):
        doc = preprocess_text(sample_brief_text)
        ex = extract_rules(doc)
        assert ex.case_citations, "fixture contains 500 F.3d 100 and 300 U.S. 200"
        assert len(ex.case_citations) == len(set(ex.case_citations))
        for c in ex.case_citations:
            assert c in ex.facts_text

    def test_baseline_leaves_llm_only_fields_empty(self, sample_brief_text):
        ex = extract_rules(preprocess_text(sample_brief_text))
        assert ex.parties == []
        assert ex.procedural_posture is None
        assert ex.key_events == []
        assert ex.record_citations == []

    def test_no_span_found(self):
        ex = extract_rules("Just a short note with no headings at all.")
        assert ex.facts_span is None
        assert ex.confidence == "low"
        assert "no_span_found" in ex.notes
        assert ex.case_citations == []

    def test_doc_type_passthrough(self, sample_brief_introduction_factual):
        doc = preprocess_text(sample_brief_introduction_factual)
        ex = extract_rules(doc, doc_type_id="CERT_PETITION")
        assert ex.doc_type_id == "CERT_PETITION"
        assert ex.facts_span is not None

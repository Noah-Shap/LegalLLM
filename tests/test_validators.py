"""Tests for legallm.validators (C4)."""

from legallm.schema import FactsExtraction, FactsSpan, KeyEvent
from legallm.validators import (
    citation_supported,
    cite_key,
    parse_date,
    parse_payload,
    squash_ws,
    validate_extraction,
)

DOC = (
    "STATEMENT OF FACTS\n\n"
    "On January 1, 2024, Appellant filed a complaint. See 500 F.3d 100. "
    "The record at 1-ER-102 shows   the   hearing.\n\n"
    "ARGUMENT\n\nThe court erred."
)


def _ex(**kw) -> FactsExtraction:
    base = dict(extractor_version="test", confidence="high")
    base.update(kw)
    return FactsExtraction(**base)


def _span(text: str, doc: str = DOC) -> FactsSpan:
    a = doc.index(text)
    return FactsSpan(start=a, end=a + len(text), text=text)


class TestHelpers:
    def test_squash_ws(self):
        assert squash_ws("  a \n\n b\t c ") == "a b c"

    def test_parse_date_accepts_common_forms(self):
        for d in ("2024", "2024-01", "2024-01-05", "January 5, 2024", "Jan. 5, 2024", "Jan 5, 2024", "1/5/2024"):
            assert parse_date(d), d

    def test_parse_date_rejects_garbage(self):
        assert not parse_date("sometime in spring")
        assert not parse_date("2024-13-45")
        assert not parse_date("")

    def test_parse_date_none_ok(self):
        assert parse_date(None)

    def test_citation_supported_whitespace_insensitive(self):
        key = cite_key(DOC)
        assert citation_supported("500 F.3d 100", key)
        assert citation_supported("1-ER-102 shows the hearing", key)
        assert not citation_supported("999 U.S. 1", key)
        assert not citation_supported("   ", key)

    def test_citation_supported_hyphen_break_and_dash_glyphs(self):
        doc = "See 1- ER-102 and 1-ER-106–07 and “Foo” v. Bar, 5 F.3d 1."
        key = cite_key(doc)
        assert citation_supported("1-ER-102", key)  # hyphen-break artifact in source
        assert citation_supported("1-ER-106-07", key)  # en dash in source
        assert citation_supported('"Foo" v. Bar, 5 F.3d 1', key)  # curly quotes in source
        assert not citation_supported("1-ER-103", key)

    def test_citation_supported_dropped_hyphens_but_not_wrong_digits(self):
        doc = "See (9-ER2042) and (5ER-862) and 776 F. Supp. 1422, 1426 and 1-ER-106–07."
        key = cite_key(doc)
        assert citation_supported("9-ER-2042", key)  # PDF dropped a hyphen
        assert citation_supported("5-ER-862", key)
        assert not citation_supported("776 F. Supp. 1422, 1425", key)  # wrong pincite stays flagged
        assert not citation_supported("1-ER-107", key)  # range expansion stays flagged


class TestValidateExtraction:
    def test_clean_extraction_passes(self):
        ex = _ex(
            facts_span=_span("On January 1, 2024, Appellant filed a complaint. See 500 F.3d 100."),
            case_citations=["500 F.3d 100"],
            record_citations=["1-ER-102"],
            key_events=[KeyEvent(date="2024-01-01", text="Complaint filed.")],
        )
        r = validate_extraction(ex, DOC)
        assert r.ok, r.flags
        assert r.flags == []
        assert r.citation_fidelity == 1.0
        assert r.n_citations == 2
        assert all(r.checks.values())

    def test_span_out_of_bounds(self):
        ex = _ex(facts_span=FactsSpan(start=0, end=len(DOC) + 10, text="x"))
        r = validate_extraction(ex, DOC)
        assert not r.ok
        assert "span_out_of_bounds" in r.flags
        assert r.checks["span_in_bounds"] is False

    def test_span_text_mismatch(self):
        ex = _ex(facts_span=FactsSpan(start=0, end=5, text="WRONG"))
        r = validate_extraction(ex, DOC)
        assert not r.ok
        assert "span_text_mismatch" in r.flags

    def test_empty_facts_flagged_when_required(self):
        r = validate_extraction(_ex(), DOC)
        assert not r.ok
        assert "empty_facts" in r.flags

    def test_empty_facts_allowed_when_not_required(self):
        r = validate_extraction(_ex(), DOC, require_facts=False)
        assert r.ok

    def test_whitespace_only_span_is_empty(self):
        doc = "abc   \n  def"
        ex = _ex(facts_span=FactsSpan(start=3, end=8, text=doc[3:8]))
        r = validate_extraction(ex, doc)
        assert "empty_facts" in r.flags

    def test_hallucinated_citation_flagged(self):
        ex = _ex(facts_span=_span("STATEMENT OF FACTS"), case_citations=["500 F.3d 100", "999 U.S. 1"])
        r = validate_extraction(ex, DOC)
        assert not r.ok
        assert "unsupported_citation:999 U.S. 1" in r.flags
        assert r.citation_fidelity == 0.5
        assert r.n_unsupported_citations == 1

    def test_no_citations_gives_none_fidelity(self):
        r = validate_extraction(_ex(facts_span=_span("STATEMENT OF FACTS")), DOC)
        assert r.citation_fidelity is None
        assert r.checks["citation_fidelity"] is True

    def test_bad_date_flagged(self):
        ex = _ex(facts_span=_span("STATEMENT OF FACTS"), key_events=[KeyEvent(date="last spring", text="x")])
        r = validate_extraction(ex, DOC)
        assert "unparseable_date:last spring" in r.flags
        assert r.checks["dates_parseable"] is False

    def test_to_dict_shape(self):
        d = validate_extraction(_ex(facts_span=_span("STATEMENT OF FACTS")), DOC).to_dict()
        assert set(d) == {
            "ok",
            "flags",
            "checks",
            "citation_fidelity",
            "n_citations",
            "n_unsupported_citations",
        }


class TestParsePayload:
    def test_valid_payload(self):
        payload = {
            "facts_span": {"start": 0, "end": 3, "text": "abc"},
            "parties": ["A", "B"],
            "procedural_posture": None,
            "key_events": [],
            "record_citations": [],
            "case_citations": [],
            "confidence": "low",
            "notes": [],
            "extractor_version": "model-claimed",  # must be overwritten
            "schema_version": "0.0",  # must be dropped
        }
        ex, errors = parse_payload(payload, extractor_version="llm-v1", doc_type_id="CERT_PETITION")
        assert errors == []
        assert ex is not None
        assert ex.extractor_version == "llm-v1"
        assert ex.doc_type_id == "CERT_PETITION"
        assert ex.schema_version != "0.0"

    def test_invalid_payload_returns_errors(self):
        ex, errors = parse_payload({"confidence": "huge", "bogus": 1}, extractor_version="llm-v1")
        assert ex is None
        assert any("confidence" in e for e in errors)
        assert any("bogus" in e for e in errors)

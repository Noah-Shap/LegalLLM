"""Tests for legallm.llm_extractor (C2). No network: the Anthropic client is faked."""

import json
from types import SimpleNamespace

import pytest

from legallm.llm_extractor import (
    DEFAULT_MODEL,
    LlmConfig,
    LlmExtractionError,
    LlmExtractor,
    estimate_cost_usd,
    find_anchor,
    locate_span,
    select_window,
)
from legallm.schema import FactsExtraction, llm_output_json_schema
from legallm.single_doc import EXTRACTORS, extract_from_text
from legallm.validators import validate_extraction

DOC = (
    "IN THE COURT OF APPEALS\n\nTABLE OF CONTENTS\n\n"
    "STATEMENT OF FACTS\n\n"
    "On January 1, 2024, Appellant filed a complaint against Acme Corp. "
    "The district court held a hearing on March 15, 2024. See 500 F.3d 100; 1-ER-102. "
    "The court entered judgment for Acme Corp. and Appellant timely appealed.\n\n"
    "ARGUMENT\n\nThe court erred in every respect.\n"
)


def _wire(**overrides):
    base = {
        "has_facts": True,
        "facts_start_anchor": "On January 1, 2024, Appellant filed a complaint against Acme Corp.",
        "facts_end_anchor": "for Acme Corp. and Appellant timely appealed.",
        "parties": ["Appellant", "Acme Corp."],
        "procedural_posture": "Appeal from a judgment for Acme Corp.",
        "key_events": [{"date": "2024-01-01", "text": "Complaint filed."}, {"date": None, "text": "Judgment entered."}],
        "record_citations": ["1-ER-102"],
        "case_citations": ["500 F.3d 100"],
        "confidence": "high",
        "notes": [],
    }
    base.update(overrides)
    return base


class FakeMessages:
    def __init__(self, payload, *, stop_reason="end_turn", raw_text=None):
        self.payload = payload
        self.stop_reason = stop_reason
        self.raw_text = raw_text
        self.calls = []

    def create(self, **req):
        self.calls.append(req)
        text = self.raw_text if self.raw_text is not None else json.dumps(self.payload)
        return SimpleNamespace(
            model=req["model"],
            stop_reason=self.stop_reason,
            stop_details=None,
            _request_id="req_test",
            content=[SimpleNamespace(type="text", text=text)],
            usage=SimpleNamespace(
                input_tokens=1000, output_tokens=200, cache_creation_input_tokens=0, cache_read_input_tokens=0
            ),
        )


def _extractor(payload=None, **kw):
    fm = FakeMessages(payload or _wire(), **kw)
    return LlmExtractor(client=SimpleNamespace(messages=fm)), fm


class TestAnchors:
    def test_exact(self):
        assert find_anchor(DOC, "STATEMENT OF FACTS") == (
            DOC.index("STATEMENT OF FACTS"),
            DOC.index("STATEMENT OF FACTS") + 18,
        )

    def test_whitespace_case_quote_tolerant(self):
        doc = "The court\n  said “no” and\tstopped."
        hit = find_anchor(doc, 'the COURT said "no" and stopped')
        assert hit is not None
        assert doc[hit[0] : hit[1]] == "The court\n  said “no” and\tstopped"

    def test_not_found(self):
        assert find_anchor(DOC, "this text is not in the document") is None
        assert find_anchor(DOC, "   ") is None

    def test_start_at(self):
        first = DOC.index("Acme Corp.")
        hit = find_anchor(DOC, "Acme Corp.", start_at=first + 1)
        assert hit is not None and hit[0] > first

    def test_locate_span_ok(self):
        span, notes = locate_span(DOC, "On January 1, 2024, Appellant", "Appellant timely appealed.")
        assert span is not None and notes == []
        assert span.text.startswith("On January 1, 2024") and span.text.endswith("timely appealed.")
        assert DOC[span.start : span.end] == span.text

    def test_locate_span_missing_or_bad(self):
        assert locate_span(DOC, None, "x")[1] == ["anchor_missing"]
        assert locate_span(DOC, "not here at all", "appealed.")[1] == ["start_anchor_not_found"]
        assert locate_span(DOC, "On January 1", "not here either")[1] == ["end_anchor_not_found"]


class TestWindow:
    def test_no_truncation(self):
        assert select_window(DOC, 10_000) == (DOC, False)

    def test_head_window_cuts_at_newline(self):
        text, truncated = select_window(DOC, 60)
        assert truncated and len(text) <= 60 and DOC.startswith(text)


class TestCost:
    def test_sonnet_price(self):
        usage = SimpleNamespace(
            input_tokens=1_000_000, output_tokens=100_000, cache_creation_input_tokens=0, cache_read_input_tokens=0
        )
        assert estimate_cost_usd("claude-sonnet-5", usage) == pytest.approx(2.0 + 1.0)

    def test_unknown_model(self):
        assert estimate_cost_usd("nope", SimpleNamespace(input_tokens=1)) is None


class TestSchema:
    def test_structured_output_schema_shape(self):
        s = llm_output_json_schema()
        assert s["type"] == "object" and s["additionalProperties"] is False
        assert "$ref" not in json.dumps(s) and "$defs" not in s
        assert set(s["required"]) == set(s["properties"])
        assert "facts_start_anchor" in s["properties"] and "facts_span" not in s["properties"]
        ev = s["properties"]["key_events"]["items"]
        assert ev["additionalProperties"] is False


class TestExtractor:
    def test_happy_path_and_provenance(self):
        ex_fn, fm = _extractor()
        ex = ex_fn(DOC, "DISTRICT_COURT")
        assert isinstance(ex, FactsExtraction)
        assert ex.extractor_version == "llm-v2"  # default prompt version
        assert ex.doc_type_id == "DISTRICT_COURT"
        assert ex.facts_span is not None and DOC[ex.facts_span.start : ex.facts_span.end] == ex.facts_span.text
        assert ex.facts_span.text.startswith("On January 1") and ex.facts_span.text.endswith("timely appealed.")
        assert ex.parties == ["Appellant", "Acme Corp."]
        assert ex.key_events[1].date is None
        assert ex.provenance["model_id"] == DEFAULT_MODEL
        assert ex.provenance["prompt_version"] == "v2"
        assert ex.provenance["retries"] == 0
        assert len(ex.provenance["prompt_sha"]) == 16
        assert ex.provenance["input_tokens"] == 1000
        assert ex.provenance["cost_usd"] == pytest.approx((1000 * 2 + 200 * 10) / 1e6)
        assert ex.provenance["doc_truncated"] is False
        assert ex.provenance["anchors"]["start"].startswith("On January 1")
        assert ex.provenance["anchors"]["has_facts"] is True
        assert validate_extraction(ex, DOC).ok

    def test_request_shape(self):
        ex_fn, fm = _extractor()
        ex_fn(DOC, "UNKNOWN")
        req = fm.calls[0]
        assert req["model"] == DEFAULT_MODEL
        assert "temperature" not in req
        assert req["output_config"]["format"]["type"] == "json_schema"
        assert req["output_config"]["effort"] == "medium"
        assert req["system"][0]["cache_control"] == {"type": "ephemeral"}
        assert "<document" in req["messages"][0]["content"] and DOC in req["messages"][0]["content"]

    def test_no_facts(self):
        ex_fn, _ = _extractor(_wire(has_facts=False, facts_start_anchor=None, facts_end_anchor=None, confidence="low"))
        ex = ex_fn(DOC)
        assert ex.facts_span is None and "llm_no_facts" in ex.notes
        assert not validate_extraction(ex, DOC).ok

    def test_hallucinated_anchor_yields_no_span(self):
        ex_fn, _ = _extractor(_wire(facts_start_anchor="words that are not in the brief"))
        ex = ex_fn(DOC)
        assert ex.facts_span is None and "start_anchor_not_found" in ex.notes

    def test_hallucinated_citation_caught_by_validators(self):
        ex_fn, _ = _extractor(_wire(case_citations=["500 F.3d 100", "999 U.S. 1"]))
        r = validate_extraction(ex_fn(DOC), DOC)
        assert not r.ok and r.citation_fidelity == pytest.approx(2 / 3)  # 500 F.3d 100 + 1-ER-102 ok, 999 U.S. 1 not

    def test_truncation_note(self):
        cfg = LlmConfig(max_doc_chars=120)
        fm = FakeMessages(_wire())
        ex = LlmExtractor(cfg, client=SimpleNamespace(messages=fm))(DOC)
        assert "doc_truncated_to_window" in ex.notes and ex.provenance["doc_truncated"] is True
        assert 'truncated="true"' in fm.calls[0]["messages"][0]["content"]

    def test_bad_json_raises(self):
        ex_fn, _ = _extractor(raw_text="not json")
        with pytest.raises(LlmExtractionError, match="non-JSON"):
            ex_fn(DOC)

    def test_schema_violation_raises(self):
        ex_fn, _ = _extractor(_wire(confidence="huge"))
        with pytest.raises(LlmExtractionError, match="schema"):
            ex_fn(DOC)

    def test_max_tokens_raises(self):
        ex_fn, _ = _extractor(stop_reason="max_tokens")
        with pytest.raises(LlmExtractionError, match="max_tokens"):
            ex_fn(DOC)

    def test_refusal_raises(self):
        ex_fn, _ = _extractor(stop_reason="refusal")
        with pytest.raises(LlmExtractionError, match="refused"):
            ex_fn(DOC)

    def test_missing_credentials_message(self, monkeypatch):
        import anthropic

        def boom(*a, **k):
            raise anthropic.AnthropicError("no creds")

        monkeypatch.setattr(anthropic, "Anthropic", boom)
        with pytest.raises(LlmExtractionError, match="ant auth login"):
            _ = LlmExtractor().client

    def test_prompt_sha_changes_with_prompt(self):
        a = LlmExtractor(LlmConfig(), client=object()).prompt_sha
        b = LlmExtractor(LlmConfig(system_prompt="different"), client=object()).prompt_sha
        assert a != b


class TestRegistry:
    def test_llm_v1_registered(self):
        assert "llm-v1" in EXTRACTORS

    def test_single_doc_path_with_fake_client(self, monkeypatch):
        import legallm.llm_extractor as mod

        fm = FakeMessages(_wire())
        monkeypatch.setitem(
            mod._extractors, "v1", LlmExtractor(LlmConfig(prompt_version="v1"), client=SimpleNamespace(messages=fm))
        )
        r = extract_from_text(DOC, method="llm-v1")
        assert r.extraction.extractor_version == "llm-v1"
        assert r.validation.ok, r.validation.flags
        d = r.to_dict()
        assert d["extraction"]["provenance"]["cost_usd"] > 0

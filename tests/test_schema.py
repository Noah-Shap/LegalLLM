"""Tests for legallm.schema (C1)."""

import json

import pytest
from pydantic import ValidationError

from legallm.schema import (
    SCHEMA_VERSION,
    FactsExtraction,
    FactsSpan,
    KeyEvent,
    llm_output_json_schema,
)


class TestFactsSpan:
    def test_valid(self):
        s = FactsSpan(start=0, end=5, text="hello")
        assert s.length == 5

    def test_end_before_start_rejected(self):
        with pytest.raises(ValidationError):
            FactsSpan(start=5, end=1, text="x")

    def test_negative_rejected(self):
        with pytest.raises(ValidationError):
            FactsSpan(start=-1, end=1, text="x")


class TestFactsExtraction:
    def test_minimal(self):
        ex = FactsExtraction(extractor_version="rules_v2", confidence="high")
        assert ex.schema_version == SCHEMA_VERSION
        assert ex.facts_span is None
        assert ex.facts_text == ""
        assert not ex.has_facts
        assert ex.parties == [] and ex.key_events == [] and ex.case_citations == []

    def test_full_roundtrip(self):
        ex = FactsExtraction(
            extractor_version="llm-v1",
            confidence="medium",
            facts_span=FactsSpan(start=10, end=20, text="0123456789"),
            parties=["Smith", "Jones Corp."],
            procedural_posture="Appeal from summary judgment.",
            key_events=[KeyEvent(date="2024-01-01", text="Complaint filed."), KeyEvent(text="Hearing held.")],
            record_citations=["1-ER-102"],
            case_citations=["500 F.3d 100"],
            notes=["merged_2_sections"],
            doc_type_id="DISTRICT_COURT",
        )
        assert ex.has_facts
        data = json.loads(ex.to_json())
        back = FactsExtraction.model_validate(data)
        assert back == ex

    def test_bad_confidence_rejected(self):
        with pytest.raises(ValidationError):
            FactsExtraction(extractor_version="x", confidence="very high")

    def test_extra_field_rejected(self):
        with pytest.raises(ValidationError):
            FactsExtraction(extractor_version="x", confidence="low", hallucinated_field=1)

    def test_extractor_version_required(self):
        with pytest.raises(ValidationError):
            FactsExtraction(confidence="low")

    def test_key_event_text_required(self):
        with pytest.raises(ValidationError):
            KeyEvent(date="2024", text="")


class TestLlmOutputSchema:
    def test_wire_schema_excludes_producer_fields(self):
        schema = llm_output_json_schema()
        for k in ("extractor_version", "schema_version", "doc_type_id", "provenance", "facts_span"):
            assert k not in schema["properties"]
        assert schema["additionalProperties"] is False
        assert set(schema["required"]) == set(schema["properties"])

    def test_refs_inlined(self):
        schema = llm_output_json_schema()
        assert "$defs" not in schema
        assert "$ref" not in json.dumps(schema)
        assert schema["properties"]["key_events"]["items"]["properties"]["text"]["type"] == "string"

    def test_provenance_default_and_roundtrip(self):
        ex = FactsExtraction(
            extractor_version="llm-v1", confidence="low", provenance={"model_id": "m", "cost_usd": 0.01}
        )
        assert FactsExtraction.model_validate(json.loads(ex.to_json())).provenance["cost_usd"] == 0.01
        assert FactsExtraction(extractor_version="x", confidence="low").provenance == {}

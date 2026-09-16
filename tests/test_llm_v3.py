"""Prompt v3 / wire schema 2 (structured record citations) and the explicit method registry."""

import json
from types import SimpleNamespace

import pytest

from legallm.llm_extractor import (
    METHOD_PROMPT_VERSIONS,
    LlmConfig,
    LlmExtractor,
    method_version,
    plain_method_for,
)
from legallm.prompts import FACTS_SYSTEM_V2, FACTS_SYSTEM_V3, PROMPT_WIRE, PROMPTS
from legallm.routing import ROUTED_METHODS, get_router, reset_router
from legallm.schema import LlmFactsOutput, LlmFactsOutputV2, RecordCite, llm_output_json_schema, wire_model
from legallm.single_doc import EXTRACTORS

DOC = (
    "IN THE COURT OF APPEALS\n\nSTATEMENT OF FACTS\n\nOn January 5, 2020, the plaintiff filed suit. 2-ER-104, 106. "
    "The court dismissed the complaint. 5-ER-873-876.\n\nARGUMENT\n\nThe district court erred.\n"
)


def _wire_v2(record_cites):
    return {
        "has_facts": True,
        "facts_start_anchor": "On January 5, 2020, the plaintiff",
        "facts_end_anchor": "dismissed the complaint. 5-ER-873-876.",
        "parties": ["plaintiff"],
        "procedural_posture": "Appeal.",
        "key_events": [],
        "record_citations": record_cites,
        "case_citations": [],
        "confidence": "high",
        "notes": [],
    }


class FakeMessages:
    def __init__(self, payload):
        self.payload, self.calls = payload, []

    def create(self, **req):
        self.calls.append(req)
        return SimpleNamespace(
            model=req["model"],
            stop_reason="end_turn",
            stop_details=None,
            _request_id="r",
            content=[SimpleNamespace(type="text", text=json.dumps(self.payload))],
            usage=SimpleNamespace(
                input_tokens=10, output_tokens=5, cache_creation_input_tokens=0, cache_read_input_tokens=0
            ),
        )


class TestPromptV3:
    def test_v3_is_v2_plus_structured_record_cites(self):
        assert PROMPTS["v3"][1] == PROMPTS["v2"][1]  # user template unchanged
        assert FACTS_SYSTEM_V3 != FACTS_SYSTEM_V2
        assert "as_printed" in FACTS_SYSTEM_V3 and "as_printed" not in FACTS_SYSTEM_V2
        # everything outside the record_citations bullet is identical
        v2_lines = [ln for ln in FACTS_SYSTEM_V2.splitlines() if not ln.startswith(("- record_citations", "  "))]
        v3_lines = [ln for ln in FACTS_SYSTEM_V3.splitlines() if not ln.startswith(("- record_citations", "  "))]
        assert v2_lines == v3_lines
        assert PROMPT_WIRE == {"v1": "1", "v2": "1", "v3": "2"}

    def test_frozen_shas(self):
        v2 = LlmExtractor(LlmConfig(prompt_version="v2", backend="api"), client=object())
        v3 = LlmExtractor(LlmConfig(prompt_version="v3", backend="api"), client=object())
        assert v2.prompt_sha == "aa4020336ae219ec"  # v2 untouched by the wire-schema change
        assert v3.prompt_sha == "59532802dd12b37b", v3.prompt_sha
        assert v3.wire_version == "2" and v2.wire_version == "1"


class TestWireSchema2:
    def test_schema_has_record_cite_objects(self):
        s1 = llm_output_json_schema("1")
        s2 = llm_output_json_schema("2")
        assert s1["properties"]["record_citations"]["items"] == {"type": "string"}
        items = s2["properties"]["record_citations"]["items"]
        assert set(items["properties"]) == {"as_printed", "prefix", "pages"} and items["additionalProperties"] is False
        assert "$ref" not in json.dumps(s2) and "$defs" not in s2
        assert wire_model("1") is LlmFactsOutput and wire_model("2") is LlmFactsOutputV2
        with pytest.raises(KeyError):
            wire_model("9")

    def test_v2_model_validates_objects_and_rejects_strings(self):
        ok = LlmFactsOutputV2.model_validate(
            _wire_v2([{"as_printed": "2-ER-104, 106", "prefix": "2-ER", "pages": ["104", "106"]}])
        )
        assert isinstance(ok.record_citations[0], RecordCite)
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            LlmFactsOutputV2.model_validate(_wire_v2(["2-ER-104"]))

    def test_extractor_keeps_printed_string_and_pages(self):
        cites = [
            {"as_printed": "2-ER-104, 106", "prefix": "2-ER", "pages": ["104", "106"]},
            {"as_printed": "5-ER-873-876", "prefix": "5-ER", "pages": ["873", "876"]},
        ]
        fm = FakeMessages(_wire_v2(cites))
        ex = LlmExtractor(LlmConfig(prompt_version="v3", backend="api"), client=SimpleNamespace(messages=fm))(DOC)
        assert ex.record_citations == ["2-ER-104, 106", "5-ER-873-876"]  # downstream stays strings
        assert ex.provenance["record_cites_structured"] == cites and ex.provenance["wire"] == "2"
        assert fm.calls[0]["output_config"]["format"]["schema"]["properties"]["record_citations"]["items"]["properties"]
        from legallm.validators import validate_extraction

        rep = validate_extraction(ex, DOC)
        assert rep.citation_fidelity == 1.0 and rep.n_nonverbatim_citations == 0

    def test_v2_prompt_still_uses_wire_1(self):
        fm = FakeMessages({**_wire_v2(["2-ER-104, 106"])})
        ex = LlmExtractor(LlmConfig(prompt_version="v2", backend="api"), client=SimpleNamespace(messages=fm))(DOC)
        assert ex.record_citations == ["2-ER-104, 106"] and "record_cites_structured" not in ex.provenance
        assert fm.calls[0]["output_config"]["format"]["schema"]["properties"]["record_citations"]["items"] == {
            "type": "string"
        }


class TestRegistry:
    def test_lineage(self):
        assert METHOD_PROMPT_VERSIONS == {"llm-v1": "v1", "llm-v2": "v2", "llm-v4": "v3"}
        assert set(ROUTED_METHODS) == {"llm-v3", "llm-v5"}
        assert ROUTED_METHODS["llm-v5"].cheap_version == "v3" and ROUTED_METHODS["llm-v5"].cheap_method == "llm-v4"
        assert set(EXTRACTORS) == {"rules_v2", "llm-v1", "llm-v2", "llm-v3", "llm-v4", "llm-v5"}
        assert method_version("llm-v4") == "v3" and plain_method_for("v2") == "llm-v2"
        with pytest.raises(KeyError):
            method_version("llm-v3")  # routed, not plain
        with pytest.raises(KeyError):
            plain_method_for("v9")

    def test_routers_are_per_method(self):
        reset_router()
        r3, r5 = get_router("llm-v3"), get_router("llm-v5")
        assert r3 is not r5 and r3.method == "llm-v3" and r5.method == "llm-v5"
        assert r5.cheap.config.prompt_version == "v3" and r5.strong.config.prompt_version == "v3"
        assert r3.config_payload.startswith("llm-v3|") and r5.config_payload.startswith("llm-v5|")
        assert r5.config_payload != r3.config_payload
        with pytest.raises(KeyError):
            get_router("llm-v9")
        reset_router()

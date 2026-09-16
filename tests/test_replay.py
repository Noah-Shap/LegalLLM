"""Tests for legallm.replay (record/replay model responses) and the gate's use of it."""

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from legallm.ci_gate import SMOKE_GOLD, build_extractors, run_smoke
from legallm.llm_extractor import LlmConfig, LlmExtractor
from legallm.replay import (
    RecordingClient,
    ReplayClient,
    ReplayError,
    load_responses,
    request_key,
    response_from,
    save_responses,
)

DOC = (
    "IN THE COURT OF APPEALS\n\nSTATEMENT OF FACTS\n\nOn January 5, 2020, the plaintiff filed suit. "
    "The court dismissed the complaint.\n\nARGUMENT\n\nThe district court erred.\n"
)
WIRE = {
    "has_facts": True,
    "facts_start_anchor": "On January 5, 2020, the plaintiff",
    "facts_end_anchor": "dismissed the complaint.",
    "parties": ["plaintiff"],
    "procedural_posture": "Appeal.",
    "key_events": [],
    "record_citations": [],
    "case_citations": [],
    "confidence": "high",
    "notes": [],
}


class FakeMessages:
    def __init__(self, text):
        self.text, self.calls = text, 0

    def create(self, **req):
        self.calls += 1
        return SimpleNamespace(
            model=req["model"],
            stop_reason="end_turn",
            stop_details=None,
            _request_id="r",
            content=[SimpleNamespace(type="text", text=self.text)],
            usage=SimpleNamespace(
                input_tokens=10, output_tokens=5, cache_creation_input_tokens=0, cache_read_input_tokens=0
            ),
            cli={"total_cost_usd": 0.01},
        )


def test_request_key_depends_on_model_prompt_and_document():
    ex_a = LlmExtractor(LlmConfig(prompt_version="v2", backend="api"), client=object())
    ex_b = LlmExtractor(LlmConfig(prompt_version="v1", backend="api"), client=object())
    ex_c = LlmExtractor(LlmConfig(prompt_version="v2", backend="api", model="claude-opus-5"), client=object())
    k = request_key(ex_a.build_request(DOC, "UNKNOWN")[0])
    assert len(k) == 16
    assert k == request_key(ex_a.build_request(DOC, "UNKNOWN")[0])
    assert k != request_key(ex_a.build_request(DOC + " x", "UNKNOWN")[0])
    assert k != request_key(ex_b.build_request(DOC, "UNKNOWN")[0])
    assert k != request_key(ex_c.build_request(DOC, "UNKNOWN")[0])


def test_record_then_replay_roundtrip(tmp_path):
    store = {}
    fake = FakeMessages(json.dumps(WIRE))
    rec_client = RecordingClient(SimpleNamespace(messages=fake), store)
    ex = LlmExtractor(LlmConfig(prompt_version="v2", backend="api"), client=rec_client)
    out = ex(DOC)
    assert out.facts_span is not None and fake.calls == 1 and len(store) == 1
    rec = next(iter(store.values()))
    assert rec["usage"]["input_tokens"] == 10 and rec["cli_cost_usd"] == 0.01 and json.loads(rec["text"]) == WIRE
    p = tmp_path / "responses.jsonl"
    save_responses(p, store)
    loaded = load_responses(p)
    assert loaded.keys() == store.keys() and load_responses(tmp_path / "none.jsonl") == {}
    ex2 = LlmExtractor(LlmConfig(prompt_version="v2", backend="api"), client=ReplayClient(loaded))
    out2 = ex2(DOC)
    assert (out2.facts_span.start, out2.facts_span.end) == (out.facts_span.start, out.facts_span.end)
    assert out2.provenance["input_tokens"] == 10
    assert fake.calls == 1  # replay never touched the real client


def test_replay_miss_raises():
    ex = LlmExtractor(LlmConfig(prompt_version="v2", backend="api"), client=ReplayClient({}))
    with pytest.raises(ReplayError, match="no recorded response"):
        ex(DOC)
    r = response_from({"text": "{}", "model": "m"})
    assert r.usage is None and r.content[0].text == "{}"


def test_build_extractors_replay_and_router():
    ext = build_extractors({}, record=False, backend="api")
    assert set(ext) == {"llm-v1", "llm-v2", "llm-v3", "llm-v4", "llm-v5"}
    assert ext["llm-v3"].cheap is ext["llm-v2"] and ext["llm-v3"].strong.config.model == "claude-opus-5"
    assert ext["llm-v5"].cheap is ext["llm-v4"] and ext["llm-v5"].strong.config.prompt_version == "v3"
    assert ext["llm-v4"].wire_version == "2" and ext["llm-v2"].wire_version == "1"


def test_committed_recordings_cover_the_fixture_briefs(tmp_path):
    """The committed recordings replay every fixture brief without a live call."""
    data = run_smoke(["rules_v2", "llm-v2", "llm-v3"], gold=SMOKE_GOLD, runs_dir=tmp_path / "runs")
    for m in ("llm-v2", "llm-v3"):
        assert data["summaries"][m]["n_errors"] == 0, data["summaries"][m]
        assert data["summaries"][m]["iou_mean"] is not None
    assert data["meta"]["n_recordings"] >= 3 and Path(data["meta"]["responses"]).name == "responses.jsonl"

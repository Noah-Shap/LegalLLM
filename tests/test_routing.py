"""Tests for legallm.routing (item 11, llm-v3: cheap tier first, strong tier on trigger). Offline, fake clients."""

import json
from types import SimpleNamespace

import pytest

import legallm.llm_extractor as llm_mod
from legallm.extraction_eval import ExtractionCache, method_config_sha, run_method
from legallm.gold import GoldRecord, doc_sha1
from legallm.llm_extractor import LlmConfig, LlmExtractionError, LlmExtractor
from legallm.routing import (
    DEFAULT_TRIGGERS,
    ROUTED_METHOD,
    RouteConfig,
    Router,
    get_router,
    reset_router,
    trigger_for,
)

DOC = (
    "IN THE COURT OF APPEALS\n\nSTATEMENT OF FACTS\n\nOn January 5, 2020, the plaintiff filed suit against "
    "the defendant in district court. The court dismissed the complaint. See Smith v. Jones, 500 U.S. 100 (1991).\n\n"
    "ARGUMENT\n\nThe district court erred.\n"
)


def _wire(*, has_facts=True, start="On January 5, 2020, the plaintiff", end="500 U.S. 100 (1991).", cites=None):
    return {
        "has_facts": has_facts,
        "facts_start_anchor": start if has_facts else None,
        "facts_end_anchor": end if has_facts else None,
        "parties": ["plaintiff", "defendant"],
        "procedural_posture": "Appeal from dismissal.",
        "key_events": [],
        "record_citations": [],
        "case_citations": cites if cites is not None else ["500 U.S. 100 (1991)"],
        "confidence": "high",
        "notes": [],
    }


class FakeMessages:
    def __init__(self, payload, *, fail=False):
        self.payload, self.fail, self.calls = payload, fail, []

    def create(self, **req):
        self.calls.append(req)
        if self.fail:
            raise RuntimeError("boom")
        return SimpleNamespace(
            model=req["model"],
            stop_reason="end_turn",
            stop_details=None,
            _request_id="req",
            content=[SimpleNamespace(type="text", text=json.dumps(self.payload))],
            usage=SimpleNamespace(
                input_tokens=1000, output_tokens=100, cache_creation_input_tokens=0, cache_read_input_tokens=0
            ),
        )


def _tier(payload, *, model, fail=False):
    fm = FakeMessages(payload, fail=fail)
    ex = LlmExtractor(LlmConfig(model=model, prompt_version="v2", backend="api"), client=SimpleNamespace(messages=fm))
    return ex, fm


def _router(cheap_payload, strong_payload=None, *, cheap_fail=False, strong_fail=False, triggers=DEFAULT_TRIGGERS):
    cheap, cfm = _tier(cheap_payload, model="claude-sonnet-5", fail=cheap_fail)
    strong, sfm = _tier(strong_payload or _wire(), model="claude-opus-5", fail=strong_fail)
    return Router(RouteConfig(triggers=triggers), cheap=cheap, strong=strong), cfm, sfm


class TestTrigger:
    def test_no_trigger_on_good_span(self):
        ex = _tier(_wire(), model="m")[0](DOC)
        assert trigger_for(ex, DOC, DEFAULT_TRIGGERS) is None

    def test_anchor_not_found(self):
        ex = _tier(_wire(start="THIS ANCHOR IS NOWHERE IN THE DOCUMENT AT ALL"), model="m")[0](DOC)
        assert ex.facts_span is None and "start_anchor_not_found" in ex.notes
        assert trigger_for(ex, DOC, DEFAULT_TRIGGERS) == "anchor_not_found"

    def test_no_facts_verdict_is_not_escalated(self):
        ex = _tier(_wire(has_facts=False), model="m")[0](DOC)
        assert ex.facts_span is None and "llm_no_facts" in ex.notes
        assert trigger_for(ex, DOC, DEFAULT_TRIGGERS) is None

    def test_error_trigger(self):
        assert trigger_for(None, DOC, DEFAULT_TRIGGERS) == "error"
        assert trigger_for(None, DOC, ("anchor_not_found",)) is None

    def test_unsupported_citation_only_when_configured(self):
        ex = _tier(_wire(cites=["999 F.3d 999 (2020)"]), model="m")[0](DOC)
        assert trigger_for(ex, DOC, DEFAULT_TRIGGERS) is None
        assert trigger_for(ex, DOC, DEFAULT_TRIGGERS + ("unsupported_citation",)) == "unsupported_citation"


class TestRouter:
    def test_cheap_pass_kept_when_clean(self):
        r, cfm, sfm = _router(_wire())
        ex = r(DOC)
        assert ex.extractor_version == ROUTED_METHOD and ex.facts_span is not None
        assert len(cfm.calls) == 1 and len(sfm.calls) == 0
        rt = ex.provenance["routing"]
        assert rt["escalated"] is False and rt["trigger"] is None and ex.provenance["tier"] == "cheap"
        assert ex.notes[-1] == "routed:cheap"
        assert ex.provenance["model_id"] == "claude-sonnet-5"

    def test_escalates_on_anchor_failure_and_sums_cost(self):
        r, cfm, sfm = _router(_wire(start="NOWHERE TO BE FOUND ANCHOR TEXT HERE"), _wire())
        ex = r(DOC)
        assert len(cfm.calls) == 1 and len(sfm.calls) == 1
        assert sfm.calls[0]["model"] == "claude-opus-5"
        assert ex.facts_span is not None and ex.provenance["tier"] == "strong"
        rt = ex.provenance["routing"]
        assert rt["trigger"] == "anchor_not_found" and rt["escalated"] and rt["strong_recovered"]
        assert rt["cheap"]["span"] is None and rt["strong"]["span"] == [ex.facts_span.start, ex.facts_span.end]
        # cost = cheap + strong at list prices: sonnet (1000 in, 100 out) + opus (1000 in, 100 out)
        assert ex.provenance["cost_usd"] == pytest.approx((2.0 + 1.0) / 1000 + (5.0 + 2.5) / 1000)
        assert ex.provenance["latency_s"] >= rt["cheap"]["latency_s"]
        assert "routed:strong:anchor_not_found" in ex.notes

    def test_cheap_error_escalates(self):
        r, cfm, sfm = _router(_wire(), _wire(), cheap_fail=True)
        ex = r(DOC)
        assert len(sfm.calls) == 1 and ex.provenance["routing"]["trigger"] == "error"
        assert ex.provenance["routing"]["cheap"]["error"].startswith("RuntimeError")

    def test_strong_error_falls_back_to_cheap(self):
        r, cfm, sfm = _router(_wire(start="NOWHERE TO BE FOUND ANCHOR TEXT HERE"), strong_fail=True)
        ex = r(DOC)
        assert ex.provenance["tier"] == "cheap" and "escalation_error" in ex.provenance["routing"]
        assert ex.facts_span is None

    def test_both_fail_raises(self):
        r, _, _ = _router(_wire(), cheap_fail=True, strong_fail=True)
        with pytest.raises(LlmExtractionError):
            r(DOC)

    def test_route_with_supplied_cheap_result_skips_cheap_call(self):
        r, cfm, sfm = _router(_wire())
        cheap = _tier(_wire(), model="claude-sonnet-5")[0](DOC)
        ex = r.route(DOC, cheap=cheap)
        assert len(cfm.calls) == 0 and len(sfm.calls) == 0 and ex.provenance["tier"] == "cheap"


class TestRegistryAndHarness:
    def test_registered_and_config_sha(self, monkeypatch):
        from legallm.single_doc import EXTRACTORS

        assert ROUTED_METHOD in EXTRACTORS
        reset_router()
        r = get_router(RouteConfig(backend="api"))
        assert get_router() is r
        sha = method_config_sha(ROUTED_METHOD)
        assert len(sha) == 12 and sha != method_config_sha("llm-v2")
        assert "claude-opus-5" in r.config_payload and "anchor_not_found" in r.config_payload
        llm_mod.configure_default(backend="api")  # rebuilds the router
        assert get_router() is not r
        reset_router()

    def test_harness_reuses_cached_cheap_result(self, tmp_path):
        cache = ExtractionCache(tmp_path / "cache")
        rec = GoldRecord(gold_id="g1", search_result_id=1, source="audit_set", pdf_path="x", rules_span=None)
        # cheap tier cached under llm-v2 with a good span -> the router must not call either tier
        cheap_ex = _tier(_wire(), model="claude-sonnet-5")[0](DOC)
        cache.put("llm-v2", ExtractionCache.key(method_config_sha("llm-v2"), doc_sha1(DOC)), cheap_ex, 0.1)
        r, cfm, sfm = _router(_wire(), _wire())
        out = run_method([rec], ROUTED_METHOD, {"g1": DOC}, cache=cache, extractor=r, config_sha="abc")
        assert out[0].error is None and out[0].span_found
        assert len(cfm.calls) == 0 and len(sfm.calls) == 0
        assert cache.get(ROUTED_METHOD, ExtractionCache.key("abc", doc_sha1(DOC))) is not None

    def test_harness_without_cheap_cache_calls_cheap(self, tmp_path):
        cache = ExtractionCache(tmp_path / "cache")
        rec = GoldRecord(gold_id="g1", search_result_id=1, source="audit_set", pdf_path="x", rules_span=None)
        r, cfm, sfm = _router(_wire(), _wire())
        out = run_method([rec], ROUTED_METHOD, {"g1": DOC}, cache=cache, extractor=r, config_sha="abc")
        assert out[0].error is None and len(cfm.calls) == 1 and len(sfm.calls) == 0

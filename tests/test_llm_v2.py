"""Tests for prompt v2 wiring (item 8): version registry, anchor relaxation (L2), CLI retry (L5)."""

import json
from types import SimpleNamespace

import pytest

from legallm.claude_cli import ClaudeCliClient, ClaudeCliError
from legallm.llm_extractor import (
    LlmConfig,
    LlmExtractionError,
    LlmExtractor,
    configure_default,
    find_anchor_relaxed,
    get_extractor,
    locate_span,
    method_version,
)
from legallm.prompts import PROMPT_VERSION, PROMPT_VERSIONS, PROMPTS
from legallm.single_doc import EXTRACTORS

DOC = (
    "STATEMENT OF THE CASE\n\n"
    "Case: 24-720, 07/25/2024, DktEntry: 17.1, Page 15 of 86\n"
    "X provides a free online platform allowing users to express their viewpoints and share information.\n"
    "The district court denied X leave to amend. X appealed.\n\n"
    "SUMMARY OF ARGUMENT\n\nThe court erred.\n"
)


class TestVersions:
    def test_prompts_registry(self):
        assert PROMPT_VERSIONS == ("v1", "v2", "v3") and PROMPT_VERSION == "v2"
        assert PROMPTS["v1"][0] != PROMPTS["v2"][0]
        assert "attachments are never the facts section" in PROMPTS["v2"][0]
        assert "never expand" in PROMPTS["v2"][0]

    def test_v1_prompt_frozen(self):
        # prompt_sha of v1 must not drift (the eval cache is keyed by it)
        sha = LlmExtractor(LlmConfig(prompt_version="v1"), client=object()).prompt_sha
        assert sha == "2e9b97f8dcd48884", sha

    def test_config_resolution(self):
        c1, c2 = LlmConfig(prompt_version="v1"), LlmConfig(prompt_version="v2")
        assert c1.resolved_system_prompt == PROMPTS["v1"][0] and c2.resolved_user_template == PROMPTS["v2"][1]
        assert LlmConfig(system_prompt="X").resolved_system_prompt == "X"
        assert c1.extractor_version == "llm-v1" and c2.extractor_version == "llm-v2"

    def test_unknown_version_rejected(self):
        with pytest.raises(LlmExtractionError, match="unknown prompt version"):
            LlmExtractor(LlmConfig(prompt_version="v9"), client=object())
        with pytest.raises(KeyError):
            get_extractor("v9")

    def test_method_registry_and_overrides(self, monkeypatch):
        assert "llm-v1" in EXTRACTORS and "llm-v2" in EXTRACTORS
        assert method_version("llm-v2") == "v2"
        with pytest.raises(KeyError):
            method_version("rules_v2")
        import legallm.llm_extractor as mod

        monkeypatch.setattr(mod, "_overrides", {})
        monkeypatch.setattr(mod, "_extractors", {})
        configure_default(backend="claude-cli", effort="high")
        assert get_extractor("v1").config.backend == "claude-cli" and get_extractor("v1").config.effort == "high"
        assert get_extractor("v2").config.prompt_version == "v2" and get_extractor("v2").config.backend == "claude-cli"
        assert get_extractor("v1") is get_extractor("v1")  # cached per version


class TestAnchorRelaxation:
    def test_exact_still_preferred(self):
        hit, relaxed = find_anchor_relaxed(DOC, "X provides a free online platform", keep_head=True)
        assert hit is not None and not relaxed

    def test_start_relaxes_to_head_words(self):
        # model appended a paraphrase after 8 verbatim words
        hit, relaxed = find_anchor_relaxed(
            DOC, "X provides a free online platform allowing users to speak freely", keep_head=True
        )
        assert relaxed and DOC[hit[0] :].startswith("X provides a free online platform allowing users")

    def test_end_relaxes_to_tail_words(self):
        hit, relaxed = find_anchor_relaxed(
            DOC, "some invented preamble denied X leave to amend. X appealed.", keep_head=False
        )
        assert relaxed and DOC[: hit[1]].endswith("X appealed.")

    def test_no_match_at_all(self):
        hit, relaxed = find_anchor_relaxed(DOC, "nothing like this appears anywhere in the text", keep_head=True)
        assert hit is None and not relaxed

    def test_locate_span_notes(self):
        span, notes = locate_span(
            DOC,
            "X provides a free online platform allowing users to speak freely",
            "junk before denied X leave to amend. X appealed.",
        )
        assert span is not None
        assert span.text.startswith("X provides") and span.text.endswith("X appealed.")
        assert notes == ["start_anchor_relaxed", "end_anchor_relaxed"]


class _FlakyRun:
    """First call: CLI error with no detail; second: a good structured result."""

    def __init__(self):
        self.calls = 0

    def __call__(self, argv, **kw):
        import subprocess

        self.calls += 1
        if self.calls == 1:
            body = {"is_error": True, "result": None}
        else:
            body = {
                "is_error": False,
                "structured_output": {
                    "has_facts": True,
                    "facts_start_anchor": "X provides a free online platform",
                    "facts_end_anchor": "X appealed.",
                    "parties": ["X"],
                    "procedural_posture": None,
                    "key_events": [],
                    "record_citations": [],
                    "case_citations": [],
                    "confidence": "high",
                    "notes": [],
                },
                "modelUsage": {"claude-sonnet-5": {"inputTokens": 10, "outputTokens": 5}},
                "total_cost_usd": 0.001,
                "session_id": "s",
            }
        return subprocess.CompletedProcess(argv, 0, stdout=json.dumps(body), stderr="")


class TestCliRetry:
    def test_retries_once_on_transient_error(self):
        run = _FlakyRun()
        ex_fn = LlmExtractor(LlmConfig(backend="claude-cli"), client=ClaudeCliClient(exe="claude", run=run))
        ex = ex_fn(DOC)
        assert run.calls == 2 and ex.facts_span is not None
        assert ex.provenance["retries"] == 1

    def test_gives_up_after_second_failure(self):
        def always_bad(argv, **kw):
            import subprocess

            return subprocess.CompletedProcess(
                argv, 0, stdout=json.dumps({"is_error": True, "result": None}), stderr=""
            )

        ex_fn = LlmExtractor(LlmConfig(backend="claude-cli"), client=ClaudeCliClient(exe="claude", run=always_bad))
        with pytest.raises(LlmExtractionError, match="claude-cli"):
            ex_fn(DOC)

    def test_non_transient_not_retried(self):
        calls = []

        def boom(argv, **kw):
            calls.append(1)
            raise ClaudeCliError("could not run claude: missing")

        ex_fn = LlmExtractor(LlmConfig(backend="claude-cli"), client=ClaudeCliClient(exe="claude", run=boom))
        with pytest.raises(LlmExtractionError):
            ex_fn(DOC)
        assert len(calls) == 1


def test_fake_client_namespace_still_works():
    fm = SimpleNamespace(
        create=lambda **req: SimpleNamespace(
            model="m",
            stop_reason="end_turn",
            stop_details=None,
            _request_id="r",
            content=[
                SimpleNamespace(
                    type="text",
                    text=json.dumps(
                        {
                            "has_facts": False,
                            "facts_start_anchor": None,
                            "facts_end_anchor": None,
                            "parties": [],
                            "procedural_posture": None,
                            "key_events": [],
                            "record_citations": [],
                            "case_citations": [],
                            "confidence": "low",
                            "notes": ["clerk letter"],
                        }
                    ),
                )
            ],
            usage=None,
        )
    )
    ex = LlmExtractor(client=SimpleNamespace(messages=fm))(DOC)
    assert ex.facts_span is None and "llm_no_facts" in ex.notes and ex.extractor_version == "llm-v2"

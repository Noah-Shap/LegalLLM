"""Tests for legallm.claude_cli (item 4b). No real CLI: subprocess.run is faked."""

import json
import os
import subprocess

import pytest

from legallm.claude_cli import (
    ClaudeCliClient,
    ClaudeCliError,
    build_argv,
    build_env,
    find_claude_exe,
    parse_result,
    to_response,
)
from legallm.llm_extractor import LlmConfig, LlmExtractionError, LlmExtractor
from legallm.validators import validate_extraction

DOC = "STATEMENT OF FACTS\n\nOn January 1, 2024, Appellant sued Acme. Judgment followed.\n\nARGUMENT\n\nNo.\n"

WIRE = {
    "has_facts": True,
    "facts_start_anchor": "On January 1, 2024, Appellant sued Acme.",
    "facts_end_anchor": "Judgment followed.",
    "parties": ["Appellant", "Acme"],
    "procedural_posture": None,
    "key_events": [],
    "record_citations": [],
    "case_citations": [],
    "confidence": "high",
    "notes": [],
}


def _cli_result(**over):
    res = {
        "type": "result",
        "is_error": False,
        "result": "done",
        "structured_output": WIRE,
        "modelUsage": {
            "claude-sonnet-5": {
                "inputTokens": 1200,
                "outputTokens": 90,
                "cacheReadInputTokens": 0,
                "cacheCreationInputTokens": 0,
            }
        },
        "total_cost_usd": 0.0033,
        "duration_ms": 4200,
        "duration_api_ms": 3900,
        "session_id": "sess_abc",
        "num_turns": 1,
    }
    res.update(over)
    return res


class FakeRun:
    def __init__(self, result=None, *, stdout=None, returncode=0, stderr="", raise_exc=None):
        self.result = result
        self.stdout = stdout
        self.returncode = returncode
        self.stderr = stderr
        self.raise_exc = raise_exc
        self.calls = []

    def __call__(self, argv, **kw):
        self.calls.append((argv, kw))
        if self.raise_exc:
            raise self.raise_exc
        out = self.stdout if self.stdout is not None else json.dumps(self.result)
        return subprocess.CompletedProcess(argv, self.returncode, stdout=out, stderr=self.stderr)


REQ = {
    "model": "claude-sonnet-5",
    "max_tokens": 100,
    "system": [{"type": "text", "text": "SYS", "cache_control": {"type": "ephemeral"}}],
    "messages": [{"role": "user", "content": "USER PROMPT"}],
    "output_config": {"format": {"type": "json_schema", "schema": {"type": "object"}}, "effort": "medium"},
}


class TestArgvAndEnv:
    def test_argv(self):
        argv, stdin = build_argv("claude", REQ)
        assert argv[:2] == ["claude", "-p"]
        assert "--output-format" in argv and argv[argv.index("--output-format") + 1] == "json"
        assert argv[argv.index("--tools") + 1] == ""
        assert "--no-session-persistence" in argv
        assert argv[argv.index("--model") + 1] == "claude-sonnet-5"
        assert "--append-system-prompt" not in argv  # default: system text folded into the prompt
        assert stdin == "<instructions>\nSYS\n</instructions>\n\nUSER PROMPT"
        assert json.loads(argv[argv.index("--json-schema") + 1]) == {"type": "object"}
        assert argv[argv.index("--effort") + 1] == "medium"

    def test_argv_flag_mode(self):
        argv, stdin = build_argv("claude", REQ, system_via="flag")
        assert argv[argv.index("--append-system-prompt") + 1] == "SYS"
        assert stdin == "USER PROMPT"

    def test_find_exe_prefers_native_binary(self, tmp_path, monkeypatch):
        shim = tmp_path / "claude.CMD"
        shim.write_text("@echo off", encoding="utf-8")
        native = tmp_path / "node_modules" / "@anthropic-ai" / "claude-code" / "bin" / "claude.exe"
        native.parent.mkdir(parents=True)
        native.write_bytes(b"")
        monkeypatch.setattr("legallm.claude_cli.shutil.which", lambda name: str(shim))
        assert find_claude_exe() == str(native)

    def test_find_exe_missing(self, monkeypatch):
        monkeypatch.setattr("legallm.claude_cli.shutil.which", lambda name: None)
        with pytest.raises(ClaudeCliError, match="not found"):
            find_claude_exe()

    def test_argv_without_optional_parts(self):
        argv, _ = build_argv("claude", {"model": "m", "messages": [{"role": "user", "content": "x"}]})
        assert "--append-system-prompt" not in argv and "--json-schema" not in argv and "--effort" not in argv

    def test_multi_message_rejected(self):
        with pytest.raises(ClaudeCliError):
            build_argv(
                "claude", {"messages": [{"role": "user", "content": "a"}, {"role": "assistant", "content": "b"}]}
            )

    def test_env_strips_keys(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-x")
        monkeypatch.setenv("ANTHROPIC_AUTH_TOKEN", "tok")
        monkeypatch.setenv("CLAUDECODE", "1")
        monkeypatch.setenv("PATH", "keep")
        env = build_env()
        assert "ANTHROPIC_API_KEY" not in env and "ANTHROPIC_AUTH_TOKEN" not in env and "CLAUDECODE" not in env
        assert env["PATH"] == "keep"


class TestParse:
    def test_preamble_tolerated(self):
        assert parse_result('warning: something\n{"a": 1}')["a"] == 1

    def test_no_json(self):
        with pytest.raises(ClaudeCliError, match="no JSON"):
            parse_result("nothing here")

    def test_bad_json(self):
        with pytest.raises(ClaudeCliError, match="not JSON"):
            parse_result("{not valid")

    def test_to_response_usage_from_model_usage(self):
        r = to_response(_cli_result(), "claude-sonnet-5")
        assert r.model == "claude-sonnet-5"
        assert r.usage.input_tokens == 1200 and r.usage.output_tokens == 90
        assert json.loads(r.content[0].text) == WIRE
        assert r.cli["total_cost_usd"] == 0.0033 and r.cli["session_id"] == "sess_abc"
        assert r._request_id == "sess_abc"

    def test_requested_model_wins_over_side_task_model(self):
        res = _cli_result(
            modelUsage={"claude-haiku-4-5-20251001": {"inputTokens": 5}, "claude-sonnet-5": {"inputTokens": 9}}
        )
        r = to_response(res, "claude-sonnet-5")
        assert r.model == "claude-sonnet-5" and r.usage.input_tokens == 14

    def test_to_response_usage_snake_case(self):
        res = _cli_result(usage={"input_tokens": 7, "output_tokens": 3})
        assert to_response(res, "m").usage.input_tokens == 7

    def test_is_error(self):
        with pytest.raises(ClaudeCliError, match="reported an error"):
            to_response(_cli_result(is_error=True, result="boom"), "m")

    def test_missing_structured_output(self):
        with pytest.raises(ClaudeCliError, match="no structured_output"):
            to_response(_cli_result(structured_output=None), "m")


class TestClient:
    def test_create_runs_cli(self):
        run = FakeRun(_cli_result())
        client = ClaudeCliClient(exe="claude", run=run)
        resp = client.messages.create(**REQ)
        argv, kw = run.calls[0]
        assert argv[0] == "claude" and kw["input"].endswith("USER PROMPT")
        assert "ANTHROPIC_API_KEY" not in kw["env"] and "CLAUDECODE" not in kw["env"]
        assert kw["encoding"] == "utf-8"
        assert kw["cwd"] == client.messages.workdir and not any(os.scandir(kw["cwd"]))
        assert resp.stop_reason == "end_turn"

    def test_nonzero_exit_without_json(self):
        run = FakeRun(stdout="", returncode=1, stderr="not logged in")
        with pytest.raises(ClaudeCliError, match="exited 1"):
            ClaudeCliClient(exe="claude", run=run).messages.create(**REQ)

    def test_timeout(self):
        run = FakeRun(raise_exc=subprocess.TimeoutExpired(cmd="claude", timeout=1))
        with pytest.raises(ClaudeCliError, match="timed out"):
            ClaudeCliClient(exe="claude", run=run, timeout_s=1).messages.create(**REQ)

    def test_missing_exe(self):
        run = FakeRun(raise_exc=FileNotFoundError("claude"))
        with pytest.raises(ClaudeCliError, match="could not run"):
            ClaudeCliClient(exe="claude", run=run).messages.create(**REQ)


class TestExtractorWithCliBackend:
    def test_end_to_end_provenance(self):
        run = FakeRun(_cli_result())
        ex_fn = LlmExtractor(LlmConfig(backend="claude-cli"), client=ClaudeCliClient(exe="claude", run=run))
        ex = ex_fn(DOC, "UNKNOWN")
        assert ex.facts_span is not None and ex.facts_span.text.endswith("Judgment followed.")
        assert ex.provenance["backend"] == "claude-cli"
        assert ex.provenance["billing"] == "subscription"
        assert ex.provenance["cost_usd"] == 0.0033
        assert ex.provenance["cli"]["duration_ms"] == 4200
        assert ex.provenance["input_tokens"] == 1200
        assert validate_extraction(ex, DOC).ok
        # the CLI received our schema and prompt
        argv, kw = run.calls[0]
        assert "--json-schema" in argv and "<document" in kw["input"]

    def test_cli_error_maps_to_extraction_error(self):
        run = FakeRun(_cli_result(is_error=True, result="rate limited"))
        ex_fn = LlmExtractor(LlmConfig(backend="claude-cli"), client=ClaudeCliClient(exe="claude", run=run))
        with pytest.raises(LlmExtractionError, match="claude-cli"):
            ex_fn(DOC)

    def test_unknown_backend(self):
        with pytest.raises(LlmExtractionError, match="unknown backend"):
            _ = LlmExtractor(LlmConfig(backend="carrier-pigeon")).client

    def test_cli_backend_builds_cli_client(self):
        ex_fn = LlmExtractor(LlmConfig(backend="claude-cli"))
        assert isinstance(ex_fn.client, ClaudeCliClient)

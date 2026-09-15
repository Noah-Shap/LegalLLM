"""Claude Code CLI transport for the LLM extractor (item 4b).

Runs the same request through headless ``claude -p`` instead of the Messages
API, so extraction/eval runs bill the claude.ai subscription rather than API
credits. Pattern borrowed from Hustle's ``Invoke-DraftSpec.ps1``:

    claude -p --model <id> --output-format json --tools '' --no-session-persistence \\
           --json-schema <schema> [--append-system-prompt <text>] [--effort <level>]   < prompt

Two environment conditions are mandatory (learned the hard way in Hustle):
``ANTHROPIC_API_KEY`` / ``ANTHROPIC_AUTH_TOKEN`` must be absent (a key outranks
the login and its org may have no credit) and ``CLAUDECODE`` must be cleared
(Claude Code refuses to start nested inside itself).

The adapter exposes ``.messages.create(**req)`` and returns an object with the
same attributes ``LlmExtractor`` reads from an SDK ``Message`` (``content``,
``usage``, ``stop_reason``, ``model``, ``_request_id``) plus ``.cli`` with the
CLI-only fields (``total_cost_usd``, ``duration_ms``, ``session_id``).

Limits: works only on a machine with an active ``claude`` login; not usable
from a deployed service. Record ``backend`` in provenance so results from the
two transports are never mixed silently.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

BACKEND_NAME = "claude-cli"
_STRIP_ENV = ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "CLAUDECODE")


class ClaudeCliError(RuntimeError):
    """The CLI could not be run or returned an unusable result."""


@dataclass
class CliUsage:
    input_tokens: int = 0
    output_tokens: int = 0
    cache_creation_input_tokens: int = 0
    cache_read_input_tokens: int = 0


@dataclass
class CliTextBlock:
    text: str
    type: str = "text"


@dataclass
class CliResponse:
    model: str
    content: list[CliTextBlock]
    usage: CliUsage
    stop_reason: str = "end_turn"
    stop_details: Any = None
    _request_id: str | None = None
    cli: dict[str, Any] = field(default_factory=dict)


def find_claude_exe() -> str:
    """Path to the Claude Code executable.

    On Windows ``shutil.which`` returns the npm ``claude.cmd`` shim, which re-parses
    every argument through cmd.exe (long JSON args fail with "filename, directory
    name, or volume label syntax is incorrect"). Prefer the native binary the shim
    wraps: ``<bin>/node_modules/@anthropic-ai/claude-code/bin/claude.exe``.
    """
    exe = shutil.which("claude")
    if exe is None:
        raise ClaudeCliError("`claude` CLI not found on PATH (install Claude Code and run `claude login`)")
    if exe.lower().endswith((".cmd", ".bat")):
        native = os.path.join(os.path.dirname(exe), "node_modules", "@anthropic-ai", "claude-code", "bin", "claude.exe")
        if os.path.exists(native):
            return native
    return exe


def build_env(base: dict[str, str] | None = None) -> dict[str, str]:
    """Copy of the environment with API-key and nested-session variables removed."""
    env = dict(os.environ if base is None else base)
    for k in _STRIP_ENV:
        env.pop(k, None)
    return env


def _system_text(system: Any) -> str | None:
    if system is None:
        return None
    if isinstance(system, str):
        return system
    parts = [b.get("text", "") for b in system if isinstance(b, dict) and b.get("type") == "text"]
    return "\n".join(p for p in parts if p) or None


def _user_text(messages: list[dict[str, Any]]) -> str:
    if len(messages) != 1 or messages[0].get("role") != "user":
        raise ClaudeCliError("claude-cli backend supports exactly one user message")
    content = messages[0]["content"]
    if isinstance(content, str):
        return content
    return "\n".join(b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text")


def build_argv(exe: str, req: dict[str, Any], *, system_via: str = "prompt") -> tuple[list[str], str]:
    """Translate a Messages-API-shaped request into CLI argv + stdin text.

    ``system_via="prompt"`` (default, the Hustle-proven shape) folds the system text
    into the stdin prompt; ``"flag"`` passes it with ``--append-system-prompt``.
    """
    argv = [exe, "-p", "--output-format", "json", "--tools", "", "--no-session-persistence"]
    if req.get("model"):
        argv += ["--model", str(req["model"])]
    sys_text = _system_text(req.get("system"))
    user_text = _user_text(req.get("messages") or [])
    if sys_text and system_via == "flag":
        argv += ["--append-system-prompt", sys_text]
    elif sys_text:
        user_text = "<instructions>\n" + sys_text + "\n</instructions>\n\n" + user_text
    oc = req.get("output_config") or {}
    fmt = oc.get("format") or {}
    if fmt.get("type") == "json_schema" and fmt.get("schema") is not None:
        argv += ["--json-schema", json.dumps(fmt["schema"], separators=(",", ":"))]
    if oc.get("effort"):
        argv += ["--effort", str(oc["effort"])]
    return argv, user_text


def parse_result(raw: str) -> dict[str, Any]:
    """Parse the CLI's JSON result, tolerating any preamble before the first '{'."""
    start = raw.find("{")
    if start < 0:
        raise ClaudeCliError(f"claude returned no JSON: {raw[:300]!r}")
    try:
        res = json.loads(raw[start:])
    except json.JSONDecodeError as e:
        raise ClaudeCliError(f"claude output is not JSON ({e}): {raw[start : start + 300]!r}") from e
    if not isinstance(res, dict):
        raise ClaudeCliError("claude output is not a JSON object")
    return res


def _int(d: dict[str, Any], *keys: str) -> int:
    for k in keys:
        v = d.get(k)
        if isinstance(v, int | float):
            return int(v)
    return 0


def _usage_from(res: dict[str, Any]) -> CliUsage:
    u = res.get("usage")
    if isinstance(u, dict):
        return CliUsage(
            input_tokens=_int(u, "input_tokens", "inputTokens"),
            output_tokens=_int(u, "output_tokens", "outputTokens"),
            cache_creation_input_tokens=_int(u, "cache_creation_input_tokens", "cacheCreationInputTokens"),
            cache_read_input_tokens=_int(u, "cache_read_input_tokens", "cacheReadInputTokens"),
        )
    total = CliUsage()
    for mu in (res.get("modelUsage") or {}).values():
        if isinstance(mu, dict):
            total.input_tokens += _int(mu, "inputTokens", "input_tokens")
            total.output_tokens += _int(mu, "outputTokens", "output_tokens")
            total.cache_creation_input_tokens += _int(mu, "cacheCreationInputTokens", "cache_creation_input_tokens")
            total.cache_read_input_tokens += _int(mu, "cacheReadInputTokens", "cache_read_input_tokens")
    return total


def to_response(res: dict[str, Any], requested_model: str) -> CliResponse:
    if res.get("is_error"):
        raise ClaudeCliError(f"claude reported an error: {res.get('result')!r}")
    so = res.get("structured_output")
    if so is None:
        raise ClaudeCliError(
            f"claude returned no structured_output (keys={sorted(res)}; result: {str(res.get('result'))[:300]!r})"
        )
    models = list((res.get("modelUsage") or {}).keys())
    primary = [m for m in models if m == requested_model or (requested_model and m.startswith(requested_model))]
    model = primary[0] if primary else (models[0] if models else requested_model)
    cli = {
        "total_cost_usd": res.get("total_cost_usd"),
        "duration_ms": res.get("duration_ms"),
        "duration_api_ms": res.get("duration_api_ms"),
        "session_id": res.get("session_id"),
        "num_turns": res.get("num_turns"),
        "models_used": models,
    }
    return CliResponse(
        model=model,
        content=[CliTextBlock(text=json.dumps(so))],
        usage=_usage_from(res),
        stop_reason="end_turn",
        _request_id=res.get("session_id"),
        cli=cli,
    )


Runner = Callable[..., subprocess.CompletedProcess[str]]


class ClaudeCliMessages:
    """``.create(**req)`` shaped like ``anthropic.Anthropic().messages``."""

    def __init__(
        self,
        exe: str | None = None,
        timeout_s: float = 900.0,
        run: Runner = subprocess.run,
        system_via: str = "prompt",
        workdir: str | None = None,
    ):
        self._exe = exe
        self.timeout_s = timeout_s
        self._run = run
        self.system_via = system_via
        # Run in an empty directory: otherwise Claude Code loads the caller's CLAUDE.md /
        # project context into the prompt, which contaminated the first real run.
        self.workdir = workdir or tempfile.mkdtemp(prefix="legallm-claude-cli-")

    @property
    def exe(self) -> str:
        if self._exe is None:
            self._exe = find_claude_exe()
        return self._exe

    def create(self, **req: Any) -> CliResponse:
        argv, stdin_text = build_argv(self.exe, req, system_via=self.system_via)
        try:
            proc = self._run(
                argv,
                input=stdin_text,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=build_env(),
                cwd=self.workdir,
                timeout=self.timeout_s,
            )
        except subprocess.TimeoutExpired as e:
            raise ClaudeCliError(f"claude timed out after {self.timeout_s}s") from e
        except OSError as e:
            raise ClaudeCliError(f"could not run claude: {e}") from e
        if proc.returncode != 0 and "{" not in (proc.stdout or ""):
            raise ClaudeCliError(f"claude exited {proc.returncode}: {(proc.stderr or proc.stdout)[:500]!r}")
        return to_response(parse_result(proc.stdout or ""), str(req.get("model", "")))


class ClaudeCliClient:
    def __init__(
        self,
        exe: str | None = None,
        timeout_s: float = 900.0,
        run: Runner = subprocess.run,
        system_via: str = "prompt",
        workdir: str | None = None,
    ):
        self.messages = ClaudeCliMessages(exe=exe, timeout_s=timeout_s, run=run, system_via=system_via, workdir=workdir)

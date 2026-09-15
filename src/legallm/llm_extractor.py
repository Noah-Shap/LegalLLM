"""LLM facts extractor (intent.md §5, C2) — cheap tier only (routing is item 11).

    extract_llm(doc_text, doc_type_id) -> FactsExtraction

Design
------
- One structured-output call (``output_config.format`` = JSON schema of
  ``LlmFactsOutput``). The model returns verbatim *anchors* for the start and
  end of the facts section, never offsets; ``locate_span`` maps them back onto
  ``doc_text`` (exact match, then a whitespace/quote-tolerant match). A missing
  anchor yields ``facts_span=None`` plus a note, which the validators turn into
  ``empty_facts`` — the signal the escalation router will act on.
- Determinism: current models reject ``temperature``; we rely on adaptive
  thinking at a fixed ``effort`` and record ``prompt_sha`` + ``model_id`` in
  ``provenance`` so runs are reproducible in configuration if not bit-for-bit.
- Long briefs: whole document when it fits ``max_doc_chars``; otherwise the head
  window (facts sections sit in the first half of a brief) with a note. Offsets
  stay valid because the window starts at 0.
- Retries/timeouts: SDK retries (429/5xx/connection) with ``max_retries``;
  per-request timeout; non-retryable API errors raise ``LlmExtractionError``.
- Cost: computed from ``usage`` with a per-model price table; stored in
  ``provenance`` for the eval harness and request logs.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
from dataclasses import dataclass
from typing import Any

from legallm.claude_cli import BACKEND_NAME as CLI_BACKEND
from legallm.claude_cli import ClaudeCliClient, ClaudeCliError
from legallm.prompts import PROMPT_VERSION, PROMPT_VERSIONS, PROMPTS
from legallm.schema import FactsExtraction, FactsSpan, LlmFactsOutput, llm_output_json_schema
from legallm.validators import parse_payload

DEFAULT_MODEL = "claude-sonnet-5"  # D1 (intent.md §11): Sonnet 5 is the extractor tier
EXTRACTOR_VERSION = f"llm-{PROMPT_VERSION}"

# USD per 1M tokens (Anthropic API list prices, 2026-06). Cache multipliers are the
# standard 1.25x write / 0.1x read; treat cost as an estimate, not an invoice.
PRICES_PER_MTOK: dict[str, dict[str, float]] = {
    "claude-sonnet-5": {"input": 2.00, "output": 10.00},
    "claude-opus-5": {"input": 5.00, "output": 25.00},
    "claude-haiku-4-5": {"input": 1.00, "output": 5.00},
}


class LlmExtractionError(RuntimeError):
    """Raised when the model call cannot produce a usable extraction."""


# ---------------------------------------------------------------------------
# Anchor location
# ---------------------------------------------------------------------------

_QUOTE_MAP = str.maketrans({"‘": "'", "’": "'", "“": '"', "”": '"', "–": "-", "—": "-"})


def _canon(text: str) -> tuple[str, list[int]]:
    """Canonicalise text for tolerant matching; return (canon, index_map to original)."""
    out: list[str] = []
    idx: list[int] = []
    in_ws = False
    for i, ch in enumerate(text.translate(_QUOTE_MAP)):
        if ch.isspace():
            if not in_ws and out:
                out.append(" ")
                idx.append(i)
            in_ws = True
        else:
            out.append(ch.lower())
            idx.append(i)
            in_ws = False
    # drop trailing space
    if out and out[-1] == " ":
        out.pop()
        idx.pop()
    return "".join(out), idx


def find_anchor(doc_text: str, anchor: str, *, start_at: int = 0) -> tuple[int, int] | None:
    """Return (start, end) offsets of ``anchor`` in ``doc_text`` at or after ``start_at``.

    Tries an exact match first, then a case-, whitespace-, and quote-insensitive match.
    """
    a = anchor.strip()
    if not a:
        return None
    pos = doc_text.find(a, start_at)
    if pos >= 0:
        return pos, pos + len(a)
    c_doc, idx = _canon(doc_text[start_at:])
    c_anchor, _ = _canon(a)
    if not c_anchor:
        return None
    pos = c_doc.find(c_anchor)
    if pos < 0:
        return None
    s = start_at + idx[pos]
    e = start_at + idx[pos + len(c_anchor) - 1] + 1
    return s, e


RELAX_SIZES = (8, 6, 4)  # word counts tried when a full anchor is not found (L2 in the taxonomy)


def _relaxed(anchor: str, n: int, *, keep_head: bool) -> str:
    words = anchor.split()
    if len(words) <= n:
        return ""
    return " ".join(words[:n] if keep_head else words[-n:])


def find_anchor_relaxed(
    doc_text: str, anchor: str, *, keep_head: bool, start_at: int = 0
) -> tuple[tuple[int, int] | None, bool]:
    """Exact/tolerant match first; then progressively shorter prefixes (start) or suffixes (end).

    Returns ((start, end) or None, relaxed). A relaxed match keeps the matched fragment's
    boundary on the side that matters (the head of a start anchor, the tail of an end anchor).
    """
    hit = find_anchor(doc_text, anchor, start_at=start_at)
    if hit is not None:
        return hit, False
    for n in RELAX_SIZES:
        frag = _relaxed(anchor, n, keep_head=keep_head)
        if not frag:
            continue
        hit = find_anchor(doc_text, frag, start_at=start_at)
        if hit is not None:
            return hit, True
    return None, False


def locate_span(doc_text: str, start_anchor: str | None, end_anchor: str | None) -> tuple[FactsSpan | None, list[str]]:
    """Build a FactsSpan from the model's anchors; return (span_or_None, notes)."""
    notes: list[str] = []
    if not start_anchor or not end_anchor:
        return None, ["anchor_missing"]
    s, s_relaxed = find_anchor_relaxed(doc_text, start_anchor, keep_head=True)
    if s is None:
        return None, ["start_anchor_not_found"]
    if s_relaxed:
        notes.append("start_anchor_relaxed")
    e, e_relaxed = find_anchor_relaxed(doc_text, end_anchor, keep_head=False, start_at=s[0])
    if e is None:
        # End anchor may legitimately precede the start anchor's *end* if they overlap; try from doc start.
        e, e_relaxed = find_anchor_relaxed(doc_text, end_anchor, keep_head=False)
        if e is None:
            return None, notes + ["end_anchor_not_found"]
    if e_relaxed:
        notes.append("end_anchor_relaxed")
    start, end = s[0], e[1]
    if end <= start:
        return None, ["anchor_order_invalid"]
    if s[1] > e[0]:
        notes.append("anchors_overlap")
    return FactsSpan(start=start, end=end, text=doc_text[start:end]), notes


# ---------------------------------------------------------------------------
# Windowing
# ---------------------------------------------------------------------------


def select_window(doc_text: str, max_doc_chars: int) -> tuple[str, bool]:
    """Return the text to send and whether it was truncated to the head window."""
    if len(doc_text) <= max_doc_chars:
        return doc_text, False
    cut = doc_text.rfind("\n", 0, max_doc_chars)
    if cut < max_doc_chars // 2:
        cut = max_doc_chars
    return doc_text[:cut], True


# ---------------------------------------------------------------------------
# Extractor
# ---------------------------------------------------------------------------


def estimate_cost_usd(model: str, usage: Any) -> float | None:
    p = PRICES_PER_MTOK.get(model)
    if p is None or usage is None:
        return None
    inp = float(getattr(usage, "input_tokens", 0) or 0)
    out = float(getattr(usage, "output_tokens", 0) or 0)
    cw = float(getattr(usage, "cache_creation_input_tokens", 0) or 0)
    cr = float(getattr(usage, "cache_read_input_tokens", 0) or 0)
    return round((inp * p["input"] + out * p["output"] + cw * p["input"] * 1.25 + cr * p["input"] * 0.1) / 1e6, 6)


BACKENDS = ("api", CLI_BACKEND)


@dataclass(frozen=True)
class LlmConfig:
    model: str = DEFAULT_MODEL
    backend: str = os.environ.get(
        "LEGALLM_LLM_BACKEND", "api"
    )  # "api" (Messages API) | "claude-cli" (headless claude -p)
    effort: str = "medium"  # low | medium | high | xhigh | max
    max_tokens: int = 8192
    max_doc_chars: int = 400_000  # ~100k tokens; head window beyond this
    timeout_s: float = 180.0
    max_retries: int = 3
    prompt_version: str = PROMPT_VERSION  # key into prompts.PROMPTS ("v1", "v2", ...)
    system_prompt: str | None = None  # override; default = PROMPTS[prompt_version]
    user_template: str | None = None

    @property
    def extractor_version(self) -> str:
        return f"llm-{self.prompt_version}"

    @property
    def resolved_system_prompt(self) -> str:
        if self.system_prompt is not None:
            return self.system_prompt
        return PROMPTS[self.prompt_version][0]

    @property
    def resolved_user_template(self) -> str:
        if self.user_template is not None:
            return self.user_template
        return PROMPTS[self.prompt_version][1]


class LlmExtractor:
    """Callable ``(doc_text, doc_type_id) -> FactsExtraction`` backed by the Claude API."""

    def __init__(self, config: LlmConfig | None = None, client: Any = None):
        self.config = config or LlmConfig()
        self._client = client
        self.schema = llm_output_json_schema()
        if self.config.prompt_version not in PROMPTS and self.config.system_prompt is None:
            raise LlmExtractionError(f"unknown prompt version {self.config.prompt_version!r}; known: {PROMPT_VERSIONS}")
        self.prompt_sha = hashlib.sha256(
            (
                self.config.resolved_system_prompt
                + "\n"
                + self.config.resolved_user_template
                + "\n"
                + json.dumps(self.schema, sort_keys=True)
            ).encode("utf-8")
        ).hexdigest()[:16]
        self._last_retries = 0

    @property
    def client(self) -> Any:
        if self._client is None and self.config.backend == CLI_BACKEND:
            self._client = ClaudeCliClient(timeout_s=max(self.config.timeout_s, 300.0))
        if self._client is None:
            if self.config.backend not in BACKENDS:
                raise LlmExtractionError(f"unknown backend {self.config.backend!r}; choose one of {BACKENDS}")
            import anthropic  # lazy: importing the package must not require credentials

            # Credential resolution is the SDK's: ANTHROPIC_API_KEY -> ANTHROPIC_AUTH_TOKEN -> `ant auth login`
            # OAuth profile -> WIF. Do not gate on env vars here or profile-based auth breaks.
            try:
                self._client = anthropic.Anthropic(timeout=self.config.timeout_s, max_retries=self.config.max_retries)
            except anthropic.AnthropicError as e:
                raise LlmExtractionError(
                    "no Anthropic credentials found: set ANTHROPIC_API_KEY, or run `ant auth login`"
                ) from e
        return self._client

    # -- request ----------------------------------------------------------
    def build_request(self, doc_text: str, doc_type_id: str) -> tuple[dict[str, Any], bool]:
        window, truncated = select_window(doc_text, self.config.max_doc_chars)
        user = self.config.resolved_user_template.format(
            doc_type_id=doc_type_id,
            n_chars=len(doc_text),
            truncated_attr=' truncated="true"' if truncated else "",
            document=window,
        )
        system_text = self.config.resolved_system_prompt
        req: dict[str, Any] = {
            "model": self.config.model,
            "max_tokens": self.config.max_tokens,
            "system": [{"type": "text", "text": system_text, "cache_control": {"type": "ephemeral"}}],
            "messages": [{"role": "user", "content": user}],
            "output_config": {"format": {"type": "json_schema", "schema": self.schema}, "effort": self.config.effort},
        }
        return req, truncated

    def _call(self, req: dict[str, Any]) -> Any:
        client = self.client
        self._last_retries = 0
        if isinstance(client, ClaudeCliClient):
            # L5 (taxonomy): the CLI occasionally returns is_error with no detail, or prose without the
            # structured-output call; both cleared on an immediate retry in the first 120-doc run.
            for attempt in range(2):
                try:
                    return client.messages.create(**req)
                except ClaudeCliError as e:
                    transient = "reported an error" in str(e) or "no structured_output" in str(e)
                    if attempt == 0 and transient:
                        self._last_retries += 1
                        continue
                    raise LlmExtractionError(f"claude-cli: {e}") from e

        import anthropic

        try:
            return client.messages.create(**req)
        except anthropic.AuthenticationError as e:
            raise LlmExtractionError(f"authentication failed ({e.status_code}): {e.message}") from e
        except anthropic.RateLimitError as e:  # SDK already retried
            raise LlmExtractionError(f"rate limited after retries: {e.message}") from e
        except anthropic.APIStatusError as e:
            raise LlmExtractionError(f"API error {e.status_code}: {e.message}") from e
        except anthropic.APIConnectionError as e:
            raise LlmExtractionError(f"connection error: {e}") from e

    # -- response ---------------------------------------------------------
    @staticmethod
    def _response_text(resp: Any) -> str:
        for block in getattr(resp, "content", []) or []:
            if getattr(block, "type", None) == "text":
                return str(block.text)
        return ""

    def __call__(self, doc_text: str, doc_type_id: str = "UNKNOWN") -> FactsExtraction:
        req, truncated = self.build_request(doc_text, doc_type_id)
        t0 = time.perf_counter()
        resp = self._call(req)
        latency = time.perf_counter() - t0

        provenance: dict[str, Any] = {
            "backend": self.config.backend,
            "model_id": getattr(resp, "model", self.config.model),
            "prompt_version": self.config.prompt_version,
            "prompt_sha": self.prompt_sha,
            "effort": self.config.effort,
            "stop_reason": getattr(resp, "stop_reason", None),
            "request_id": getattr(resp, "_request_id", None),
            "latency_s": round(latency, 3),
            "doc_chars": len(doc_text),
            "doc_truncated": truncated,
            "retries": self._last_retries,
        }
        usage = getattr(resp, "usage", None)
        if usage is not None:
            provenance.update(
                {
                    "input_tokens": getattr(usage, "input_tokens", None),
                    "output_tokens": getattr(usage, "output_tokens", None),
                    "cache_creation_input_tokens": getattr(usage, "cache_creation_input_tokens", None),
                    "cache_read_input_tokens": getattr(usage, "cache_read_input_tokens", None),
                    "cost_usd": estimate_cost_usd(self.config.model, usage),
                }
            )
        cli_meta = getattr(resp, "cli", None)
        if isinstance(cli_meta, dict):
            # Subscription-billed: cost_usd is the CLI's API-rate estimate, not an invoice line.
            provenance.update({"billing": "subscription", "cli": cli_meta})
            if cli_meta.get("total_cost_usd") is not None:
                provenance["cost_usd"] = cli_meta["total_cost_usd"]

        stop = provenance["stop_reason"]
        if stop == "refusal":
            details = getattr(resp, "stop_details", None)
            raise LlmExtractionError(f"model refused: {getattr(details, 'category', None)}")
        if stop == "max_tokens":
            raise LlmExtractionError("output truncated (max_tokens); raise LlmConfig.max_tokens")

        text = self._response_text(resp)
        try:
            raw = json.loads(text)
        except json.JSONDecodeError as e:
            raise LlmExtractionError(f"non-JSON model output: {e}") from e

        try:
            wire = LlmFactsOutput.model_validate(raw)
        except Exception as e:  # pydantic ValidationError
            raise LlmExtractionError(f"model output failed schema: {e}") from e

        notes = list(wire.notes)
        if truncated:
            notes.append("doc_truncated_to_window")
        # Keep the raw anchors so anchor failures can be diagnosed from the run cache.
        provenance["anchors"] = {
            "start": wire.facts_start_anchor,
            "end": wire.facts_end_anchor,
            "has_facts": wire.has_facts,
        }
        span: FactsSpan | None = None
        if wire.has_facts:
            span, loc_notes = locate_span(doc_text, wire.facts_start_anchor, wire.facts_end_anchor)
            notes.extend(loc_notes)
        else:
            notes.append("llm_no_facts")

        payload = {
            "facts_span": span.model_dump() if span else None,
            "parties": wire.parties,
            "procedural_posture": wire.procedural_posture,
            "key_events": [ev.model_dump() for ev in wire.key_events],
            "record_citations": wire.record_citations,
            "case_citations": wire.case_citations,
            "confidence": wire.confidence,
            "notes": notes,
            "provenance": provenance,
        }
        ex, errors = parse_payload(payload, extractor_version=self.config.extractor_version, doc_type_id=doc_type_id)
        if ex is None:
            raise LlmExtractionError("internal: assembled payload failed schema: " + "; ".join(errors))
        return ex


# ---------------------------------------------------------------------------
# Registry: one lazily-built extractor per prompt version, shared config overrides
# ---------------------------------------------------------------------------

_extractors: dict[str, LlmExtractor] = {}
_overrides: dict[str, Any] = {}


def method_version(method: str) -> str:
    """'llm-v2' -> 'v2'."""
    if not method.startswith("llm-"):
        raise KeyError(f"not an llm method: {method!r}")
    return method[4:]


def get_extractor(version: str = PROMPT_VERSION) -> LlmExtractor:
    """The shared extractor for a prompt version, built with the current overrides on first use."""
    if version not in PROMPT_VERSIONS:
        raise KeyError(f"unknown prompt version {version!r}; known: {PROMPT_VERSIONS}")
    if version not in _extractors:
        _extractors[version] = LlmExtractor(LlmConfig(prompt_version=version, **_overrides))
    return _extractors[version]


def default_extractor() -> LlmExtractor:
    return get_extractor(PROMPT_VERSION)


def configure_default(**overrides: Any) -> LlmExtractor:
    """Set config overrides (e.g. backend='claude-cli', effort='high') for every prompt version."""
    _overrides.clear()
    _overrides.update(overrides)
    _extractors.clear()
    return default_extractor()


def extract_llm(doc_text: str, doc_type_id: str = "UNKNOWN", *, version: str = PROMPT_VERSION) -> FactsExtraction:
    """Registry entry point: Sonnet 5 extractor at the given prompt version."""
    return get_extractor(version)(doc_text, doc_type_id)


def llm_method(version: str) -> Any:
    """Extractor callable ``(doc_text, doc_type_id)`` bound to one prompt version, for the method registry."""

    def _fn(doc_text: str, doc_type_id: str = "UNKNOWN") -> FactsExtraction:
        return extract_llm(doc_text, doc_type_id, version=version)

    _fn.__name__ = f"extract_llm_{version}"
    return _fn


_WORD = re.compile(r"\S+")


def anchor_preview(text: str, n_words: int = 12) -> str:
    """First ``n_words`` words of ``text`` (helper for logs/tests)."""
    return " ".join(_WORD.findall(text)[:n_words])

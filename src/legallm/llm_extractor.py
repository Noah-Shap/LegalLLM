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
import re
import time
from dataclasses import dataclass
from typing import Any

from legallm.prompts import FACTS_SYSTEM_V1, FACTS_USER_V1, PROMPT_VERSION
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


def locate_span(doc_text: str, start_anchor: str | None, end_anchor: str | None) -> tuple[FactsSpan | None, list[str]]:
    """Build a FactsSpan from the model's anchors; return (span_or_None, notes)."""
    notes: list[str] = []
    if not start_anchor or not end_anchor:
        return None, ["anchor_missing"]
    s = find_anchor(doc_text, start_anchor)
    if s is None:
        return None, ["start_anchor_not_found"]
    e = find_anchor(doc_text, end_anchor, start_at=s[0])
    if e is None:
        # End anchor may legitimately precede the start anchor's *end* if they overlap; try from doc start.
        e = find_anchor(doc_text, end_anchor)
        if e is None:
            return None, ["end_anchor_not_found"]
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


@dataclass(frozen=True)
class LlmConfig:
    model: str = DEFAULT_MODEL
    effort: str = "medium"  # low | medium | high | xhigh | max
    max_tokens: int = 8192
    max_doc_chars: int = 400_000  # ~100k tokens; head window beyond this
    timeout_s: float = 180.0
    max_retries: int = 3
    system_prompt: str = FACTS_SYSTEM_V1
    user_template: str = FACTS_USER_V1
    prompt_version: str = PROMPT_VERSION

    @property
    def extractor_version(self) -> str:
        return f"llm-{self.prompt_version}"


class LlmExtractor:
    """Callable ``(doc_text, doc_type_id) -> FactsExtraction`` backed by the Claude API."""

    def __init__(self, config: LlmConfig | None = None, client: Any = None):
        self.config = config or LlmConfig()
        self._client = client
        self.schema = llm_output_json_schema()
        self.prompt_sha = hashlib.sha256(
            (
                self.config.system_prompt
                + "\n"
                + self.config.user_template
                + "\n"
                + json.dumps(self.schema, sort_keys=True)
            ).encode("utf-8")
        ).hexdigest()[:16]

    @property
    def client(self) -> Any:
        if self._client is None:
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
        user = self.config.user_template.format(
            doc_type_id=doc_type_id,
            n_chars=len(doc_text),
            truncated_attr=' truncated="true"' if truncated else "",
            document=window,
        )
        req: dict[str, Any] = {
            "model": self.config.model,
            "max_tokens": self.config.max_tokens,
            "system": [{"type": "text", "text": self.config.system_prompt, "cache_control": {"type": "ephemeral"}}],
            "messages": [{"role": "user", "content": user}],
            "output_config": {"format": {"type": "json_schema", "schema": self.schema}, "effort": self.config.effort},
        }
        return req, truncated

    def _call(self, req: dict[str, Any]) -> Any:
        import anthropic

        try:
            return self.client.messages.create(**req)
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
            "model_id": getattr(resp, "model", self.config.model),
            "prompt_version": self.config.prompt_version,
            "prompt_sha": self.prompt_sha,
            "effort": self.config.effort,
            "stop_reason": getattr(resp, "stop_reason", None),
            "request_id": getattr(resp, "_request_id", None),
            "latency_s": round(latency, 3),
            "doc_chars": len(doc_text),
            "doc_truncated": truncated,
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


_default: LlmExtractor | None = None


def default_extractor() -> LlmExtractor:
    global _default
    if _default is None:
        _default = LlmExtractor()
    return _default


def extract_llm(doc_text: str, doc_type_id: str = "UNKNOWN") -> FactsExtraction:
    """Registry entry point: default Sonnet 5 extractor, prompt v1."""
    return default_extractor()(doc_text, doc_type_id)


_WORD = re.compile(r"\S+")


def anchor_preview(text: str, n_words: int = 12) -> str:
    """First ``n_words`` words of ``text`` (helper for logs/tests)."""
    return " ".join(_WORD.findall(text)[:n_words])

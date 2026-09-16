"""Routed extractor (item 11, ``llm-v3``): cheap tier first, strong tier only when the cheap pass fails.

Route: Sonnet 5 at prompt v2 (``llm-v2``) → deterministic checks → if a *trigger* fires, re-run the same
prompt on Opus 5 (D2's escalation tier, effort ``high``) and return that result. Triggers are the failure
classes the evals showed the cheap tier cannot recover on its own:

- ``anchor_not_found`` — the model said the document has a facts section but its anchors could not be
  located in the text (taxonomy L2; 8 of 120 gold docs on llm-v2). Empty span, no downstream value.
- ``span_text_mismatch`` / ``span_out_of_bounds`` — validator flags (never seen, cheap to check).
- ``error`` — the cheap call itself failed (transport error, refusal, schema failure).
- ``unsupported_citation`` — off by default: llm-v2 trips it on ~20 % of docs through list/range
  expansion (L3) and the judge rated those spans correct, so escalating would spend Opus on a citation
  formatting habit both tiers share.

A cheap-tier ``has_facts = false`` verdict is **not** escalated: the judge found those 100 % correct.

Provenance keeps both passes: ``provenance["routing"]`` records the trigger, the cheap pass's model /
prompt sha / cost / latency / notes, and whether escalation happened; ``cost_usd`` and ``latency_s`` are the
totals for the document, so the eval harness's cost-per-doc and latency rows reflect the whole route.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from legallm.llm_extractor import (
    DEFAULT_MODEL,
    LlmConfig,
    LlmExtractionError,
    LlmExtractor,
    current_overrides,
    get_extractor,
    plain_method_for,
)
from legallm.schema import FactsExtraction
from legallm.validators import validate_extraction

ROUTED_VERSION = "v3"
ROUTED_METHOD = f"llm-{ROUTED_VERSION}"
STRONG_MODEL = "claude-opus-5"
DEFAULT_TRIGGERS: tuple[str, ...] = ("anchor_not_found", "span_text_mismatch", "span_out_of_bounds", "error")
ALL_TRIGGERS: tuple[str, ...] = DEFAULT_TRIGGERS + ("unsupported_citation",)


@dataclass(frozen=True)
class RouteConfig:
    cheap_version: str = "v2"
    cheap_model: str = DEFAULT_MODEL
    strong_version: str = "v2"
    strong_model: str = STRONG_MODEL
    strong_effort: str = "high"
    triggers: tuple[str, ...] = DEFAULT_TRIGGERS
    backend: str | None = None  # None = follow configure_default() like the other llm-* methods
    extra: dict[str, Any] = field(default_factory=dict)  # further LlmConfig overrides for the strong tier

    @property
    def cheap_method(self) -> str:
        return plain_method_for(self.cheap_version)


# Routed methods -> configuration. llm-v3 = prompt v2 both tiers; llm-v5 = prompt v3 (structured record cites).
ROUTED_METHODS: dict[str, RouteConfig] = {
    "llm-v3": RouteConfig(cheap_version="v2", strong_version="v2"),
    "llm-v5": RouteConfig(cheap_version="v3", strong_version="v3"),
}


def trigger_for(extraction: FactsExtraction | None, doc_text: str, triggers: tuple[str, ...]) -> str | None:
    """The first configured trigger the cheap result fires, or None."""
    if extraction is None:
        return "error" if "error" in triggers else None
    notes = set(extraction.notes)
    anchors = (extraction.provenance or {}).get("anchors") or {}
    said_has_facts = bool(anchors.get("has_facts", extraction.facts_span is not None))
    if "anchor_not_found" in triggers and said_has_facts and extraction.facts_span is None:
        if notes & {"start_anchor_not_found", "end_anchor_not_found", "anchors_overlap"} or not notes & {
            "llm_no_facts"
        }:
            return "anchor_not_found"
    report = validate_extraction(extraction, doc_text, require_facts=False)
    for t in triggers:
        if t in ("anchor_not_found", "error"):
            continue
        if any(f == t or f.startswith(t + ":") for f in report.flags):
            return t
    return None


class Router:
    """Callable ``(doc_text, doc_type_id) -> FactsExtraction`` registered as ``llm-v3``."""

    cheap_method: str

    def __init__(
        self,
        config: RouteConfig | None = None,
        *,
        method: str = ROUTED_METHOD,
        cheap: LlmExtractor | None = None,
        strong: LlmExtractor | None = None,
    ):
        self.config = config or ROUTED_METHODS.get(method) or RouteConfig()
        self.method = method
        self.cheap_method = self.config.cheap_method
        self._cheap = cheap
        self._strong = strong

    @property
    def cheap(self) -> LlmExtractor:
        if self._cheap is None:
            self._cheap = get_extractor(self.config.cheap_version)
        return self._cheap

    @property
    def strong(self) -> LlmExtractor:
        if self._strong is None:
            overrides = dict(current_overrides())
            if self.config.backend is not None:
                overrides["backend"] = self.config.backend
            overrides.update(self.config.extra)
            overrides.update(
                {
                    "model": self.config.strong_model,
                    "effort": self.config.strong_effort,
                    "prompt_version": self.config.strong_version,
                }
            )
            self._strong = LlmExtractor(LlmConfig(**overrides))
        return self._strong

    @property
    def config_payload(self) -> str:
        """What changes this method's output (both tiers + triggers) — feeds the eval cache key."""
        c, s = self.cheap, self.strong
        return "|".join(
            [
                self.method,
                c.prompt_sha,
                c.config.model,
                c.config.effort,
                c.config.backend,
                s.prompt_sha,
                s.config.model,
                s.config.effort,
                s.config.backend,
                ",".join(self.config.triggers),
            ]
        )

    def route(
        self, doc_text: str, doc_type_id: str = "UNKNOWN", *, cheap: FactsExtraction | None = None
    ) -> FactsExtraction:
        """Run the route; ``cheap`` lets a caller supply an already-computed cheap-tier result."""
        cheap_error: str | None = None
        if cheap is None:
            try:
                cheap = self.cheap(doc_text, doc_type_id)
            except LlmExtractionError as e:
                cheap_error = f"{type(e).__name__}: {e}"
            except Exception as e:  # transport errors surface the same way as model errors
                cheap_error = f"{type(e).__name__}: {e}"
        trigger = trigger_for(cheap, doc_text, self.config.triggers)
        cheap_prov = (cheap.provenance if cheap is not None else None) or {}
        routing: dict[str, Any] = {
            "method": self.method,
            "trigger": trigger,
            "escalated": trigger is not None,
            "cheap": {
                "model_id": cheap_prov.get("model_id", self.config.cheap_model),
                "prompt_sha": cheap_prov.get("prompt_sha"),
                "cost_usd": cheap_prov.get("cost_usd"),
                "latency_s": cheap_prov.get("latency_s"),
                "notes": list(cheap.notes) if cheap is not None else [],
                "error": cheap_error,
                "span": [cheap.facts_span.start, cheap.facts_span.end]
                if cheap is not None and cheap.facts_span
                else None,
            },
        }
        if trigger is None:
            if cheap is None:  # cheap failed and "error" is not a configured trigger
                raise LlmExtractionError(f"cheap tier failed and escalation is not enabled for errors: {cheap_error}")
            return self._finish(cheap, routing, tier="cheap")

        try:
            strong = self.strong(doc_text, doc_type_id)
        except Exception as e:
            routing["escalation_error"] = f"{type(e).__name__}: {e}"
            if cheap is None:
                raise LlmExtractionError(f"cheap tier failed ({cheap_error}); strong tier failed ({e})") from e
            return self._finish(cheap, routing, tier="cheap")
        routing["strong"] = {
            "model_id": (strong.provenance or {}).get("model_id", self.config.strong_model),
            "prompt_sha": (strong.provenance or {}).get("prompt_sha"),
            "cost_usd": (strong.provenance or {}).get("cost_usd"),
            "latency_s": (strong.provenance or {}).get("latency_s"),
            "notes": list(strong.notes),
            "span": [strong.facts_span.start, strong.facts_span.end] if strong.facts_span else None,
        }
        routing["strong_recovered"] = strong.facts_span is not None or "llm_no_facts" in strong.notes
        return self._finish(strong, routing, tier="strong")

    def _finish(self, ex: FactsExtraction, routing: dict[str, Any], *, tier: str) -> FactsExtraction:
        prov = dict(ex.provenance or {})
        cheap_cost = routing["cheap"].get("cost_usd") or 0.0
        cheap_lat = routing["cheap"].get("latency_s") or 0.0
        if tier == "strong":
            if prov.get("cost_usd") is not None or cheap_cost:
                prov["cost_usd"] = round((prov.get("cost_usd") or 0.0) + cheap_cost, 6)
            prov["latency_s"] = round((prov.get("latency_s") or 0.0) + cheap_lat, 3)
        prov["tier"] = tier
        prov["routing"] = routing
        notes = list(ex.notes)
        notes.append(f"routed:{tier}" + (f":{routing['trigger']}" if routing["trigger"] else ""))
        return ex.model_copy(update={"extractor_version": self.method, "provenance": prov, "notes": notes})

    def __call__(self, doc_text: str, doc_type_id: str = "UNKNOWN") -> FactsExtraction:
        return self.route(doc_text, doc_type_id)


_routers: dict[str, Router] = {}


def get_router(method: str = ROUTED_METHOD, config: RouteConfig | None = None) -> Router:
    """The shared router for a routed method (rebuilt when a config is passed or after ``configure_default``)."""
    if config is not None or method not in _routers:
        if config is None and method not in ROUTED_METHODS:
            raise KeyError(f"unknown routed method {method!r}; known: {sorted(ROUTED_METHODS)}")
        _routers[method] = Router(config, method=method)
    return _routers[method]


def reset_router() -> None:
    _routers.clear()


def routed_method(method: str = ROUTED_METHOD) -> Any:
    """Registry callable for a routed method that always resolves the current shared router."""

    def _fn(doc_text: str, doc_type_id: str = "UNKNOWN") -> FactsExtraction:
        return get_router(method)(doc_text, doc_type_id)

    _fn.__name__ = f"extract_{method.replace('-', '_')}"
    return _fn

"""FactsExtraction schema (intent.md §5, C1).

One versioned Pydantic model shared by every extractor (rules_v2 baseline, LLM
extractors) and by the validators, eval harness, API, and UI. Offsets in
``facts_span`` are character offsets into the *document text handed to the
extractor* (see ``legallm.baseline_adapter.preprocess_text``).
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

SCHEMA_VERSION = "1.0"

Confidence = Literal["high", "medium", "low"]


class FactsSpan(BaseModel):
    """A contiguous character span of the document text."""

    model_config = ConfigDict(extra="forbid")

    start: int = Field(ge=0, description="Start character offset (inclusive) into the document text.")
    end: int = Field(ge=0, description="End character offset (exclusive) into the document text.")
    text: str = Field(description="Exact substring document_text[start:end].")

    @model_validator(mode="after")
    def _check_order(self) -> FactsSpan:
        if self.end < self.start:
            raise ValueError("facts_span.end must be >= facts_span.start")
        return self

    @property
    def length(self) -> int:
        return self.end - self.start


class KeyEvent(BaseModel):
    """A dated (or undated) event from the factual narrative."""

    model_config = ConfigDict(extra="forbid")

    date: str | None = Field(
        default=None,
        description="Date as stated in the brief, normalised to YYYY, YYYY-MM, or YYYY-MM-DD when possible.",
    )
    text: str = Field(min_length=1, description="One-sentence description of the event.")


class FactsExtraction(BaseModel):
    """Structured output of a facts extractor for one brief."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(default=SCHEMA_VERSION, description="Schema version this object conforms to.")
    extractor_version: str = Field(description='Producer identifier, e.g. "rules_v2" or "llm-v1".')
    confidence: Confidence = Field(description="Extractor's own confidence in the facts span.")
    facts_span: FactsSpan | None = Field(default=None, description="The facts section, or null if none was found.")
    parties: list[str] = Field(default_factory=list, description="Named parties to the case.")
    procedural_posture: str | None = Field(
        default=None, description="How the case reached this court (e.g. appeal from summary judgment)."
    )
    key_events: list[KeyEvent] = Field(default_factory=list, description="Key factual events, in document order.")
    record_citations: list[str] = Field(
        default_factory=list, description="Record cites appearing verbatim in the facts (e.g. '1-ER-102', 'R. 45')."
    )
    case_citations: list[str] = Field(
        default_factory=list, description="Case citations appearing verbatim in the facts (e.g. '500 U.S. 100')."
    )
    notes: list[str] = Field(default_factory=list, description="Diagnostic notes / quality flags from the extractor.")
    doc_type_id: str = Field(default="UNKNOWN", description="Document type id used for extraction policy.")

    @property
    def facts_text(self) -> str:
        return self.facts_span.text if self.facts_span is not None else ""

    @property
    def has_facts(self) -> bool:
        return self.facts_span is not None and bool(self.facts_span.text.strip())

    def to_json(self, indent: int | None = 2) -> str:
        return str(self.model_dump_json(indent=indent))


# Fields an LLM extractor is expected to fill; the caller sets the rest.
LLM_OUTPUT_FIELDS: tuple[str, ...] = (
    "facts_span",
    "parties",
    "procedural_posture",
    "key_events",
    "record_citations",
    "case_citations",
    "confidence",
    "notes",
)


def llm_output_json_schema() -> dict[str, Any]:
    """JSON schema for the model-filled subset of ``FactsExtraction``.

    Intended for tool-call / structured-output definitions (C2). Producer-owned
    fields (``schema_version``, ``extractor_version``, ``doc_type_id``) are excluded
    so the model cannot claim a version.
    """
    full = FactsExtraction.model_json_schema()
    props = {k: v for k, v in full["properties"].items() if k in LLM_OUTPUT_FIELDS}
    return {
        "type": "object",
        "properties": props,
        "required": list(LLM_OUTPUT_FIELDS),
        "additionalProperties": False,
        "$defs": full.get("$defs", {}),
    }

"""Baseline adapter: rules_v2 facts extractor → FactsExtraction (intent.md §5, C3).

The rule-based extractor is frozen as the baseline the LLM must beat. This
module only re-shapes its output into the shared schema.

Text contract
-------------
``extract_facts_span`` returns offsets into a *preprocessed* copy of the text
(PACER headers stripped, roman-numeral heading lines merged). To make offsets
from every extractor comparable, callers preprocess once with
``preprocess_text`` and pass that ``doc_text`` to every extractor. Preprocessing
is idempotent, so the rules extractor's internal pass is a no-op on it.
"""

from __future__ import annotations

from legallm.citation_extractor import extract_citations
from legallm.facts_extractor import extract_facts_span, merge_roman_heading_lines, strip_pacer_headers
from legallm.schema import FactsExtraction, FactsSpan

RULES_VERSION = "rules_v2"


def preprocess_text(clean: str, *, max_passes: int = 4) -> str:
    """Apply the extractor's preprocessing to normalised text until it reaches a fixed point.

    A single pass is not always idempotent (a handful of real PDFs lose one trailing
    character on the second pass), and the offset contract requires that the rules
    extractor's internal pass be a no-op on the text it is given.
    """
    text = clean
    for _ in range(max_passes):
        nxt = merge_roman_heading_lines(strip_pacer_headers(text))
        if nxt == text:
            return text
        text = nxt
    return text


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for it in items:
        if it not in seen:
            seen.add(it)
            out.append(it)
    return out


def extract_rules(doc_text: str, doc_type_id: str = "UNKNOWN") -> FactsExtraction:
    """Run rules_v2 on preprocessed ``doc_text`` and return a FactsExtraction.

    Filled fields: ``facts_span``, ``confidence``, ``notes`` (extractor notes +
    quality-gate flags), ``case_citations`` (regex extractor, verbatim strings).
    ``parties``, ``procedural_posture``, ``key_events`` and ``record_citations``
    are left empty — the baseline does not produce them.
    """
    span, meta = extract_facts_span(doc_text, doc_type_id=doc_type_id)
    source: str = meta.get("preprocessed_text", doc_text)
    notes: list[str] = list(meta.get("notes", []))
    if source != doc_text:
        # Should not happen (preprocessing is idempotent); flag so offsets are not trusted silently.
        notes.append("preprocessing_not_idempotent")

    facts_span: FactsSpan | None = None
    case_cites: list[str] = []
    if span is not None:
        a, b = span
        text = source[a:b]
        facts_span = FactsSpan(start=a, end=b, text=text)
        case_cites = _dedupe([c.original_text for c in extract_citations(text).case_citations])

    return FactsExtraction(
        extractor_version=RULES_VERSION,
        confidence=meta.get("confidence", "low"),
        facts_span=facts_span,
        case_citations=case_cites,
        notes=notes,
        doc_type_id=doc_type_id,
    )

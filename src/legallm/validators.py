"""Deterministic validators for FactsExtraction objects (intent.md §5, C4).

Checks (all pure, no network):
  schema_valid        payload parses as FactsExtraction (see ``parse_payload``)
  span_in_bounds      0 <= start <= end <= len(doc_text)
  span_text_matches   facts_span.text == doc_text[start:end]
  facts_nonempty      a non-empty facts span exists (when required)
  citation_fidelity   every emitted case/record citation is supported by doc_text: verbatim (ignoring
                      whitespace, hyphens/dashes and quote glyphs) or component-supported (list/range
                      shorthand the model expanded: every number printed near the same prefix) — the
                      anti-hallucination gate. Both rates are reported; only 'unsupported' fails.
  dates_parseable     every key_events[].date parses with an accepted format

Flags are stable strings so the eval harness can count them (C6/C8).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from pydantic import ValidationError

from legallm.schema import FactsExtraction

_WS = re.compile(r"\s+")

_DATE_FORMATS: tuple[str, ...] = (
    "%Y-%m-%d",
    "%Y-%m",
    "%Y",
    "%B %d, %Y",
    "%b. %d, %Y",
    "%b %d, %Y",
    "%B %Y",
    "%b. %Y",
    "%b %Y",
    "%m/%d/%Y",
    "%m/%d/%y",
)


def squash_ws(s: str) -> str:
    """Collapse all whitespace runs to a single space and strip."""
    return _WS.sub(" ", s).strip()


def parse_date(s: str | None) -> bool:
    """Return True if ``s`` matches one of the accepted date formats."""
    if s is None:
        return True
    s = s.strip()
    if not s:
        return False
    for fmt in _DATE_FORMATS:
        try:
            datetime.strptime(s, fmt)
            return True
        except ValueError:
            continue
    return False


_DASH_QUOTE_MAP = str.maketrans({"‘": "'", "’": "'", "“": '"', "”": '"', "–": "-", "—": "-", "‑": "-"})


def cite_key(s: str) -> str:
    """Canonical form for citation fidelity: no whitespace, no hyphens/dashes, ASCII quotes.

    PDF text carries hyphen-break artifacts ("1- ER-102"), typographic dashes
    ("1-ER-106–07") and dropped hyphens ("9-ER2042", "5ER-862"); a model that writes
    the canonical "9-ER-2042" has still copied the cite. Letters, digits and their
    order are unchanged, so this stays a verbatim test: "1-ER-107" does not match
    "1-ER-106-07", and a wrong pincite ("1425" vs "1426") is still caught.
    """
    return _WS.sub("", s.translate(_DASH_QUOTE_MAP)).replace("-", "")


def citation_supported(cite: str, doc_text_key: str) -> bool:
    """True if ``cite`` occurs in the document text modulo whitespace and dash/quote glyphs.

    ``doc_text_key`` must be ``cite_key(doc_text)``.
    """
    c = cite_key(cite)
    return bool(c) and c in doc_text_key


_NUM = re.compile(r"\d+")
# prefix = everything before the trailing run of page numbers ("5-ER-", "776 F. Supp. ", "App.", "Tr. ")
_SPLIT = re.compile(r"^(?P<prefix>.*?[^\d\s])\s*(?P<pages>\d+(?:\s*[-–—,;]\s*\d+)*)\s*$")
COMPONENT_WINDOW = 800  # chars (of cite_key text) after a prefix occurrence within which the page numbers must appear


def _split_cite(cite: str) -> tuple[str, list[str]]:
    m = _SPLIT.match(cite.strip())
    if not m:
        return "", []
    return cite_key(m.group("prefix")).rstrip(".,;:"), _NUM.findall(m.group("pages"))


def _hyphen_key(s: str) -> str:
    """Like cite_key but keeps hyphens, so page ranges stay separable ("969-970", not "969970")."""
    return _WS.sub("", s.translate(_DASH_QUOTE_MAP))


def _prefix_regex(prefix_key: str) -> re.Pattern[str]:
    """Match the hyphen-less prefix key against hyphen-keeping text, allowing a '-' between any two chars."""
    return re.compile("-?".join(re.escape(ch) for ch in prefix_key))


def citation_components_supported(cite: str, doc_text: str) -> bool:
    """Semantic fallback for list/range-form cites the source prints once and the model expands.

    ``App.1494, 1503, 1515`` in the source yields model output ``App.1503``; ``5-ER-965, ¶ 25;
    969-970`` yields ``5-ER-969-970``; ``Tr. 650, 654-59, ...`` yields ``Tr. 654-59``. Such a cite is
    *component-supported* when its prefix (everything before the trailing page numbers:
    ``App.``, ``5-ER-``, ``776 F. Supp.``, ``Tr.``) occurs in the source and every page number
    occurs, as a whole number, within ``COMPONENT_WINDOW`` characters after some occurrence of
    that prefix. A wrong pincite (``1425`` for ``1426``) or an expanded range (``1-ER-107`` from
    ``1-ER-106–07``) still fails, because that number is not printed near the prefix.
    """
    prefix, pages = _split_cite(cite)
    if not prefix or not pages:
        return False
    text = _hyphen_key(doc_text)
    pats = [re.compile(rf"(?<!\d){re.escape(p)}(?!\d)") for p in pages]
    for m in _prefix_regex(prefix).finditer(text):
        window = text[m.start() : m.start() + COMPONENT_WINDOW]
        if all(p.search(window) for p in pats):
            return True
    return False


def citation_support_level(cite: str, doc_text: str, doc_text_key: str | None = None) -> str:
    """'verbatim' | 'components' | 'unsupported'."""
    key = doc_text_key if doc_text_key is not None else cite_key(doc_text)
    if citation_supported(cite, key):
        return "verbatim"
    if citation_components_supported(cite, doc_text):
        return "components"
    return "unsupported"


@dataclass
class ValidationReport:
    """Outcome of ``validate_extraction``."""

    ok: bool
    flags: list[str] = field(default_factory=list)
    checks: dict[str, bool] = field(default_factory=dict)
    citation_fidelity: float | None = None  # fraction of emitted citations found verbatim; None if none emitted
    citation_support: float | None = None  # fraction found verbatim OR component-supported; None if none emitted
    n_citations: int = 0
    n_unsupported_citations: int = 0  # neither verbatim nor component-supported (the failure count)
    n_nonverbatim_citations: int = 0  # component-supported only (list/range expansion)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "flags": list(self.flags),
            "checks": dict(self.checks),
            "citation_fidelity": self.citation_fidelity,
            "citation_support": self.citation_support,
            "n_citations": self.n_citations,
            "n_unsupported_citations": self.n_unsupported_citations,
            "n_nonverbatim_citations": self.n_nonverbatim_citations,
        }


def parse_payload(
    payload: dict[str, Any],
    *,
    extractor_version: str,
    doc_type_id: str = "UNKNOWN",
) -> tuple[FactsExtraction | None, list[str]]:
    """Schema-validate a raw dict (e.g. an LLM tool-call output).

    Producer-owned fields are overwritten from the arguments. Returns
    ``(model, [])`` on success or ``(None, [error strings])`` on failure.
    """
    data = dict(payload)
    data["extractor_version"] = extractor_version
    data["doc_type_id"] = doc_type_id
    data.pop("schema_version", None)
    try:
        return FactsExtraction.model_validate(data), []
    except ValidationError as e:
        errors = [f"{'.'.join(str(p) for p in err['loc'])}: {err['msg']}" for err in e.errors()]
        return None, errors


def validate_extraction(
    extraction: FactsExtraction,
    doc_text: str,
    *,
    require_facts: bool = True,
) -> ValidationReport:
    """Run all deterministic checks against the document text the offsets refer to."""
    flags: list[str] = []
    checks: dict[str, bool] = {}
    span = extraction.facts_span
    n = len(doc_text)

    # span_in_bounds / span_text_matches
    if span is None:
        checks["span_in_bounds"] = True
        checks["span_text_matches"] = True
    else:
        in_bounds = 0 <= span.start <= span.end <= n
        checks["span_in_bounds"] = in_bounds
        if not in_bounds:
            flags.append("span_out_of_bounds")
        matches = in_bounds and doc_text[span.start : span.end] == span.text
        checks["span_text_matches"] = matches
        if in_bounds and not matches:
            flags.append("span_text_mismatch")

    # facts_nonempty
    nonempty = extraction.has_facts
    checks["facts_nonempty"] = nonempty or not require_facts
    if require_facts and not nonempty:
        flags.append("empty_facts")

    # citation_fidelity (verbatim) and citation_support (verbatim or component-supported)
    doc_key = cite_key(doc_text)
    cites = list(extraction.case_citations) + list(extraction.record_citations)
    levels = {c: citation_support_level(c, doc_text, doc_key) for c in cites}
    unsupported = [c for c in cites if levels[c] == "unsupported"]
    nonverbatim = [c for c in cites if levels[c] == "components"]
    checks["citation_fidelity"] = not unsupported
    for c in unsupported:
        flags.append(f"unsupported_citation:{squash_ws(c)[:80]}")
    for c in nonverbatim:
        flags.append(f"nonverbatim_citation:{squash_ws(c)[:80]}")
    fidelity = None if not cites else (len(cites) - len(unsupported) - len(nonverbatim)) / len(cites)
    support = None if not cites else (len(cites) - len(unsupported)) / len(cites)

    # dates_parseable
    bad_dates = [ev.date for ev in extraction.key_events if ev.date is not None and not parse_date(ev.date)]
    checks["dates_parseable"] = not bad_dates
    for d in bad_dates:
        flags.append(f"unparseable_date:{d[:40]}")

    return ValidationReport(
        ok=all(checks.values()),
        flags=flags,
        checks=checks,
        citation_fidelity=fidelity,
        citation_support=support,
        n_citations=len(cites),
        n_unsupported_citations=len(unsupported),
        n_nonverbatim_citations=len(nonverbatim),
    )

"""Citation extraction and normalization from legal text.

Extracts case citations from text, normalizes them to a canonical form,
and provides masking functionality for leakage prevention.

Phase-1 scope: case citations only (statutes, regulations, secondary sources
are extracted for auditing but excluded from labels).

Reference: approved_spec_package_v0_2.md §Citation targets
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

# ---------------------------------------------------------------------------
# Citation patterns
# ---------------------------------------------------------------------------

# Standard case citation: volume reporter page (year)
# e.g., "500 U.S. 100 (1990)", "123 F.3d 456", "789 F. Supp. 2d 100"
#
# Reporter pattern is built as a flat alternation to avoid nested group issues.
_REPORTERS = [
    # Federal - high priority
    r"U\.S\.",
    r"S\.\s*Ct\.",
    r"L\.\s*Ed\.\s*2d",
    r"L\.\s*Ed\.",
    r"F\.\s*Supp\.\s*\d[a-z]{1,2}",
    r"F\.\s*Supp\.",
    r"F\.\s*App'x",
    r"F\.\s*\d[a-z]{1,2}",
    r"F\.",
    r"B\.R\.",
    # Regional reporters
    r"A\.\s*\d[a-z]{1,2}",
    r"A\.",
    r"N\.E\.\s*\d[a-z]{1,2}",
    r"N\.E\.",
    r"N\.W\.\s*\d[a-z]{1,2}",
    r"N\.W\.",
    r"P\.\s*\d[a-z]{1,2}",
    r"P\.",
    r"S\.E\.\s*\d[a-z]{1,2}",
    r"S\.E\.",
    r"S\.W\.\s*\d[a-z]{1,2}",
    r"S\.W\.",
    r"So\.\s*\d[a-z]{1,2}",
    r"So\.",
    # State-specific
    r"Cal\.\s*Rptr\.\s*\d[a-z]{1,2}",
    r"Cal\.\s*Rptr\.",
    r"Cal\.\s*App\.\s*\d[a-z]{1,2}",
    r"Cal\.\s*App\.",
    r"N\.Y\.S\.\s*\d[a-z]{1,2}",
    r"N\.Y\.S\.",
    r"N\.Y\.\s*\d[a-z]{1,2}",
    r"N\.Y\.",
    r"Ill\.\s*\d[a-z]{1,2}",
    r"Ill\.",
    # Bankruptcy
    r"Bankr\.",
    # Generic fallback (must be last — matches any "Abbr." pattern)
    r"[A-Z][A-Za-z]*\.\s*\d[a-z]{1,2}",
    r"[A-Z][A-Za-z]*\.",
]
_REPORTER_PATTERN = "|".join(_REPORTERS)

# Full case citation pattern: volume reporter page
RE_FULL_CASE_CITE = re.compile(
    r"(?P<volume>\d{1,4})"
    r"\s+"
    r"(?P<reporter>" + _REPORTER_PATTERN + r")"
    r"\s+"
    r"(?P<page>\d{1,5})"
    r"(?:,?\s+\d{1,5})?"  # optional pincite
    r"(?:\s*\((?P<court_year>[^)]*\d{4}[^)]*)\))?"  # optional (court year)
)

# Case name pattern: "Party v. Party" preceding a citation
# Captures the most common forms. The "v." is the anchor.
RE_CASE_NAME = re.compile(
    r"""
    (?P<case_name>
        (?:(?:In\s+re|Ex\s+parte)\s+)?     # optional "In re" / "Ex parte"
        [A-Z][A-Za-z''.\-]+                 # first party (starts uppercase)
        (?:\s+[A-Za-z''.\-]+){0,5}          # additional name words
        \s+v\.?\s+                           # "v." or "v"
        [A-Z][A-Za-z''.\-]+                 # second party
        (?:\s+[A-Za-z''.\-]+){0,5}          # additional name words
    )
    \s*,?\s*                                 # separator before citation
    """,
    re.VERBOSE,
)

# Short-form citations: Id., Ibid., supra, infra
RE_SHORT_FORM = re.compile(
    r"\b(?:Id\.|Ibid\.|[Ss]upra|[Ii]nfra)"
    r"(?:\s+at\s+\d{1,5})?"  # optional pincite
)

# Statute pattern (for auditing, excluded from Phase-1 labels)
RE_STATUTE = re.compile(r"\b\d{1,3}\s+(?:U\.S\.C|C\.F\.R|Fed\.\s*R\.\s*(?:Civ|Crim|App|Evid)\.\s*P)\.\s*§?\s*\d+")

# Secondary source pattern (for auditing)
RE_SECONDARY = re.compile(r"\b\d{1,3}\s+(?:Am\.\s*Jur\.|C\.J\.S\.|A\.L\.R\.)")


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class ExtractedCitation:
    """A single citation extracted from text."""

    original_text: str  # exact text as found
    start: int  # character offset in source text
    end: int  # character offset in source text
    target_type: str  # "case" | "statute" | "regulation" | "secondary" | "short_form" | "unknown"
    volume: str | None = None
    reporter: str | None = None
    page: str | None = None
    court_year: str | None = None
    case_name: str | None = None
    normalized: str | None = None  # canonical form: "volume reporter page"
    resolution_status: str = "unresolved"  # "resolved" | "unresolved" | "excluded"
    resolved_id: str | None = None
    resolved_source: str | None = None
    excluded_reason: str | None = None
    confidence: float | None = None


@dataclass
class CitationExtractionResult:
    """Result of citation extraction from a text span."""

    citations: list[ExtractedCitation] = field(default_factory=list)
    case_citations: list[ExtractedCitation] = field(default_factory=list)
    short_form_count: int = 0
    statute_count: int = 0
    secondary_count: int = 0


# ---------------------------------------------------------------------------
# Normalization
# ---------------------------------------------------------------------------


def _normalize_reporter(reporter: str) -> str:
    """Normalize reporter abbreviation to a canonical form."""
    # Collapse internal whitespace
    r = re.sub(r"\s+", " ", reporter.strip())
    # Common normalizations
    r = r.replace("S. Ct.", "S.Ct.")
    r = r.replace("L. Ed.", "L.Ed.")
    r = r.replace("L. Ed. 2d", "L.Ed.2d")
    r = r.replace("F. 2d", "F.2d")
    r = r.replace("F. 3d", "F.3d")
    r = r.replace("F. Supp. 2d", "F.Supp.2d")
    r = r.replace("F. Supp. 3d", "F.Supp.3d")
    r = r.replace("F.Supp. 2d", "F.Supp.2d")
    r = r.replace("F.Supp. 3d", "F.Supp.3d")
    r = r.replace("F. Supp.", "F.Supp.")
    r = r.replace("F. App'x", "F.App'x")
    r = r.replace("A. 2d", "A.2d")
    r = r.replace("A. 3d", "A.3d")
    r = r.replace("N.E. 2d", "N.E.2d")
    r = r.replace("N.E. 3d", "N.E.3d")
    r = r.replace("N.W. 2d", "N.W.2d")
    r = r.replace("P. 2d", "P.2d")
    r = r.replace("P. 3d", "P.3d")
    r = r.replace("S.E. 2d", "S.E.2d")
    r = r.replace("S.W. 2d", "S.W.2d")
    r = r.replace("S.W. 3d", "S.W.3d")
    r = r.replace("So. 2d", "So.2d")
    r = r.replace("So. 3d", "So.3d")
    r = r.replace("N.Y.S. 2d", "N.Y.S.2d")
    r = r.replace("N.Y.S. 3d", "N.Y.S.3d")
    r = r.replace("Cal. Rptr.", "Cal.Rptr.")
    r = r.replace("Cal. Rptr. 2d", "Cal.Rptr.2d")
    r = r.replace("Cal. Rptr. 3d", "Cal.Rptr.3d")
    r = r.replace("Cal. App.", "Cal.App.")
    return r


def normalize_citation(volume: str, reporter: str, page: str) -> str:
    """Produce a canonical citation string: 'volume reporter page'."""
    return f"{volume} {_normalize_reporter(reporter)} {page}"


# ---------------------------------------------------------------------------
# Extraction
# ---------------------------------------------------------------------------


def _try_extract_case_name(text: str, cite_start: int) -> str | None:
    """Look backward from a citation to find the case name (Party v. Party)."""
    # Search in the 200 chars before the citation
    window_start = max(0, cite_start - 200)
    window = text[window_start:cite_start]
    # Find the last "v." pattern
    matches = list(RE_CASE_NAME.finditer(window))
    if matches:
        return matches[-1].group("case_name").strip()
    return None


def extract_citations(text: str) -> CitationExtractionResult:
    """Extract all citations from a text span.

    Returns structured citation objects with type classification.
    Case citations are normalized; short-form, statute, and secondary
    citations are extracted for auditing but excluded from Phase-1 labels.
    """
    result = CitationExtractionResult()

    # 1) Extract full case citations
    seen_positions: set[tuple[int, int]] = set()
    for m in RE_FULL_CASE_CITE.finditer(text):
        volume = m.group("volume")
        reporter = m.group("reporter")
        page = m.group("page")
        court_year = m.group("court_year")

        case_name = _try_extract_case_name(text, m.start())

        cite = ExtractedCitation(
            original_text=m.group().strip(),
            start=m.start(),
            end=m.end(),
            target_type="case",
            volume=volume,
            reporter=reporter,
            page=page,
            court_year=court_year.strip() if court_year else None,
            case_name=case_name,
            normalized=normalize_citation(volume, reporter, page),
        )
        result.citations.append(cite)
        result.case_citations.append(cite)
        seen_positions.add((m.start(), m.end()))

    # 2) Extract short-form citations (excluded from Phase-1 labels)
    for m in RE_SHORT_FORM.finditer(text):
        if any(m.start() >= s and m.end() <= e for s, e in seen_positions):
            continue
        cite = ExtractedCitation(
            original_text=m.group().strip(),
            start=m.start(),
            end=m.end(),
            target_type="short_form",
            excluded_reason="context_dependent_short_form",
            resolution_status="excluded",
        )
        result.citations.append(cite)
        result.short_form_count += 1

    # 3) Extract statute references (excluded from Phase-1 labels)
    for m in RE_STATUTE.finditer(text):
        if any(m.start() >= s and m.end() <= e for s, e in seen_positions):
            continue
        cite = ExtractedCitation(
            original_text=m.group().strip(),
            start=m.start(),
            end=m.end(),
            target_type="statute",
            excluded_reason="non_case_reference",
            resolution_status="excluded",
        )
        result.citations.append(cite)
        result.statute_count += 1

    # 4) Extract secondary source references (excluded from Phase-1 labels)
    for m in RE_SECONDARY.finditer(text):
        if any(m.start() >= s and m.end() <= e for s, e in seen_positions):
            continue
        cite = ExtractedCitation(
            original_text=m.group().strip(),
            start=m.start(),
            end=m.end(),
            target_type="secondary",
            excluded_reason="non_case_reference",
            resolution_status="excluded",
        )
        result.citations.append(cite)
        result.secondary_count += 1

    # Sort all citations by position
    result.citations.sort(key=lambda c: c.start)

    return result


# ---------------------------------------------------------------------------
# Deduplication (parallel citation collapsing)
# ---------------------------------------------------------------------------


def deduplicate_case_citations(
    citations: list[ExtractedCitation],
) -> list[ExtractedCitation]:
    """Collapse parallel citations to the same case into a single canonical entry.

    Parallel citations are identified by matching case names. When multiple
    citations share the same case name (fuzzy), the one with the highest-priority
    reporter is kept as the canonical entry.
    """
    if not citations:
        return []

    # Reporter priority: U.S. > S.Ct. > L.Ed. > F.3d > F.2d > F.Supp > state
    _PRIORITY = {
        "U.S.": 0,
        "S.Ct.": 1,
        "L.Ed.": 2,
        "L.Ed.2d": 2,
        "F.3d": 3,
        "F.2d": 4,
        "F.Supp.3d": 5,
        "F.Supp.2d": 5,
        "F.Supp.": 5,
    }

    def _reporter_priority(cite: ExtractedCitation) -> int:
        if cite.reporter:
            norm = _normalize_reporter(cite.reporter)
            return _PRIORITY.get(norm, 10)
        return 99

    # Group by normalized citation string (exact dedup)
    seen_normalized: dict[str, ExtractedCitation] = {}
    unique: list[ExtractedCitation] = []

    for cite in citations:
        key = cite.normalized or cite.original_text
        if key in seen_normalized:
            # Keep the one with better reporter priority
            existing = seen_normalized[key]
            if _reporter_priority(cite) < _reporter_priority(existing):
                seen_normalized[key] = cite
                unique = [c for c in unique if (c.normalized or c.original_text) != key]
                unique.append(cite)
        else:
            seen_normalized[key] = cite
            unique.append(cite)

    return unique


# ---------------------------------------------------------------------------
# Citation masking
# ---------------------------------------------------------------------------


def mask_citations(text: str, replacement: str = "[CITATION]") -> str:
    """Replace all case citations in text with a placeholder token.

    Used to prevent citation leakage in model input (facts_text_masked).
    Masks formal citations (volume reporter page) and case name + citation
    combinations. Does NOT mask bare case name references like "the Smith court"
    (Phase-1 scope: formal citations only).
    """
    # Build list of spans to mask (case citations only, not statutes/secondary)
    spans: list[tuple[int, int]] = []

    for m in RE_FULL_CASE_CITE.finditer(text):
        start = m.start()
        end = m.end()

        # Extend backward to include case name if present
        case_name = _try_extract_case_name(text, start)
        if case_name:
            # Find where the case name starts in the text before the citation
            name_search_start = max(0, start - 200)
            window = text[name_search_start:start]
            name_idx = window.rfind(case_name)
            if name_idx >= 0:
                start = name_search_start + name_idx

        spans.append((start, end))

    # Also mask short-form references (Id., supra, etc.)
    for m in RE_SHORT_FORM.finditer(text):
        # Don't double-mask if already covered by a full citation span
        if not any(s <= m.start() and m.end() <= e for s, e in spans):
            spans.append((m.start(), m.end()))

    if not spans:
        return text

    # Merge overlapping spans
    spans.sort()
    merged: list[tuple[int, int]] = [spans[0]]
    for s, e in spans[1:]:
        if s <= merged[-1][1] + 1:
            merged[-1] = (merged[-1][0], max(merged[-1][1], e))
        else:
            merged.append((s, e))

    # Build masked text
    parts: list[str] = []
    prev_end = 0
    for s, e in merged:
        parts.append(text[prev_end:s])
        parts.append(replacement)
        prev_end = e
    parts.append(text[prev_end:])

    return "".join(parts)


# ---------------------------------------------------------------------------
# Summary helpers
# ---------------------------------------------------------------------------


def citation_summary(result: CitationExtractionResult) -> dict[str, Any]:
    """Produce a summary dict suitable for inclusion in dataset output."""
    return {
        "total_citations": len(result.citations),
        "case_citations": len(result.case_citations),
        "unique_case_citations": len(deduplicate_case_citations(result.case_citations)),
        "short_form_count": result.short_form_count,
        "statute_count": result.statute_count,
        "secondary_count": result.secondary_count,
        "normalized_case_cites": [
            c.normalized for c in deduplicate_case_citations(result.case_citations) if c.normalized
        ],
    }

"""Facts span extraction from court merits briefs (rules_v2).

Implements a three-phase pipeline:
  Phase A: Build heading map (scan document for all candidate headings)
  Phase B: Classify sections + merge adjacent fact-like sections
  Phase C: Validate with guardrails + quality gates

This module is the single source of truth for facts extraction logic.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class HeadingEntry:
    """A heading found in the document."""

    start: int  # char offset of the heading line start
    end: int  # char offset of the heading line end
    text: str  # heading text (uppercase, trimmed)
    heading_type: str  # "start" | "stop" | "other"
    confidence: float  # 1.0 exact, 0.7 soft
    match_method: str  # "exact" | "soft"


@dataclass
class SectionSpan:
    """A classified section between two headings."""

    start: int  # char offset of section content start (after heading)
    end: int  # char offset of section content end (before next heading)
    role: str  # "facts" | "procedural_history" | "argument" | "other" etc.
    heading: HeadingEntry | None = None


@dataclass
class ExtractionResult:
    """Result of facts span extraction."""

    start: int | None = None
    end: int | None = None
    method: str = "rules_v2"
    notes: list[str] = field(default_factory=list)
    confidence: str = "low"  # "high" | "medium" | "low"
    sections_merged: int = 0
    heading_map_size: int = 0
    start_heading_text: str | None = None
    stop_heading_text: str | None = None
    match_method: str = "none"  # "exact" | "soft" | "fallback"
    doc_type_id: str = "UNKNOWN"
    intro_found: bool = False
    intro_classified_as: str | None = None
    quality_gates: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Heading vocabulary
# ---------------------------------------------------------------------------

# Ordered by specificity (longest/most-specific first for disambiguation).
START_HEADINGS = [
    "STATEMENT OF FACTS AND PROCEDURAL HISTORY",
    "STATEMENT OF THE CASE AND FACTS",
    "FACTUAL AND PROCEDURAL BACKGROUND",
    "FACTUAL AND PROCEDURAL HISTORY",
    "FACTS AND PROCEDURAL HISTORY",
    "COUNTER-STATEMENT OF FACTS",
    "COUNTER-STATEMENT OF THE CASE",
    "STATEMENT OF RELEVANT FACTS",
    "STATEMENT OF MATERIAL FACTS",
    "STATEMENT OF THE PROCEEDINGS",
    "RELEVANT FACTUAL BACKGROUND",
    "NATURE OF THE PROCEEDINGS",
    "COURSE OF PROCEEDINGS",
    "STATEMENT OF THE FACTS",
    "STATEMENT OF THE CASE",
    "PRELIMINARY STATEMENT",
    "PROCEDURAL BACKGROUND",
    "FACTUAL BACKGROUND",
    "PROCEDURAL HISTORY",
    "PROCEDURAL POSTURE",
    "STATEMENT OF FACTS",
    "NATURE OF THE CASE",
    "RELEVANT FACTS",
    "BACKGROUND",
]

# INTRODUCTION is conditional — only treated as start heading when
# DOC_TYPE_HEADING_POLICY allows it (see §4 of spec).
CONDITIONAL_START_HEADINGS = ["INTRODUCTION"]

STOP_HEADINGS = [
    "SUMMARY OF THE ARGUMENT",
    "SUMMARY OF ARGUMENT",
    "STANDARDS OF REVIEW",
    "STANDARD OF REVIEW",
    "STATEMENT OF THE ISSUES",
    "QUESTIONS PRESENTED",
    "REASONS FOR GRANTING",
    "RELIEF REQUESTED",
    "PRAYER FOR RELIEF",
    "ISSUES PRESENTED",
    "LEGAL FRAMEWORK",
    "LEGAL ANALYSIS",
    "LEGAL STANDARD",
    "ARGUMENTS",
    "ARGUMENT",
    "DISCUSSION",
    "ANALYSIS",
    "CONCLUSION",
]

# Procedural headings — classified as fact-like for merging purposes.
PROCEDURAL_HEADINGS = {
    "PROCEDURAL HISTORY",
    "PROCEDURAL BACKGROUND",
    "PROCEDURAL POSTURE",
    "COURSE OF PROCEEDINGS",
    "STATEMENT OF THE PROCEEDINGS",
    "FACTS AND PROCEDURAL HISTORY",
    "FACTUAL AND PROCEDURAL HISTORY",
    "FACTUAL AND PROCEDURAL BACKGROUND",
    "STATEMENT OF FACTS AND PROCEDURAL HISTORY",
}

# Soft keywords with word-boundary enforcement (fix for v0 substring matching).
SOFT_START_KEYWORDS = [
    re.compile(r"\bFACT(?:S|UAL)\b"),
    re.compile(r"\bBACKGROUND\b"),
    re.compile(r"\bSTATEMENT\s+OF\s+THE\s+CASE\b"),
    re.compile(r"\bSTATEMENT\b"),  # lowest priority
    re.compile(r"\bPROCEDURAL\b"),
    re.compile(r"\bPRELIMINARY\b"),
    re.compile(r"\bNATURE\s+OF\b"),
]

SOFT_STOP_KEYWORDS = [
    re.compile(r"\bARGUMENT\b"),
    re.compile(r"\bDISCUSSION\b"),
    re.compile(r"\bSTANDARD\s+OF\s+REVIEW\b"),
    re.compile(r"\bLEGAL\s+STANDARD\b"),
    re.compile(r"\bCONCLUSION\b"),
    re.compile(r"\bRELIEF\b"),
    re.compile(r"\bANALYSIS\b"),
]

BAD_HEADING_FRAGMENTS = [
    "TABLE OF CONTENTS",
    "TABLE OF AUTHORITIES",
    "TABLE OF CITATIONS",
    "JURISDICTION",
    "CERTIFICATE",
    "SERVICE",
    "COMPLIANCE",
    "CORPORATE DISCLOSURE",
    "CASE ",
    "DOCUMENT ",
    "FILED ",
    "PAGE ",
]

TOC_MARKERS = ("TABLE OF CONTENTS", "TABLE OF AUTHORITIES", "TABLE OF CITATIONS")

# ---------------------------------------------------------------------------
# Document-type reference table
# ---------------------------------------------------------------------------

DOC_TYPE_HEADING_POLICY: dict[str, dict[str, bool]] = {
    "FEDERAL_APPELLATE_OPENING": {"introduction_as_facts": False},
    "FEDERAL_APPELLATE_RESPONSE": {"introduction_as_facts": False},
    "STATE_APPELLATE": {"introduction_as_facts": True},
    "CERT_PETITION": {"introduction_as_facts": True},
    "MERITS_SCOTUS": {"introduction_as_facts": True},
    "DISTRICT_COURT": {"introduction_as_facts": True},
    "UNKNOWN": {"introduction_as_facts": False},
}

# ---------------------------------------------------------------------------
# Regex patterns
# ---------------------------------------------------------------------------

RE_DOT_LEADERS = re.compile(r"\.{2,}\s*\d{1,4}")
RE_TRAILING_PAGE = re.compile(r"\s+\d{1,4}\s*$")


def _heading_regex(phrases: list[str]) -> re.Pattern[str]:
    """Build a regex that matches heading lines with optional roman/arabic prefixes."""
    esc = [re.escape(p.upper()) for p in phrases]
    joined = "|".join(esc)
    return re.compile(
        rf"""(?mx)
        ^\s*
        (?:[IVXLC]+\.)?\s*          # optional roman numeral (dot required)
        (?:\d+\.?)?\s*               # optional arabic numeral
        (?:{joined})                 # heading phrase
        \s*(?:[:\.\-–—])?\s*        # optional trailing punctuation
        (?:\.{{2,}}\s*\d{{1,4}})?\s* # optional dot leaders + page number
        (?:\s+\d{{1,4}})?\s*         # optional bare page number
        $"""
    )


# General all-caps heading line pattern (for soft keyword matching).
HEADING_LINE = re.compile(r"(?m)^\s*(?:[IVXLC]+\.)?\s*(?:\d+\.)?\s*([A-Z][A-Z0-9 \-–—/&,:]{2,90})\s*$")

# Quality flag patterns (unchanged from v0).
RE_CASE_CITE = re.compile(r"\b\d{1,4}\s+[A-Z][A-Za-z\.\s]{0,20}\s+\d{1,5}\b")
RE_ARG_MARKERS = re.compile(
    r"\b(we\s+argue|this\s+court\s+should|standard\s+of\s+review|for\s+these\s+reasons)\b",
    re.I,
)

# ---------------------------------------------------------------------------
# Preprocessing utilities (relocated from pipeline.py)
# ---------------------------------------------------------------------------


def strip_pacer_headers(clean: str) -> str:
    """Remove PACER/ECF header stamp lines."""
    out = []
    for line in clean.splitlines():
        u = line.strip().upper()
        if "DOCUMENT" in u and "FILED" in u and "PAGE" in u and u.startswith("CASE "):
            continue
        if u.startswith("CASE:") and "DOCUMENT:" in u and "PAGE:" in u:
            continue
        out.append(line)
    return "\n".join(out)


def merge_roman_heading_lines(text: str) -> str:
    """Merge standalone roman numeral lines with the following line."""
    lines = text.splitlines()
    merged: list[str] = []
    i = 0
    while i < len(lines):
        cur = lines[i].strip()
        if re.fullmatch(r"[IVXLC]+", cur) and i + 1 < len(lines):
            nxt = lines[i + 1].strip()
            merged.append(f"{cur}. {nxt}")
            i += 2
            continue
        merged.append(lines[i])
        i += 1
    return "\n".join(merged)


# ---------------------------------------------------------------------------
# Phase A: Build heading map
# ---------------------------------------------------------------------------


def _line_at(text: str, idx: int) -> str:
    """Return the full line containing character at idx."""
    ls = text.rfind("\n", 0, idx) + 1
    le = text.find("\n", idx)
    if le == -1:
        le = len(text)
    return text[ls:le]


def _is_probably_toc_entry(upper_text: str, match_start: int) -> bool:
    """Check if a heading match is likely a TOC entry rather than a real heading."""
    window = 15000
    prev = upper_text[max(0, match_start - window) : match_start]
    if not any(m in prev for m in TOC_MARKERS):
        return False

    line = _line_at(upper_text, match_start).strip()

    if re.search(r"\.{2,}\s*\d{1,4}\s*$", line):
        return True
    if re.search(r"\s+\d{1,4}\s*$", line) and len(line) >= 20:
        return True
    return False


def _classify_heading_text(text: str, doc_type_id: str) -> tuple[str, float, str]:
    """Classify a heading text as start/stop/other with confidence.

    Returns (heading_type, confidence, match_method).
    """
    upper = text.upper().strip()

    # Check exact start headings.
    for h in START_HEADINGS:
        if upper == h or upper.rstrip(":.–—- ") == h:
            return "start", 1.0, "exact"

    # Check conditional start headings (e.g., INTRODUCTION).
    for h in CONDITIONAL_START_HEADINGS:
        if upper == h or upper.rstrip(":.–—- ") == h:
            policy = DOC_TYPE_HEADING_POLICY.get(doc_type_id, DOC_TYPE_HEADING_POLICY["UNKNOWN"])
            if policy.get("introduction_as_facts", False):
                return "start", 0.8, "exact"
            return "other", 0.0, "exact"

    # Check exact stop headings.
    for h in STOP_HEADINGS:
        if upper == h or upper.rstrip(":.–—- ") == h:
            return "stop", 1.0, "exact"

    # Check soft start keywords (word-boundary regex).
    for pattern in SOFT_START_KEYWORDS:
        if pattern.search(upper):
            return "start", 0.7, "soft"

    # Check soft stop keywords.
    for pattern in SOFT_STOP_KEYWORDS:
        if pattern.search(upper):
            return "stop", 0.7, "soft"

    return "other", 0.0, "none"


def build_heading_map(text: str, doc_type_id: str = "UNKNOWN") -> tuple[list[HeadingEntry], bool, str | None]:
    """Phase A: Scan document for all candidate headings.

    Returns (heading_entries, intro_found, intro_classified_as).
    """
    upper = text.upper()
    entries: list[HeadingEntry] = []
    intro_found = False
    intro_classified_as: str | None = None

    # Build combined regex for exact headings (start + conditional + stop).
    all_exact = START_HEADINGS + CONDITIONAL_START_HEADINGS + STOP_HEADINGS
    exact_re = _heading_regex(all_exact)

    # Pass 1: Find exact heading matches.
    for m in exact_re.finditer(upper):
        if _is_probably_toc_entry(upper, m.start()):
            continue

        heading_text = m.group().strip()
        # Strip roman/arabic prefix for classification (dot required for roman).
        clean_text = re.sub(r"^\s*(?:[IVXLC]+\.)?\s*(?:\d+\.?)?\s*", "", heading_text).strip()
        clean_text = re.sub(r"\s*(?:[:\.\-–—])?\s*$", "", clean_text).strip()
        # Remove dot-leader page numbers.
        clean_text = re.sub(r"\.{2,}\s*\d{1,4}\s*$", "", clean_text).strip()
        clean_text = re.sub(r"\s+\d{1,4}\s*$", "", clean_text).strip()

        htype, conf, method = _classify_heading_text(clean_text, doc_type_id)

        # Track INTRODUCTION specifically.
        if clean_text.upper() in ("INTRODUCTION",):
            intro_found = True
            intro_classified_as = "factual" if htype == "start" else "argumentative"

        if htype == "other" and conf == 0.0:
            continue

        entries.append(
            HeadingEntry(
                start=m.start(),
                end=m.end(),
                text=clean_text,
                heading_type=htype,
                confidence=conf,
                match_method=method,
            )
        )

    # Pass 2: Find soft heading matches (all-caps lines not already matched).
    exact_positions = {(e.start, e.end) for e in entries}
    for m in HEADING_LINE.finditer(upper):
        title = m.group(1).strip()
        if any(b in title for b in BAD_HEADING_FRAGMENTS):
            continue
        if _is_probably_toc_entry(upper, m.start()):
            continue
        # Skip if already matched by exact pass.
        if any(abs(m.start() - pos[0]) < 5 for pos in exact_positions):
            continue

        htype, conf, method = _classify_heading_text(title, doc_type_id)

        # Track INTRODUCTION in Pass 2 as well.
        if title.upper() in ("INTRODUCTION",):
            intro_found = True
            intro_classified_as = "factual" if htype == "start" else "argumentative"

        if htype == "other":
            continue

        entries.append(
            HeadingEntry(
                start=m.start(),
                end=m.end(),
                text=title,
                heading_type=htype,
                confidence=conf,
                match_method=method,
            )
        )

    # Sort by position.
    entries.sort(key=lambda e: e.start)

    # Deduplicate overlapping entries (keep highest confidence).
    deduped: list[HeadingEntry] = []
    for entry in entries:
        if deduped and abs(entry.start - deduped[-1].start) < 10:
            if entry.confidence > deduped[-1].confidence:
                deduped[-1] = entry
        else:
            deduped.append(entry)

    return deduped, intro_found, intro_classified_as


# ---------------------------------------------------------------------------
# Phase B: Section classification + merge
# ---------------------------------------------------------------------------


def _section_role(heading: HeadingEntry) -> str:
    """Determine the section role from a heading entry."""
    if heading.heading_type == "stop":
        text_upper = heading.text.upper()
        if "ARGUMENT" in text_upper:
            return "argument"
        if "STANDARD" in text_upper or "REVIEW" in text_upper:
            return "standard_of_review"
        if "CONCLUSION" in text_upper or "RELIEF" in text_upper:
            return "conclusion"
        return "other_stop"

    if heading.heading_type == "start":
        if heading.text.upper() in PROCEDURAL_HEADINGS:
            return "procedural_history"
        return "facts"

    return "other"


def classify_sections(heading_map: list[HeadingEntry], text_len: int) -> list[SectionSpan]:
    """Phase B: Walk heading map and classify each inter-heading span."""
    if not heading_map:
        return []

    sections: list[SectionSpan] = []
    for i, heading in enumerate(heading_map):
        content_start = heading.end
        content_end = heading_map[i + 1].start if i + 1 < len(heading_map) else text_len

        role = _section_role(heading)
        sections.append(
            SectionSpan(
                start=content_start,
                end=content_end,
                role=role,
                heading=heading,
            )
        )

    return sections


def merge_fact_sections(
    sections: list[SectionSpan],
    max_merge: int = 6,
) -> tuple[list[SectionSpan], list[str]]:
    """Merge adjacent fact-like sections.

    Args:
        sections: Classified section spans from Phase B.
        max_merge: Maximum number of contiguous fact-like sections to merge.
            Sections beyond this limit are dropped with a warning.

    Returns (merged_groups, notes) where merged_groups is the best contiguous
    group of fact-like sections.
    """
    notes: list[str] = []
    fact_like = {"facts", "procedural_history"}

    # Build contiguous groups of fact-like sections.
    groups: list[list[SectionSpan]] = []
    current_group: list[SectionSpan] = []

    for section in sections:
        if section.role in fact_like:
            current_group.append(section)
        else:
            if current_group:
                groups.append(current_group)
                current_group = []
    if current_group:
        groups.append(current_group)

    if not groups:
        return [], notes

    # Pick the group with the highest total confidence.
    best_group = max(
        groups,
        key=lambda g: sum(s.heading.confidence for s in g if s.heading),
    )

    # Enforce max merge count.
    if len(best_group) > max_merge:
        notes.append("merge_limit_warning")
        best_group = best_group[:max_merge]

    if len(best_group) > 1:
        notes.append(f"merged_{len(best_group)}_sections")

    return best_group, notes


# ---------------------------------------------------------------------------
# Phase C: Validation + quality gates
# ---------------------------------------------------------------------------


def _trim_whitespace(text: str, start: int, end: int) -> tuple[int, int]:
    """Trim leading/trailing whitespace from a span."""
    while start < end and text[start] in " \n\t":
        start += 1
    while end > start and text[end - 1] in " \n\t":
        end -= 1
    return start, end


def quality_flags(text: str) -> dict[str, Any]:
    """Compute quality signals for a text span.

    Backward-compatible with the v0 quality_flags function.
    """
    n_chars = max(len(text), 1)
    cite_hits = len(RE_CASE_CITE.findall(text))
    arg_hits = len(RE_ARG_MARKERS.findall(text))
    return {
        "cite_hits": cite_hits,
        "arg_marker_hits": arg_hits,
        "cite_hits_per_10k_chars": cite_hits / (n_chars / 10_000.0),
        "arg_hits_per_10k_chars": arg_hits / (n_chars / 10_000.0),
    }


def _compute_alpha_ratio(text: str) -> float:
    """Fraction of characters that are alphabetic."""
    if not text:
        return 0.0
    alpha = sum(1 for ch in text if ch.isalpha())
    return alpha / len(text)


def _count_toc_lines(text: str) -> int:
    """Count lines that look like TOC entries (dot leaders + page number)."""
    count = 0
    for line in text.splitlines():
        if re.search(r"\.{2,}\s*\d{1,4}\s*$", line.strip()):
            count += 1
    return count


def validate_span(
    start: int,
    end: int,
    text: str,
    full_text_len: int,
    base_confidence: float,
    match_method: str,
) -> ExtractionResult:
    """Phase C: Apply guardrails and quality gates to a candidate span."""
    result = ExtractionResult(
        start=start,
        end=end,
        match_method=match_method,
    )
    notes = result.notes
    span_len = end - start

    # --- Length guardrails ---

    # Minimum length (varies by confidence).
    if base_confidence >= 1.0:
        min_len = 400
    elif base_confidence >= 0.7:
        min_len = 300
    else:
        min_len = 800

    if span_len < min_len:
        notes.append("span_too_short")
        result.start = None
        result.end = None
        result.confidence = "low"
        return result

    # Maximum length.
    max_len = min(int(0.60 * full_text_len), 50_000)
    if span_len > max_len and max_len > 0:
        notes.append("guardrail_truncated")
        # Truncate to max at nearest paragraph break.
        truncate_at = start + max_len
        # Look for a paragraph break before truncate_at.
        last_break = text.rfind("\n\n", start, truncate_at)
        end = last_break if last_break > start + min_len else truncate_at
        result.end = end
        span_len = end - start

    # --- Quality gates ---
    span_text = text[start:end]
    flags = quality_flags(span_text)
    alpha_ratio = _compute_alpha_ratio(span_text)
    toc_lines = _count_toc_lines(span_text)

    result.quality_gates = {
        **flags,
        "alpha_ratio": round(alpha_ratio, 3),
        "toc_line_count": toc_lines,
    }

    downgrades = 0

    # Gate 1: TOC contamination.
    if toc_lines > 5:
        notes.append("toc_contamination")
        downgrades += 1

    # Gate 2: Citation density.
    if flags["cite_hits"] == 0 and span_len > 2000:
        notes.append("no_citations_in_facts")
    if flags["cite_hits_per_10k_chars"] > 80:
        notes.append("excessive_citations")
        downgrades += 1

    # Gate 3: Argument contamination.
    if flags["arg_hits_per_10k_chars"] > 15.0:
        notes.append("high_argument_contamination")
        downgrades += 2  # severe — forces low confidence
    elif flags["arg_hits_per_10k_chars"] > 5.0:
        notes.append("possible_argument_contamination")
        downgrades += 1

    # Gate 4: Alpha ratio.
    if alpha_ratio < 0.50:
        notes.append("low_alpha_ratio")
        downgrades += 1

    # Gate 5: Position sanity.
    if full_text_len > 0:
        if start < 0.05 * full_text_len:
            notes.append("span_starts_very_early")
        if end > 0.95 * full_text_len:
            notes.append("span_ends_very_late")

    # Compute composite confidence.
    if base_confidence >= 1.0:
        result.confidence = "high" if downgrades == 0 else "medium"
    elif base_confidence >= 0.7:
        result.confidence = "medium" if downgrades == 0 else "low"
    else:
        result.confidence = "low"

    return result


# ---------------------------------------------------------------------------
# Top-level extraction function
# ---------------------------------------------------------------------------


def extract_facts_span(
    clean: str,
    doc_type_id: str = "UNKNOWN",
    max_merge: int = 6,
) -> tuple[tuple[int, int] | None, dict[str, Any]]:
    """Extract the facts span from normalized brief text.

    Backward-compatible with the v0 extract_facts_span signature.

    Args:
        clean: Normalized text (output of normalize_text).
        doc_type_id: Document type for policy lookup (default "UNKNOWN").
        max_merge: Maximum number of contiguous fact-like sections to merge.

    Returns:
        ((start, end), metadata) or (None, metadata).
    """
    # Preprocessing.
    preprocessed = merge_roman_heading_lines(strip_pacer_headers(clean))
    upper = preprocessed.upper()
    full_text_len = len(preprocessed)

    # Phase A: Build heading map.
    heading_map, intro_found, intro_classified_as = build_heading_map(preprocessed, doc_type_id)

    # Phase B: Classify sections and merge.
    sections = classify_sections(heading_map, full_text_len)
    merged_sections, merge_notes = merge_fact_sections(sections, max_merge=max_merge)

    # Store preprocessed text so callers can slice correctly
    # (offsets are into preprocessed, not the original clean text).
    result_meta: dict[str, Any] = {
        "method": "rules_v2",
        "preprocessed_text": preprocessed,
        "notes": list(merge_notes),
        "confidence": "low",
        "sections_merged": len(merged_sections),
        "heading_map_size": len(heading_map),
        "start_heading_text": None,
        "stop_heading_text": None,
        "match_method": "none",
        "doc_type_id": doc_type_id,
        "intro_found": intro_found,
        "intro_classified_as": intro_classified_as,
        "quality_gates": {},
    }

    if merged_sections:
        # Compute span boundaries from merged sections.
        start = merged_sections[0].start
        end = merged_sections[-1].end
        start, end = _trim_whitespace(preprocessed, start, end)

        # Determine base confidence from the best heading.
        base_conf = max((s.heading.confidence for s in merged_sections if s.heading), default=0.7)
        match_method = "exact" if base_conf >= 1.0 else "soft"

        if merged_sections[0].heading:
            result_meta["start_heading_text"] = merged_sections[0].heading.text
        # Find the stop heading (the heading that terminates the last section).
        # Look for the next heading after the last merged section in the full heading map.
        last_section_end = merged_sections[-1].end
        for entry in heading_map:
            if entry.start >= last_section_end - 5 and entry.heading_type == "stop":
                result_meta["stop_heading_text"] = entry.text
                break

        # Phase C: Validate.
        validation = validate_span(start, end, preprocessed, full_text_len, base_conf, match_method)
        result_meta["match_method"] = match_method
        result_meta["notes"].extend(validation.notes)
        result_meta["confidence"] = validation.confidence
        result_meta["quality_gates"] = validation.quality_gates

        if validation.start is not None and validation.end is not None:
            return (validation.start, validation.end), result_meta

        # Span was too short — fall through to fallback.
        result_meta["notes"].append("no_exact_heading")

    elif not merged_sections:
        result_meta["notes"].append("no_exact_heading")

    # Fallback: pre-ARGUMENT slice.
    m_arg = re.search(
        r"(?m)^\s*(?:[IVXLC]+\.?)?\s*(?:\d+\.?)?\s*ARGUMENT\s*(?:[:\.\-–—])?\s*$",
        upper,
    )
    if m_arg:
        end = m_arg.start()
        m_toa = re.search(r"(?m)^\s*TABLE OF AUTHORITIES\s*$", upper)
        if m_toa and m_toa.start() < end:
            # Start after TOA block.
            start = m_toa.end()
            # Move to next heading line after TOA.
            for m_h in HEADING_LINE.finditer(upper):
                if m_h.start() > start:
                    title = m_h.group(1).strip()
                    if not any(b in title for b in BAD_HEADING_FRAGMENTS):
                        start = m_h.end()
                        break
        else:
            start = 0

        start, end = _trim_whitespace(preprocessed, start, end)

        if end > start and (end - start) >= 800:
            result_meta["notes"].append("fallback_pre_argument")
            result_meta["match_method"] = "fallback"

            validation = validate_span(start, end, preprocessed, full_text_len, 0.5, "fallback")
            result_meta["notes"].extend(validation.notes)
            result_meta["confidence"] = validation.confidence
            result_meta["quality_gates"] = validation.quality_gates

            if validation.start is not None and validation.end is not None:
                return (validation.start, validation.end), result_meta

    result_meta["notes"].append("no_span_found")
    return None, result_meta


# ---------------------------------------------------------------------------
# Utility: heading_candidates (backward-compatible)
# ---------------------------------------------------------------------------


def heading_candidates(clean: str, limit: int = 40) -> list[str]:
    """Extract candidate heading texts from document (for diagnostics)."""
    upper = clean.upper()
    out: list[str] = []
    for m in HEADING_LINE.finditer(upper):
        title = m.group(1).strip()
        if any(b in title for b in BAD_HEADING_FRAGMENTS):
            continue
        out.append(title)
        if len(out) >= limit:
            break
    return out

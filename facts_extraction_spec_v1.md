# Facts Span Extraction Specification (v1)

## Purpose

This specification defines the complete rule set for extracting "facts" sections from U.S. court merits briefs. It replaces the underspecified facts extraction description in `approved_spec_package_v0_2.md` with a concrete, testable, and implementable design.

The facts span is the core input to the citation prediction model: given a factual narrative, predict which cases are cited. Extraction quality directly determines dataset quality.

---

## 1. Architecture Overview

### Pipeline: Heading Map → Classify + Merge → Validate

The extractor operates in three phases on normalized, preprocessed text:

```
Raw text
  │
  ▼
Preprocessing (normalize, strip PACER headers, merge roman heading lines)
  │
  ▼
Phase A: Build Heading Map
  Scan entire document for candidate headings (exact + soft match).
  Filter TOC entries. Produce ordered list of (position, text, type, confidence).
  │
  ▼
Phase B: Classify Sections + Merge
  Walk heading map. Classify each inter-heading span by role.
  Merge adjacent fact-like sections (up to 4). Stop at stop headings.
  │
  ▼
Phase C: Validate + Quality Gates
  Apply min/max length guardrails. Run quality checks.
  Produce final (start, end) + rich metadata.
  │
  ▼
Output: (facts_start, facts_end, facts_text, metadata)
```

### Why This Architecture

The previous 3-tier waterfall (exact headings → soft headings → pre-ARGUMENT fallback) had structural problems:
- Could not merge multiple fact-like sections
- Each tier used completely different matching logic
- Quality signals were computed but never fed back into extraction decisions
- The fallback path could capture half the brief without any sanity check

The heading-map approach finds all headings once, classifies once, and merges once — regardless of how headings were matched.

---

## 2. Preprocessing

Applied before Phase A. These functions are unchanged from the current implementation.

### 2.1 Text normalization (`normalize_text`)
- Normalize line endings to `\n`
- Fix hyphen-breaks: `word-\nbreak` → `wordbreak`
- Collapse 2+ spaces → 1 space
- Collapse 3+ newlines → 2 newlines
- Strip trailing spaces per line
- Strip overall leading/trailing whitespace

### 2.2 PACER header stripping (`strip_pacer_headers`)
Remove lines matching PACER/ECF header stamp patterns:
- Lines containing "DOCUMENT" + "FILED" + "PAGE" starting with "CASE "
- Lines starting with "CASE:" containing "DOCUMENT:" and "PAGE:"

### 2.3 Roman numeral heading merge (`merge_roman_heading_lines`)
If a line is a standalone roman numeral (I–C range), merge with the next line:
- `"III\n. STATEMENT OF FACTS"` → `"III. STATEMENT OF FACTS"`

---

## 3. Phase A: Heading Map

### 3.1 Heading detection

Scan the uppercased document for lines matching the heading pattern:

```
^\s*
(?:[IVXLC]+\.?)?\s*          # optional roman numeral prefix
(?:\d+\.?)?\s*               # optional arabic numeral prefix
(?:<HEADING_PHRASE>)          # the heading text
\s*(?:[:\.\-–—])?\s*         # optional trailing punctuation
$
```

Headings are matched against two lists: **exact start headings** and **exact stop headings**. Additionally, lines matching the general all-caps heading pattern are checked against **soft keywords**.

### 3.2 Exact start headings (facts-like sections)

These headings signal the beginning of factual narrative. Ordered by specificity (most specific first for disambiguation):

```
STATEMENT OF FACTS AND PROCEDURAL HISTORY
STATEMENT OF THE CASE AND FACTS
FACTUAL AND PROCEDURAL BACKGROUND
FACTUAL AND PROCEDURAL HISTORY
FACTS AND PROCEDURAL HISTORY
STATEMENT OF FACTS
STATEMENT OF THE FACTS
STATEMENT OF THE CASE
STATEMENT OF RELEVANT FACTS
STATEMENT OF MATERIAL FACTS
STATEMENT OF THE PROCEEDINGS
COUNTER-STATEMENT OF FACTS
COUNTER-STATEMENT OF THE CASE
FACTUAL BACKGROUND
RELEVANT FACTUAL BACKGROUND
RELEVANT FACTS
NATURE OF THE CASE
NATURE OF THE PROCEEDINGS
COURSE OF PROCEEDINGS
PRELIMINARY STATEMENT
PROCEDURAL HISTORY
PROCEDURAL BACKGROUND
PROCEDURAL POSTURE
BACKGROUND
INTRODUCTION                    # conditional — see §4 (doc-type reference table)
```

**Additions over v0 (current implementation):**
| Heading | Rationale |
|---|---|
| `NATURE OF THE CASE` | Standard form in many state courts and some federal district courts |
| `NATURE OF THE PROCEEDINGS` | Variant used in certain jurisdictions |
| `PRELIMINARY STATEMENT` | Common in NY state courts and some federal filings |
| `COUNTER-STATEMENT OF FACTS` | Appellee/respondent briefs frequently use this |
| `COUNTER-STATEMENT OF THE CASE` | Variant of counter-statement |
| `STATEMENT OF RELEVANT FACTS` | Used in some circuits for targeted factual recitation |
| `STATEMENT OF MATERIAL FACTS` | Common in summary judgment contexts |
| `COURSE OF PROCEEDINGS` | Procedural narrative variant |
| `STATEMENT OF THE PROCEEDINGS` | Procedural narrative variant |
| `PROCEDURAL BACKGROUND` | Variant of PROCEDURAL HISTORY |
| `PROCEDURAL POSTURE` | Variant focusing on current case posture |
| `RELEVANT FACTUAL BACKGROUND` | Combined variant |
| `INTRODUCTION` | **Conditional** — only treated as facts-like for certain doc types (see §4) |

### 3.3 Exact stop headings (end of facts region)

These headings signal that the factual narrative has ended:

```
SUMMARY OF ARGUMENT
SUMMARY OF THE ARGUMENT
ARGUMENT
ARGUMENTS
STANDARD OF REVIEW
STANDARDS OF REVIEW
LEGAL STANDARD
LEGAL ANALYSIS
LEGAL FRAMEWORK
DISCUSSION
ANALYSIS
CONCLUSION
RELIEF REQUESTED
PRAYER FOR RELIEF
ISSUES PRESENTED
QUESTIONS PRESENTED
REASONS FOR GRANTING
STATEMENT OF THE ISSUES
```

**Additions over v0:**
| Heading | Rationale |
|---|---|
| `SUMMARY OF THE ARGUMENT` | Alternate phrasing seen in many briefs |
| `ARGUMENTS` (plural) | Common variant |
| `STANDARDS OF REVIEW` (plural) | Common variant |
| `LEGAL ANALYSIS` | Used in some district court briefing |
| `LEGAL FRAMEWORK` | Used in some circuits |
| `PRAYER FOR RELIEF` | Common in Texas and other state courts |
| `ISSUES PRESENTED` | Follows facts in merits briefs; precedes in cert petitions (handled by position) |
| `QUESTIONS PRESENTED` | Variant of issues presented |
| `REASONS FOR GRANTING` | Cert petition specific |
| `STATEMENT OF THE ISSUES` | Variant |

### 3.4 Soft keyword matching

For heading-like lines (all-caps, 2–90 chars) that don't match any exact heading, apply soft keyword matching with **word-boundary enforcement**:

**Soft start keywords:**
```python
SOFT_START_KEYWORDS = [
    r"\bFACT(?:S|UAL)\b",                  # FACTS, FACTUAL — not FACTSHEET
    r"\bBACKGROUND\b",
    r"\bSTATEMENT\s+OF\s+THE\s+CASE\b",
    r"\bSTATEMENT\b",                       # lowest priority
    r"\bPROCEDURAL\b",
    r"\bPRELIMINARY\b",
    r"\bNATURE\s+OF\b",
]
```

**Soft stop keywords:**
```python
SOFT_STOP_KEYWORDS = [
    r"\bARGUMENT\b",
    r"\bDISCUSSION\b",
    r"\bSTANDARD\s+OF\s+REVIEW\b",
    r"\bLEGAL\s+STANDARD\b",
    r"\bCONCLUSION\b",
    r"\bRELIEF\b",
    r"\bANALYSIS\b",
]
```

**Critical fix:** The v0 implementation used bare substring matching (`"FACT" in title`), which could match "FACTSHEET" or "MANUFACTURED". The v1 spec requires regex word-boundary matching (`\b`) for all soft keywords.

### 3.5 Bad heading fragments (exclusion list)

Lines matching the heading pattern but containing these fragments are excluded from the heading map:

```
TABLE OF CONTENTS
TABLE OF AUTHORITIES
TABLE OF CITATIONS
JURISDICTION
CERTIFICATE
SERVICE
COMPLIANCE
CORPORATE DISCLOSURE
CASE                            # as a prefix (bare "CASE " followed by docket info)
DOCUMENT                        # as a prefix
FILED                           # as a prefix
PAGE                            # as a prefix
```

### 3.6 TOC entry filtering

A heading match is classified as a TOC entry (and excluded from the heading map) if:
1. A TOC marker ("TABLE OF CONTENTS", "TABLE OF AUTHORITIES", "TABLE OF CITATIONS") appears within 15,000 characters before the match, **AND**
2. The line containing the match has a strong TOC signal:
   - Dot leaders followed by a page number: `\.{2,}\s*\d{1,4}\s*$`
   - Trailing page number with line length ≥ 20: `\s+\d{1,4}\s*$`

### 3.7 Heading map output

Phase A produces an ordered list of heading entries:

```python
@dataclass
class HeadingEntry:
    start: int          # character offset of heading line start
    end: int            # character offset of heading line end (after heading text)
    text: str           # heading text (uppercase, trimmed)
    heading_type: str   # "start" | "stop" | "other"
    confidence: float   # 1.0 for exact match, 0.7 for soft keyword match
    match_method: str   # "exact" | "soft"
```

Entries are sorted by `start` position.

---

## 4. Document-Type Reference Table

### 4.1 Purpose

Some headings (notably INTRODUCTION) are factual in certain types of briefs and argumentative in others. Rather than applying a blanket rule, the extractor consults a document-type reference table to determine heading interpretation.

### 4.2 Classification table

| `doc_type_id` | Category | INTRODUCTION as facts? | Notes |
|---|---|---|---|
| `FEDERAL_APPELLATE_OPENING` | Federal appellate opening brief | No (typically argumentative) | 3d Cir., 9th Cir. opening briefs |
| `FEDERAL_APPELLATE_RESPONSE` | Federal appellate response brief | No (use COUNTER-STATEMENT instead) | Appellee briefs |
| `STATE_APPELLATE` | State appellate brief | Yes (often factual, esp. NY practice) | NY App. Div. briefs |
| `CERT_PETITION` | Certiorari petition | Yes (usually factual summary) | Supreme Court cert petitions |
| `MERITS_SCOTUS` | Supreme Court merits brief | Yes (typically factual) | SCOTUS merits briefs |
| `DISTRICT_COURT` | District court brief/motion | Yes (often factual; PRELIMINARY STATEMENT common) | Summary judgment briefs |
| `UNKNOWN` | Unclassified | No (conservative default) | Fallback |

### 4.3 Assignment logic

`doc_type_id` is derived from CourtListener metadata:
- **Court field** → federal vs. state, appellate vs. district, SCOTUS
- **Filing type / description** → opening vs. response vs. reply
- **Docket info** → cert petition indicators

If metadata is insufficient to classify, assign `UNKNOWN`.

### 4.4 Policy lookup structure

```python
DOC_TYPE_HEADING_POLICY = {
    "FEDERAL_APPELLATE_OPENING": {
        "introduction_as_facts": False,
    },
    "FEDERAL_APPELLATE_RESPONSE": {
        "introduction_as_facts": False,
    },
    "STATE_APPELLATE": {
        "introduction_as_facts": True,
    },
    "CERT_PETITION": {
        "introduction_as_facts": True,
    },
    "MERITS_SCOTUS": {
        "introduction_as_facts": True,
    },
    "DISTRICT_COURT": {
        "introduction_as_facts": True,
    },
    "UNKNOWN": {
        "introduction_as_facts": False,
    },
}
```

### 4.5 INTRODUCTION logging

Regardless of the policy decision, when an INTRODUCTION heading is encountered, always record in metadata:
- `intro_found: True`
- `intro_classified_as: factual | argumentative | indeterminate`
- `doc_type_id` used for the decision

This enables later analysis to validate and refine the classification table.

---

## 5. Phase B: Section Classification + Merge

### 5.1 Section classification

Walk the heading map in document order. For each pair of consecutive headings, the text between them forms a "section span." Classify each span by its preceding heading:

| Heading type | Section role |
|---|---|
| Start heading (exact, confidence 1.0) | `facts` |
| Start heading (soft, confidence 0.7) | `facts` |
| Stop heading | `argument` / `standard_of_review` / `conclusion` / `other` (based on specific heading) |
| Bad fragment / unclassified | `other` |

Special case: `PROCEDURAL HISTORY`, `PROCEDURAL BACKGROUND`, `PROCEDURAL POSTURE`, `COURSE OF PROCEEDINGS` are classified as `procedural_history` (a subtype of facts-like for merging purposes).

### 5.2 Multi-section merging rules

**Rule 1: Adjacent fact-like sections merge.**
If two consecutive sections are both classified as `facts` or `procedural_history`, merge them into a single span. "Adjacent" means no non-fact-like heading appears between them.

**Rule 2: Preserve document order.**
Merged span = `(min(starts), max(ends))`. Section text is concatenated in order.

**Rule 3: Skip small gaps.**
If two fact-like sections are separated only by a subsection marker (roman numeral, letter prefix like "A." or "B.", or a numbered heading without any of the exact/soft keywords), treat them as continuous.

**Rule 4: Do not merge across stop headings.**
If ARGUMENT or any other stop heading appears between two fact-like sections, only the first contiguous group is used.

**Rule 5: Maximum merge count = 4.**
If more than 4 contiguous fact-like sections are found, this signals heading detection may be misfiring. Take only the first group and add `"merge_limit_warning"` to notes.

### 5.3 Fallback: pre-ARGUMENT slice

If Phase B produces no fact-like sections but the heading map contains an ARGUMENT or SUMMARY OF ARGUMENT heading:
1. Set `end` = start of the ARGUMENT heading
2. If a TABLE OF AUTHORITIES heading exists before ARGUMENT, set `start` = end of the first heading after TOA
3. Otherwise, set `start` = 0
4. This is a low-confidence extraction (`confidence: 0.5`); add `"fallback_pre_argument"` to notes

### 5.4 No extraction possible

If neither classified sections nor fallback produce a span, return `None` with `"no_span_found"` in notes.

---

## 6. Phase C: Validation + Quality Gates

### 6.1 Length guardrails

**Minimum length:**

| Extraction confidence | Min chars | Rationale |
|---|---|---|
| High (exact heading, ≥1.0) | 400 | Lowered from 500 to accommodate short facts sections in 15-20 page briefs |
| Medium (soft heading, 0.7) | 300 | Unchanged |
| Low (fallback, 0.5) | 800 | Unchanged; strict for lowest-confidence path |

If span is below minimum: return `None` with `"span_too_short"` in notes.

**Maximum length:**

`max_facts_len = min(0.60 * full_text_len, 50_000)`

- A facts section should not be the majority of the brief (typical range: 10–40%).
- 60% provides headroom for complex litigation with lengthy factual narratives.
- Absolute cap of 50,000 chars (~12,500 words, ~25 pages) prevents runaway extraction.

If span exceeds max:
1. Attempt to find a tighter stop heading within the span (scan for stop headings that were missed).
2. If no tighter boundary found, truncate to max at the nearest paragraph break.
3. Add `"guardrail_truncated"` to notes.

### 6.2 Quality gates

Applied after length validation. Produce an `extraction_confidence` composite field.

**Gate 1 — TOC contamination:**
Count lines matching dot-leader pattern `\.{2,}\s*\d{1,4}` within the span. If count > 5, the span likely contains table-of-contents material.
- Action: reject span, retry with adjusted boundaries (skip past TOC block).
- Note: `"toc_contamination"`

**Gate 2 — Citation density:**
Using the existing `RE_CASE_CITE` pattern (`\b\d{1,4}\s+[A-Z][A-Za-z\.\s]{0,20}\s+\d{1,5}\b`):
- If `cite_hits == 0` and `facts_len > 2000`: add note `"no_citations_in_facts"`. Warning only (some facts sections have few citations).
- If `cite_hits_per_10k_chars > 80`: add note `"excessive_citations"`. Suggests TOA or argument capture. Warning; flag for audit.

**Gate 3 — Argument marker contamination:**
Using the existing `RE_ARG_MARKERS` pattern:
- If `arg_hits_per_10k_chars > 5.0`: add note `"possible_argument_contamination"`. Downgrade confidence one level.
- If `arg_hits_per_10k_chars > 15.0`: add note `"high_argument_contamination"`. Set confidence to `low`.

**Gate 4 — Alpha ratio:**
`alpha_ratio = (count of alphabetic chars) / (total chars in span)`
- If `alpha_ratio < 0.50`: add note `"low_alpha_ratio"`. Suggests tables, docket numbers, or formatting artifacts. Downgrade confidence one level.

**Gate 5 — Position sanity:**
- If `facts_start < 0.05 * full_text_len`: add note `"span_starts_very_early"`. Warning (may have captured cover page).
- If `facts_end > 0.95 * full_text_len`: add note `"span_ends_very_late"`. Warning (may extend to conclusion).

### 6.3 Composite confidence

Based on the heading match confidence and quality gate results:

| Starting confidence | Quality gate downgrades | Final |
|---|---|---|
| 1.0 (exact heading) | 0 downgrades | `high` |
| 1.0 (exact heading) | 1+ downgrades | `medium` |
| 0.7 (soft heading) | 0 downgrades | `medium` |
| 0.7 (soft heading) | 1+ downgrades | `low` |
| 0.5 (fallback) | any | `low` |

---

## 7. Output Schema

### 7.1 Return value

```python
extract_facts_span(clean: str, doc_type_id: str = "UNKNOWN")
    -> tuple[tuple[int, int] | None, dict[str, Any]]
```

### 7.2 Metadata dictionary

```python
{
    "method": "rules_v2",
    "notes": list[str],                   # diagnostic notes (see §6)
    "confidence": "high" | "medium" | "low",
    "sections_merged": int,               # number of sections merged (1 = single section)
    "heading_map_size": int,              # total headings found in document
    "start_heading_text": str | None,     # the heading that started the facts span
    "stop_heading_text": str | None,      # the heading that ended the facts span
    "match_method": "exact" | "soft" | "fallback",
    "doc_type_id": str,                   # document type used for policy lookup
    "intro_found": bool,                  # whether an INTRODUCTION heading was present
    "intro_classified_as": str | None,    # "factual" | "argumentative" | "indeterminate"
    "quality_gates": {
        "cite_hits": int,
        "arg_marker_hits": int,
        "cite_hits_per_10k_chars": float,
        "arg_hits_per_10k_chars": float,
        "alpha_ratio": float,
        "toc_line_count": int,
    },
}
```

### 7.3 Compatibility with approved spec schema

The output maps to the `facts_span_artifact` schema in `approved_spec_package_v0_2.md`:

| Spec field | Source |
|---|---|
| `facts_start` | `result[0][0]` |
| `facts_end` | `result[0][1]` |
| `facts_text` | `clean[facts_start:facts_end]` |
| `facts_len` | `facts_end - facts_start` |
| `facts_extractor_method` | `meta["method"]` → `"rules_v2"` |
| `facts_extractor_notes` | `"; ".join(meta["notes"])` |

---

## 8. Acceptance Criteria

### 8.1 Pipeline success rate
≥85% of eligible briefs produce a facts span with:
- `facts_len` within bounds (≥ min, ≤ max guardrail)
- `facts_start < facts_end`
- `extraction_confidence` ≠ `None`

### 8.2 Quality targets
- ≥80% of extracted spans rated `correct` on Gold Audit Set (per approved spec §E)
- ≤5% of extractions flagged `"high_argument_contamination"`
- ≤2% of extractions flagged `"toc_contamination"`

### 8.3 Regression coverage
The test suite must include cases for:
- Every exact start heading (at least one test each)
- Every exact stop heading (at least one test each)
- Soft keyword matching with word-boundary enforcement
- Multi-section merging (2, 3, 4 sections)
- Merge limit enforcement (>4 sections)
- INTRODUCTION handling per doc_type_id (factual vs. argumentative)
- Max-length guardrail triggering
- Min-length rejection
- TOC contamination detection
- Argument contamination detection
- Pre-ARGUMENT fallback path
- No-span-found path

### 8.4 Backward compatibility
- Function signature accepts optional `doc_type_id` (defaults to `"UNKNOWN"`)
- Output tuple structure is unchanged: `(tuple[int, int] | None, dict)`
- `meta["method"]` changes from `"rules_v1"` to `"rules_v2"`
- All new metadata fields are additive (no existing fields removed)

---

## 9. Future Considerations (out of scope for v1)

- **LLM-assisted extraction:** For briefs where rules-based extraction fails or produces `low` confidence, an LLM could identify the facts section. This is explicitly deferred per the approved spec ("Non-LLM steps must be deterministic").
- **Cross-reference validation:** Validating that extracted facts text is semantically consistent with the brief's argument section (e.g., facts referenced in argument should appear in the facts span).
- **Per-circuit heading profiles:** Some circuits have distinctive briefing conventions. A per-circuit heading profile (extending the doc-type table) could improve accuracy.
- **Confidence calibration:** The current confidence scores (1.0/0.7/0.5) are heuristic. With enough Gold Audit data, these could be calibrated empirically.

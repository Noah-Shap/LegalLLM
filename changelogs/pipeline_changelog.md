# Changelog: `src/legallm/pipeline.py`

## Changes Made

### Removed (lines 115-651 of original)
- All facts extraction code: `START_HEADINGS`, `STOP_HEADINGS`, `_heading_regex()`, `_line_at()`, `_is_probably_toc_entry()`, `RE_START`, `RE_STOP`, `HEADING_LINE`, `BAD_HEADING_FRAGMENTS`, `SOFT_START_KEYWORDS`, `SOFT_STOP_KEYWORDS`, `strip_pacer_headers()`, `merge_roman_heading_lines()`, `extract_facts_span()`, `RE_CASE_CITE`, `RE_ARG_MARKERS`, `quality_flags()`, `heading_candidates()`
- Approximately 250 lines of code removed.

### Added
- Import: `from legallm.facts_extractor import extract_facts_span, heading_candidates, quality_flags`

### Unchanged
- `normalize_text()` stays in pipeline.py (used by other pipeline stages beyond facts extraction).
- `looks_like_header_only()` stays (delegates to `ocr_decision`; unrelated to facts extraction).
- All other pipeline code (search, download, OCR, scope filtering, main loop) unchanged.
- The main loop at line 983 still calls `extract_facts_span(clean)` with the same signature (backward compatible).

## Issues Encountered

None. The import swap was clean because the new module preserves the exact same function signatures.

## New Considerations

1. **`doc_type_id` not yet passed from main loop.** The main loop calls `extract_facts_span(clean)` without passing `doc_type_id`. This means all extractions default to `"UNKNOWN"` (conservative behavior). To enable INTRODUCTION handling per doc type, the main loop needs to derive `doc_type_id` from CourtListener metadata (court field, filing type, etc.). This is deferred to a future sprint.

2. **`normalize_text` could also move to its own module.** It's a general utility used by both the pipeline and the facts extractor (indirectly). For now it stays in pipeline.py, but a future refactor could create a `text_utils.py` module.

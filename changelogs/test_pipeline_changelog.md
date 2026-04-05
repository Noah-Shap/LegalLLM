# Changelog: `tests/test_pipeline.py`

## Changes Made

### Removed
- Import of `extract_facts_span`, `heading_candidates`, and `quality_flags` from `legallm.pipeline`
- All facts extraction tests (5 tests): `test_extract_facts_span_basic`, `test_extract_facts_span_no_heading`, `test_extract_facts_span_toc_skip`, `test_extract_facts_span_soft_match`, `test_extract_facts_span_fallback`
- All quality flags tests (4 tests): `test_quality_flags_citations`, `test_quality_flags_arg_markers`, `test_quality_flags_empty`, `test_quality_flags_no_matches`
- All heading candidates tests (4 tests): `test_heading_candidates_finds`, `test_heading_candidates_excludes_bad`, `test_heading_candidates_empty`, `test_heading_candidates_limit`
- Total: 13 tests removed

### Unchanged
- Imports: `candidate_pdf_urls`, `in_scope_brief`, `normalize_text` from `legallm.pipeline`
- `normalize_text` tests (6 tests): hyphen break, whitespace, multiple newlines, CRLF, trailing spaces, empty
- `in_scope_brief` tests (9 tests): opening brief, response brief, amicus, reply, motion, no brief keyword, no description, claim construction, falls back to description
- `candidate_pdf_urls` tests (4 tests): www, storage, other, no duplicates
- Total: 19 tests retained

## Issues Encountered

None. The test removal was clean — all removed tests have equivalent or improved coverage in `tests/test_facts_extractor.py`.

## New Considerations

None.

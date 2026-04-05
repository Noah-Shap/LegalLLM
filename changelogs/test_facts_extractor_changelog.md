# Changelog: `tests/test_facts_extractor.py`

## Changes Made

### Added (new file)
- 43 tests across 7 test classes covering the full `facts_extractor` module:

#### `TestBuildHeadingMap` (11 tests)
- `test_finds_exact_start_heading` — verifies exact regex match for "STATEMENT OF FACTS"
- `test_finds_exact_stop_heading` — verifies exact regex match for "ARGUMENT"
- `test_finds_soft_start_heading` — verifies soft keyword match for "FACTUAL OVERVIEW"
- `test_filters_toc_entries` — dot-leader lines excluded from heading map
- `test_roman_numeral_prefix` — "II. PROCEDURAL HISTORY" detected correctly
- `test_finds_new_headings` — "NATURE OF THE CASE" detected (new vocabulary addition)
- `test_pacer_headers_stripped` — PACER/ECF stamps removed before heading search
- `test_word_boundary_enforcement` — "MANUFACTURED" does not false-match on "FACT"
- `test_introduction_tracked_factual` — INTRODUCTION classified as factual for CERT_PETITION doc type
- `test_introduction_tracked_argumentative` — INTRODUCTION classified as argumentative when argument markers present
- `test_multiple_start_headings` — multiple fact-like headings detected in heading map

#### `TestClassifyAndMerge` (5 tests)
- `test_single_facts_section` — basic extraction of a single STATEMENT OF FACTS section
- `test_multi_section_merge` — STATEMENT OF FACTS + PROCEDURAL HISTORY merged into one span
- `test_merge_stops_at_argument` — merging does not extend past an ARGUMENT heading
- `test_merge_limit_four` — at most 4 sections merged (warning logged if exceeded)
- `test_counter_statement_detected` — COUNTER-STATEMENT OF FACTS found and extracted

#### `TestValidation` (5 tests)
- `test_min_length_rejection` — spans under 300 chars rejected
- `test_max_length_guardrail` — spans exceeding 60% of document truncated with guardrail note
- `test_toc_contamination` — spans with >5 dot-leader lines flagged
- `test_argument_contamination_flag` — high density of argument markers flagged
- `test_high_confidence_clean_span` — clean spans receive "high" confidence

#### `TestExtractFactsSpan` (12 tests)
- `test_exact_match` — end-to-end extraction with exact heading match
- `test_no_match_returns_none` — garbage text returns None
- `test_toc_heading_skipped` — TOC entries not treated as section headings
- `test_soft_match` — soft keyword fallback works
- `test_fallback_keyword_scan` — bare keyword scan as last resort
- `test_multi_section` — multi-section merge through full pipeline
- `test_counter_statement` — counter-statement brief through full pipeline
- `test_nature_of_case` — NATURE OF THE CASE heading through full pipeline
- `test_introduction_factual` — factual INTRODUCTION accepted for cert petition doc type
- `test_introduction_argumentative` — argumentative INTRODUCTION skipped when STATEMENT OF FACTS follows
- `test_output_schema` — verifies all required metadata fields present in output dict
- `test_max_length_very_long` — very long facts section triggers guardrail

#### `TestQualityFlags` (4 tests)
- `test_citation_count` — citation regex finds case citations
- `test_arg_markers` — argument marker density computed correctly
- `test_empty_text` — empty string returns zero counts
- `test_no_matches` — normal text without citations/markers returns zeros

#### `TestHeadingCandidates` (4 tests)
- `test_finds_candidates` — heading_candidates returns structured list
- `test_excludes_bad_fragments` — TABLE OF CONTENTS excluded
- `test_empty_text` — no candidates in empty string
- `test_limit` — limit parameter caps number of results

#### `TestPreprocessing` (3 tests)
- `test_strip_pacer_headers` — PACER stamp lines removed
- `test_merge_roman_heading_lines` — broken roman numeral headings re-joined
- `test_merge_roman_preserves_normal_lines` — non-heading lines unaffected

## Issues Encountered

1. **Roman numeral prefix regex bug (6 failures initially).** The `_heading_regex` function used `(?:[IVXLC]+\.?)?\s*` where the dot was optional. This caused "C" from "COUNTER-STATEMENT" and "I" from "INTRODUCTION" to be consumed as roman numeral prefixes, producing truncated heading text like "OUNTER-STATEMENT OF FACTS". Fix: changed to `(?:[IVXLC]+\.)?\s*` (dot required after roman numeral) in the source module.

2. **INTRODUCTION tracking only in Pass 1.** Tests for `intro_found`/`intro_classified_as` metadata failed because the tracking logic was only in Pass 1 (exact regex matches). When INTRODUCTION was matched via Pass 2 (HEADING_LINE soft match), it wasn't tracked. Fix: added intro tracking to Pass 2 in the source module.

3. **Multi-section merge fixture too short.** The `sample_brief_multi_section` fixture had a very short ARGUMENT section, causing the merged facts+procedural_history span to exceed 60% of the total document length, triggering the max-length guardrail. Fix: padded the argument section in `conftest.py` to make the fixture more realistic.

4. **Trailing newline in `test_merge_roman_preserves_normal_lines`.** The `merge_roman_heading_lines` function uses `"\n".join(merged)` which strips trailing newlines. The test input had a trailing `\n` that wasn't preserved. Fix: removed trailing newline from test input.

## New Considerations

1. **Test coverage for edge cases in roman numeral detection.** The dot-required fix means headings like "V STATEMENT OF FACTS" (roman numeral without dot) will not be matched. This is acceptable since standard legal formatting uses "V." but may need revisiting if we encounter non-standard briefs.

2. **INTRODUCTION classification heuristic is simple.** The current test checks for 3+ argument markers to classify as argumentative. More sophisticated NLP-based classification could improve accuracy but adds complexity.

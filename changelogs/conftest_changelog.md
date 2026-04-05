# Changelog: `tests/conftest.py`

## Changes Made

### Added (6 new fixtures)
- **`sample_brief_multi_section`** — A brief with separate STATEMENT OF FACTS and PROCEDURAL HISTORY sections followed by ARGUMENT. Used to test multi-section merging. The ARGUMENT section was padded to ensure the merged facts span stays under the 60% max-length guardrail.
- **`sample_brief_counter_statement`** — An appellee brief using COUNTER-STATEMENT OF FACTS heading (new vocabulary addition). Tests detection of non-standard facts headings.
- **`sample_brief_nature_of_case`** — A state court brief using NATURE OF THE CASE heading followed by STANDARD OF REVIEW as stop heading. Tests state-court-specific heading vocabulary.
- **`sample_brief_introduction_factual`** — A cert petition with a factual INTRODUCTION section (contains specific facts, dates, events). Used to test doc-type-aware INTRODUCTION classification.
- **`sample_brief_introduction_argumentative`** — A federal appellate opening brief with an argumentative INTRODUCTION (contains argument markers like "we argue", "should reverse") followed by a separate STATEMENT OF FACTS. Used to test that argumentative introductions are skipped in favor of the actual facts section.
- **`sample_brief_very_long_facts`** — A brief with ~60k chars of facts content in a ~70k char document. Used to test the max-length guardrail (60% of document / 50k char cap).

### Unchanged (5 existing fixtures)
- `sample_brief_text` — basic brief with exact heading matches
- `sample_brief_soft_headings` — brief requiring soft heading detection
- `sample_pacer_stamp` — PACER/ECF header stamp line
- `sample_garbage_text` — broken PDF extraction text
- `normal_english_text` — normal English text for alpha ratio testing

## Issues Encountered

1. **`sample_brief_multi_section` ARGUMENT section too short.** The initial version had a short argument section, making the facts+procedural_history span exceed 60% of the total document length. This triggered the max-length guardrail in tests that expected the full merged span. Fix: padded the argument section with additional realistic legal text to bring the document proportions into a realistic range.

## New Considerations

1. **Fixture realism vs. test isolation.** The max-length guardrail issue highlighted a tension between keeping fixtures minimal (easier to read/maintain) and making them realistic enough that guardrails don't fire unexpectedly. Future fixtures should ensure fact-like sections are proportionally <60% of the total document.

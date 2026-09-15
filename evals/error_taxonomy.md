# Error taxonomy (C8) — draft v0, 2026-09-14

Open-coded from (a) the rules_v2 notes histogram over the 120 gold documents and (b) a read of all 20
`no_facts_span` failure documents (`f001`–`f020`), before any LLM numbers were in. Update this file every
iteration: add the class counts from the latest `evals/runs/<id>/per_doc.jsonl`, and record which change each
class motivated (see `evals/iterations.md`).

## A. Why rules_v2 found nothing (20 failure docs)

| class | n | docs | what it looks like | expected in gold | motivates |
|---|---:|---|---|---|---|
| **A1 not-a-brief** | 8 | f004, f011, f017, f020 (6th Cir. clerk briefing-schedule letters), f009 (notice-of-appeal form + attachments), f013 (docket sheet), f016 (9th Cir. pro se guide), f019 (bankruptcy filing, no headings) | no facts narrative exists; the 2k build ran with `--no_scope_filter`, so these leaked into the dataset | `has_facts = no` | scope filter (pipeline) + an LLM `has_facts=false` path; the metric is `failure_correct_no_facts_rate` |
| **A2 heading fused with body** | 6 | f003, f005, f006, f010, f014, f018 | PDF text extraction glues the heading and the first sentence onto one line: `STATEMENT OF THE CASE Victoria Davidson was convicted…`, `II. BACKGROUND Mauro filed…`; the line-anchored heading regex needs the heading alone on its line | facts section exists → gold span | rules: allow a heading match at line *start* followed by body text (prompt-side this is trivial for the LLM — hypothesis: LLM recovers most of A2) |
| **A3 title-case / numbered headings** | 3 | f001 (`2. Statement of Facts Relevant to the Issues…`, pro se), f007 (`I. Factual Background` under an all-caps `STATEMENT OF THE CASE`), f014 (`Statement Of The Case I. Facts And Evidence`) | headings are not ALL CAPS, or carry a numeric prefix with a trailing period and parenthetical | gold span | rules: case-insensitive heading match for the exact-heading list; LLM should be indifferent |
| **A4 headings present, extractor still failed** | 3 | f007 (all standard headings on their own lines, 134k chars, PACER stamps on every page), f002, f012, f015 | needs a per-doc trace; suspects: TOC filter swallowing the body heading, PACER-stamp lines between heading and body, `span_too_short` after validation | gold span | investigate before changing anything; may be one bug |
| **A5 intro-only brief** | 1 | f008 | only an `INTRODUCTION` heading; doc_type_id is `UNKNOWN`, so policy treats INTRODUCTION as argument | labeler decides (guide rule 4) | doc-type inference from court metadata (currently 1,563/1,599 rows are `UNKNOWN`) |

(f007 is counted in A3 and A4; the numbers above sum to 21.)

## B. Quality flags on the 100 audit-set docs where rules_v2 *did* find a span

From the `rules-baseline` run notes (counts over 120 docs):

| note | n | reading |
|---|---:|---|
| `no_exact_heading` | 35 | span came from a soft heading or the pre-ARGUMENT fallback → lower confidence, likely boundary errors |
| `span_starts_very_early` | 28 | span begins in the first 5 % of the document — cover page / TOC bleed-in risk |
| `toc_contamination` | 23 | > 5 dot-leader lines inside the span — the span swallowed a table of contents |
| `fallback_pre_argument` | 15 | no fact-like heading at all; everything before ARGUMENT taken |
| `low_alpha_ratio` | 15 | tables, docket numbers, OCR noise inside the span |
| `no_citations_in_facts` | 19 | warning only; some facts sections cite nothing |
| `guardrail_truncated` | 6 | span hit `min(0.6 × doc, 50k)` and was cut at a paragraph break |
| `span_too_short` | 6 | a candidate span was rejected as < min length |
| `merged_5_sections` / `merged_6_sections` / `merge_limit_warning` | 4 / 4 / 3 | heading map is probably misfiring (merge limit raised from 4 to 6 in April) |

These are the strata to over-sample when Noah corrects boundaries (guide: bias to `low`/`medium`).

## C. Hypotheses to test with the first LLM run (fill in from `evals/RESULTS.md`)

1. LLM recovers most of **A2** and **A3** (heading form is irrelevant to it) → recovered-span rate on the failure stratum well above 0.
2. LLM returns `has_facts=false` on **A1** → `failure_correct_no_facts_rate` high; any span it *does* emit on an A1 doc is a hallucination class of its own (**L1 invented facts section**).
3. LLM disagreements on the audit set concentrate in the `toc_contamination` / `fallback_pre_argument` docs (rules wrong, LLM right) — check the worst-agreement list against these notes.
4. LLM-specific classes to watch: **L2 anchor not found** (`start_anchor_not_found` / `end_anchor_not_found` notes → span null), **L3 citation not verbatim** (range expansion like `1-ER-106–07` → `1-ER-107`), **L4 boundary drift run-to-run** (same doc, different end anchor across runs).

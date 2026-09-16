# Error taxonomy (C8) — v0.3, 2026-09-15 (llm-v1, llm-v2, and the Opus 5 judge pass)

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

## D. First llm-v1 run (`evals/runs/llm-v1-all_20260915-021057_0c9ab4`, 120 docs, 0 errors)

Hypotheses from §C, checked:

| # | hypothesis | outcome |
|---|---|---|
| H1 | LLM recovers A2/A3 | **Yes.** A2 fused-heading: 5/6 got a span (f003, f006, f010, f014, f018; not f005). A3 title-case: f001, f007 both got spans. A4: f012 yes, f002/f015 no. Correctness of those spans awaits labels. |
| H2 | LLM says no-facts on A1 | **Mostly.** 6/8 non-briefs correctly returned no span (f004, f009, f011, f016, f017, f020). **L1** below: f013 (docket sheet with an attached R&R — the model extracted the R&R's BACKGROUND) and f019 (bankruptcy filing with a PRELIMINARY STATEMENT / STATEMENT OF THE CASE — arguably a real facts section) got spans. |
| H3 | disagreement concentrates where rules are weak | **Yes.** Rules↔LLM IoU on audit docs where both found a span (n=70): rules confidence **high** mean 0.80 / median 0.98 (n=53); **medium** 0.34 (n=9); **low** 0.11 (n=8). By rules note: `toc_contamination` 0.31, `span_starts_very_early` 0.27, `fallback_pre_argument` 0.17, `low_alpha_ratio` 0.13. The LLM span sits *inside* the rules span on 56/70 docs (median length ratio 0.98, lower quartile 0.65): the rules over-extend (cover page, TOC, procedural tail); the LLM trims. |

New classes:

| class | n | what | reading | motivates |
|---|---:|---|---|---|
| **R1 rules false-positive span** | 17 audit docs (first written as 27, which had counted the 10 failure-stratum docs too) | rules emitted a span; LLM said `has_facts=false` with a reason: reply briefs (g002, g024, g046, g051, g063, g065, g094 …), amicus briefs (g028, g036, g070, g073, g079), a declaration + exhibits (g098), a motion reply (g059). Rules notes on these: `fallback_pre_argument` / `no_exact_heading` / `toc_contamination`, confidence mostly `low` | almost certainly the LLM is right: these documents have no facts narrative; the audit set inherited them from the 2k build's `--no_scope_filter`. **Gold labels decide** (guide: `has_facts = no`). If confirmed, ~17 % of the audit set is a scope leak, not an extraction problem | pipeline scope filter; the eval must score `has_facts` correctness, not only spans |
| **L1 invented span on a non-brief** | 2 / 8 | f013 (docket sheet + attached R&R), f019 | model finds *a* factual narrative in an attachment | prompt v2: "only the brief itself; ignore attached opinions, R&Rs, exhibits"; labeler decides f019 |
| **L2 anchor not found** | 11 (9 %) | `end_anchor_not_found` 8, `start_anchor_not_found` 3 → span null, `empty_facts` | model paraphrased, or the anchor crossed a page-header/footnote boundary; anchors were not stored in v1 provenance (fixed: `provenance.anchors` from the next run) | prompt v2: anchors must be one contiguous run of lines; fallback: retry once with "copy exactly", or locate by longest common substring |
| **L3 non-verbatim citation** | 72 cites in 27 docs (fidelity mean 0.981) after making the check hyphen-insensitive (which cleared 92 PDF-dropped-hyphen cases like `9-ER2042`) | wrong pincite (`776 F. Supp. 1422, 1425` vs source `1426`), range expansion (`1-ER-107` from `1-ER-106–07`), invented ranges (`5-ER-876-877` vs `5-ER-873-876`), `Id. at 664` short forms, glyph loss (`¶¶`, `–` in OCR) | genuine transcription errors mixed with encoding noise | prompt v2: "copy the citation string exactly as printed, including page ranges"; consider dropping `Id.` short forms from `record_citations` |
| **L4 boundary drift run-to-run** | seen on 406937652 (2 runs: end 25754 vs 24455) | same doc, different end anchor | nondeterminism at effort=medium | measure on a 10-doc × 3-run repeat before v2; cheap with the cache keyed per run label |
| **L5 transient CLI error** | 2 (g018, g061), both succeeded on retry | `claude reported an error: None` | subscription-side hiccup | harness retries once on CLI error |

Operational: span found 68.3 % (rules 83.3 %) — the gap is R1 + L2, not missed sections; validator pass 48.3 %; cost/doc $0.276 at the CLI's API-rate estimate (≈114k cache-creation tokens per call because the CLI prepends its own system prompt; an API-backend call would be ~30k tokens ≈ $0.06); latency 31.6 s mean / 29.4 s median / p90 52 s.

## E. llm-v2 (prompt v2 + anchor relaxation + CLI retry) — run `evals/runs/llm-v2-all_20260915-040449_c762da`, 120 docs, 0 errors

What changed and what it did, class by class (same 120 docs, rules_v2 and llm-v1 from cache):

| class | v1 | v2 | verdict |
|---|---|---|---|
| **L1 invented span on a non-brief** | f013 (docket sheet), f019 | f019 only | fixed for the docket sheet; f019 (a bankruptcy filing with a real PRELIMINARY STATEMENT / STATEMENT OF THE CASE) is for the labeler |
| **L2 anchor not found** | 11 docs → span null | **8** not found; **9** more rescued by 8/6/4-word relaxation (`*_anchor_relaxed` notes) | improved; the remaining 8 need the stored anchors (`provenance.anchors`, present from v2 on) to diagnose |
| **L3 non-verbatim citation** | 3,144 cites: 41 list/range expansions, 31 unsupported (16 docs) | 3,978 cites (+27 %): **152** expansions, **49** unsupported (23 docs) | the "copy exactly as printed" instruction did *not* stop expansion; the model normalises list/range shorthand regardless. Handled on the metric side instead: **citation support** (verbatim *or* component-supported) is 0.991 (v1) / 0.985 (v2); strict verbatim fidelity 0.981 / 0.962. Residual unsupported cites are composite forms the component check cannot parse (`Doc. 181 at 19:25-20:8, …`, `Appx01571; Appx01574-01575 (ECF 315-07 …)`), OCR glyphs (`1-ER-6l-62`, `¶¶`), and a few genuine errors. 18 of the 49 are in one document (g071). |
| **L4 boundary drift run-to-run** | one anecdote (406937652: 25754 vs 24455) | measured: **10 docs × 3 runs, 30/30 pairs IoU ≥ 0.999** (9 identical, one 15-char tail difference) — `evals/runs/drift_llm-v2.json` | at effort=medium the extractor is effectively deterministic; a CI regression gate on IoU is meaningful |
| **L5 transient CLI error** | 2 | 0 (retry-once wired; no retries were needed in this run) | closed |
| **R1 rules false-positive span** (audit docs the LLM calls no-facts) | 17 | the same 17 + 3 new: g008 (an appendix volume — v1 had extracted from it), g075, g084 (disorganised pro se brief) | consistent; labels decide |
| **A1 non-brief** (failure stratum) | 6/8 no span | **8/8** no span (f013 docket sheet and f010 — a district-court *order*, reclassified from A2 to A1 — now correctly no-facts) | fixed |
| **A2 heading fused with body** | 5/6 spans | 4/5 spans after moving f010 to A1 (f003, f006, f014, f018; not f005) | unchanged |
| **A3 title-case / numbered** | f001, f007, f014 | same | unchanged |
| **A4 present-but-missed** | f012 span | f012 now no-facts (a 4-page brief with only `III` as a heading); f002, f015 none | needs a look |

Aggregate: span found 65.8 % (v1 68.3 %) — the drop is entirely the 6 new `has_facts=false` verdicts, 3 of which are demonstrably right (g008, f010, f013); validator pass 48.3 % (v1 55.0 %) — driven by the +27 % citation volume meeting a strict check; rules↔v2 agreement 0.507 mean / 0.585 median (v1 0.478 / 0.442), 0.838 mean / 0.983 median where rules are `high`; **v1↔v2 agreement 0.813 mean, median 1.0, 92/120 docs ≥ 0.9** — the prompt change moved the documents it was aimed at and left the rest alone; cost $0.274/doc, 34 s/doc.

Open for v3 (after labels): (a) L3 — either restrict `record_citations` to a stricter "as printed, no splitting" rule with an example, or accept expansion as desired behaviour and make *support* the headline metric; (b) the 8 residual L2 anchor failures; (c) f019 / A4 once labeled.

## F. Opus 5 judge pass (`evals/judge/judge-v1_20260915-153046_975e61`, 120 docs, 0 errors, 16.7 s/doc, $128 CLI estimate — subscription-billed)

Noah asked for a strong-model review before human labeling, on the grounds that the obvious mistakes do not need
human nuance. The judge (D2, `claude-opus-5`, effort high) read every document with both candidate spans marked
inline, classified the document, rated each candidate with the labeling rubric, coded the issues, and proposed
corrected anchors. Consistency checks: 0 contradictions (never "correct" for an empty span where it says facts
exist, or for a non-empty span where it says none exists); the 33 near-identical A/B spans all received identical
ratings. Confidence was `high` on 119/120.

**Document kinds:** merits brief 83 · reply brief 17 · amicus 8 · clerk letter 5 · appendix/exhibits 2 · docket
sheet/form 2 · motion 1 · declaration 1 · court order 1. **No facts section: 33 docs** (25 in the audit set — up
from the LLM's 17 — plus 8 in the failure stratum).

**Ratings (rules_v2 / llm-v2):** audit set 38 correct · 21 partial · 41 incorrect / 91 · 1 · 8; failure stratum
13 · 0 · 7 / 19 · 1 · 0. Preferred B on 90, tie 19, A 11.

**Where the rules go wrong (issue codes on rules_v2):** starts_early 39, includes_cover_or_toc 34,
no_facts_section_exists 25, wrong_section 20, includes_argument 19, ends_late 13, includes_summary_of_argument 12,
span_empty 7, attachment_used 6, ends_early 5, not_a_brief 4, includes_addendum_or_statutes 3. Read together: the
pre-ARGUMENT fallback and TOC bleed-in dominate, i.e. the same `fallback_pre_argument` / `toc_contamination` /
`span_starts_very_early` notes from §B, now with a verdict attached. Rules rating by rules confidence: **high**
37 / 16 / 8, **medium** 1 / 5 / 10, **low** 0 / 0 / 23 — every low-confidence span is wrong.

**Where llm-v2 goes wrong:** span_empty 8 (the residual L2 anchor failures: g033, g034, g056, g067, g078, g080,
g092, g097 — the judge located the facts section on 7 of them, so anchors exist), starts_early 2 (g029, f019),
includes_argument 1, ends_early 3 (blemishes, still rated correct).

**Corrected anchors:** located on 58 docs (1 unlocatable); 47 coincide with llm-v2's span (IoU ≥ 0.95), 7 fill
llm-v2's empty spans, 3 overlap partially, 1 differs.

**Preview of gold-referenced metrics if the judge's verdicts were accepted as labels (in memory, not applied):**

| method | IoU vs judge-gold (mean / median) | IoU ≥ 0.9 | recovered span (failure stratum) | no-facts verdicts correct | paired vs rules |
|---|---|---|---|---|---|
| rules_v2 | 0.565 / 0.766 | 45.8 % | 0 % | 100 % (rules never emits a span on those) | — |
| llm-v1 | 0.823 / 1.000 | 78.0 % | 85.7 % | 76.9 % | — |
| llm-v2 | **0.928 / 1.000** | **91.5 %** | 85.7 % | 100 % | wins 73 / ties 37 / losses 8, mean ΔIoU +0.363 |

By rules confidence, llm-v2 IoU is 0.905 (`high`), 0.861 (`medium`), 0.996 (`low`); rules_v2 is 0.811 / 0.307 /
0.039. The IoU auto-rating (≥ 0.9 correct, ≥ 0.5 partial) agrees with the judge's rubric rating of the rules span
on 92.9 % of 98 docs — the thresholds are usable.

**Caveats.** (1) Judge and llm-v2 are both Claude models; a same-family preference is possible, and the judge's
"corrected" anchors coincide with llm-v2's span 47 times out of 58. (2) The two human labels so far (g001, g002)
agree with the judge on has_facts and, for g001, on the span to within one character, but Noah rated the rules
span `partially_correct` where the judge said `correct` (the addendum sentence) — a rubric-boundary call. Judge
verdicts are therefore held as **suggestions** (`legallm-gold prefill`) with an explicit accept policy and a
separate `labeler="judge:…"` tag; human labels on an overlap of ≥ 30 docs are still required for κ.

### F.1 Human review of the judge (2026-09-15, Noah, 35 docs)

Noah reviewed 35 documents (the 2 the judge left unresolved, the 19 it rated `partially_correct`, and 3 sampled
per accept policy), accepting the judge's suggestion where it matched his reading and overriding otherwise
(4 own labels, 31 accepted-with-review). **Judge ↔ human:** 3-class rating κ = **0.885** (agreement 93.9 %, n = 33
rules spans); has-facts κ = **1.00** (n = 35); span IoU between the human gold span and the judge's suggested span
0.935 mean, 29/31 ≥ 0.9. The only rating disagreements are two rubric-boundary calls: g001 (Noah: partially
correct — the rules span starts on the heading and a stray sentence; judge: correct) and g052 (Noah: correct;
judge: partially correct). This clears the intent's κ ≥ 0.4 threshold for using the judge as a headline metric,
and the 85 judge-accepted labels stay tagged `judge:claude-opus-5` so the two label sources remain separable.

Gold-referenced results after the review (`evals/runs/labeled-human_20260915-223814_a0177c` and `evals/runs/labeled-any_20260915-224235_c0ac4e`):

| method | human-only gold (n=35): IoU mean / ≥0.9 | all gold (n=120, 85 judge-accepted): IoU mean / ≥0.9 | recovered span (failure stratum, all) | no-facts verdicts correct (all) |
|---|---|---|---|---|
| rules_v2 | 0.647 / 34.3% | 0.572 / 46.7% | 0.0% | 100.0% |
| llm-v1 | 0.826 / 74.3% | 0.814 / 76.7% | 85.7% | 76.9% |
| llm-v2 | 0.869 / 85.7% | 0.912 / 90.0% | 85.7% | 100.0% |

llm-v2 vs rules_v2, paired on human-only gold: wins 25 / ties 5 / losses 5, mean ΔIoU +0.222;
on all gold: wins 73 / ties 37 / losses 10, ΔIoU +0.340.

## G. Downstream consequences (item 10, `evals/runs/labeled-any_20260915-224235_c0ac4e/downstream.md`)

The rules spans' citation-resolution advantage is an artifact of classes §B/§F *includes_argument*, *includes_cover_or_toc*
and R1 (spans on non-briefs): 965 unique case cites across 100 spans vs 158 in the 87 gold spans;
192 resolved targets on 11 documents that have no facts section at all. Only 15.1% of rules
targets are citations the gold facts section contains. llm-v2's remaining downstream loss is L2 (anchor failures →
empty span → no targets) and 10 citations the resolver cache has never seen (not queried, R5): target recall
67.6% at 95.9% precision. Retrieval (BM25 Recall@10) is flat across span sources including the gold
span, so the retrieval task's ceiling is the retriever, not extraction — consistent with the April M4 result.

## H. Routing (llm-v3, item 11, `evals/runs/labeled-v3_20260916-001818_90b33c`)

**What routes.** Trigger set: `anchor_not_found` (has_facts said yes, span not located — class L2), `span_text_mismatch`
/ `span_out_of_bounds` (validator), `error` (cheap call failed — L5). `unsupported_citation` is deliberately *not* a
trigger: L3 list/range expansion fires on ~20 % of docs, the judge rated those spans correct, and the strong tier
shares the habit. A cheap-tier `has_facts = false` never escalates (judge: 33/33 correct).

**What happened on the gold set.** 8 of 120 documents escalated, every one on `anchor_not_found` — exactly the 8
residual L2 failures from §D (g033, g034, g056, g067, g078, g080, g092, g097). Opus 5 (prompt v2, effort high)
located a span on all 8: seven at IoU ≥ 0.99 against gold; g034 at 0.52 (it started at a later heading than the
gold span, which begins at 3,641 — a partially_correct outcome rather than an empty span). No escalation on any
other document, so llm-v3 = llm-v2 on 112/120 docs by construction.

**Effect.** IoU 0.912 → **0.975**; IoU ≥ 0.9 on 90.0% → **95.8%**;
span found 65.8% → 72.5% (the remaining 33 no-span docs are the no-facts
documents). Paired vs rules_v2: wins 77 / ties 40 / losses 3. Cost 0.274 → 0.331 $/doc
(CLI estimate; the 8 Opus calls total $9.35, $0.44–2.50 each); latency 34.4 → 37.4 s/doc
mean, ≈ 99 s on an escalated document. Downstream: resolved-target recall vs the gold span 67.6% →
79.0% at 96.5% precision; BM25 Recall@10 0.145 (gold span 0.143) — flat, as in §G.

**Why L2 happens at all (and why routing rather than a prompt fix).** The 8 failures are long briefs where Sonnet's
anchors quote text that the PDF layer rendered differently (dropped hyphens, merged headers, ligatures) — the 8/6/4-word
relaxation in llm-v2 already recovered 9 similar cases; what remained needed a model that copies the printed text
exactly. A third prompt iteration on Sonnet would be guesswork; escalation is measurable, costs 6.7 % of docs, and
keeps the cheap tier's verdict everywhere it was right.

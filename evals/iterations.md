# Iteration log (C9)

One row per prompt / model / routing / chunking change. No change ships without a before/after row
(intent.md §7.6). Numbers come from `evals/runs/<run_id>/summary.json`; "gold n" is the number of
human-labeled documents the IoU column is computed on.

| version | date | change | motivated by (taxonomy class) | run | gold n | IoU vs gold | agreement w/ rules | span found | validator pass | cite fidelity (verbatim / support) | cost/doc | latency/doc |
|---|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| rules_v2 | 2026-04 | frozen baseline (heading map → merge → validate) | — | `rules-baseline_20260915-005115_a87a80` | 120 (35 human) | 0.572 (all, n=120) / 0.647 (human, n=35) | — | 83.3% | 83.3% | 1.000 | $0 | 0.01 s |
| llm-v1 | 2026-09-14 | first LLM extractor: Sonnet 5, prompt v1 (`prompt_sha` in run manifest), anchor-based span, effort=medium, head-window ≤ 400k chars, `claude-cli` backend | — (baseline) | `llm-v1-all_20260915-021057_0c9ab4` | 120 (35 human) | 0.814 (all, n=120) / 0.826 (human, n=35) | 0.478 mean / 0.442 median (≥0.9 on 36.7%) | 68.3% | 48.3% | 0.981 | $0.276 (CLI est.) | 31.6 s |
| llm-v2 | 2026-09-15 | prompt v2: decide has_facts first (non-briefs, reply/amicus/motions), never extract from attachments, headings may be title-case/numbered/fused, anchors one contiguous run never crossing a page header, cites copied as printed (no range expansion, no Id./supra); code: 8/6/4-word anchor relaxation, one CLI retry | R1, L1, L2, L3, L5, A2, A3 | `llm-v2-all_20260915-040449_c762da` | 120 (35 human) | 0.912 (all, n=120) / 0.869 (human, n=35) | 0.507 mean / 0.585 median (≥0.9 on 40.8%); v1↔v2 0.813 / 1.000 | 65.8% | 48.3% | 0.962 verbatim / 0.985 support | $0.274 (CLI est.) | 34.4 s |

## Notes

- **2026-09-15 · Downstream (item 10)** (`evals/runs/labeled-any_20260915-224235_c0ac4e/downstream.md`): resolved-target precision vs the gold span rules_v2 15.1% / llm-v1 88.5% / llm-v2 95.9%; recall 90.5% / 65.7% / 67.6%. Rules' higher raw resolution rate (42.5% vs 24.2%) is leakage from Argument/TOC text (192 targets on no-facts docs). BM25 Recall@10 on the 31 gold docs with targets: 0.126 / 0.145 / 0.120 (gold span 0.143) — flat; retrieval is bottlenecked by BM25, not by the span.

- **2026-09-15 · Gold labels complete (120/120): 35 human, 85 judge-accepted.** Judge↔human κ 0.885 (rating), 1.00 (has_facts), span IoU 0.935 — the judge is validated. Headline on human-only gold (n=35): llm-v2 IoU 0.869 vs rules_v2 0.647; on all gold (n=120): 0.912 vs 0.572. The IoU-vs-gold column in the table above is now filled from the all-gold run.

- **2026-09-15 · Opus 5 judge pass** (`evals/judge/judge-v1_20260915-153046_975e61`, taxonomy §F): rules_v2 rated correct on only 38/100 audit docs (41 incorrect); llm-v2 on 91/100. 33 documents have no facts section at all. If judge verdicts are taken as gold, llm-v2 IoU 0.928 vs rules 0.565; paired wins 73 / ties 37 / losses 8. Verdicts are attached to the gold set as suggestions; acceptance policy and the human overlap for κ are Noah's call.

- **2026-09-15 · llm-v2** (taxonomy §E): fixed L1 on the docket sheet and L5; anchor relaxation rescued 9 spans and cut hard anchor failures 11→8; the has_facts gate now returns no-facts on all 8 non-briefs in the failure stratum. The citation instruction did not change the model's habit of expanding list/range cites, so the validator gained a second tier: *citation support* accepts a cite whose page numbers are printed near the same prefix; strict verbatim fidelity is still reported. **Drift measured:** 10 docs × 3 runs, 30/30 pairs IoU ≥ 0.999 — effectively deterministic at effort=medium. v1↔v2 span agreement median 1.0: the prompt change was surgical.

- **2026-09-14 · llm-v1 first run, read with `evals/error_taxonomy.md` §D:** the LLM's lower span-found rate is
  dominated by 17 audit docs it declares to have *no facts section* (first logged as 27, a count that included 10 failure-stratum docs) (reply/amicus briefs where the rules emitted a
  low-confidence fallback span) and 11 anchor failures. Agreement with the rules is high exactly where the rules
  are confident (median IoU 0.98 on `high`) and low where they are not (0.11 on `low`). Gold labels decide who is
  right; until then no accuracy claim is made. Validator change in this iteration: citation fidelity ignores
  hyphens (PDF extraction drops them unpredictably), which reclassified 92 of 164 flagged cites as verbatim.

- **2026-09-14 · llm-v1 design choices, logged for later ablation:** verbatim start/end anchors instead of offsets
  or full-text return (cheap output, exact offsets); system text folded into the stdin prompt for the CLI
  backend; Claude Code's own system prompt is prepended by the CLI (≈ 60k cached tokens/call), which the API
  backend would not carry.
- Rating thresholds for the auto-rating (IoU ≥ 0.9 / ≥ 0.5) are provisional until the human↔auto confusion
  table in the run report says otherwise.

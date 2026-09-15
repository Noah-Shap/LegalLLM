# Extraction eval — run labeled-judge_20260915-154355_583547

- gold: `evals\gold\gold_v1.jsonl` · subset **labeled** · docs 118 (gold-labeled 118) · 2026-09-15T15:43:55.459048+00:00
- **rules_v2**: version `rules_v2` · backend `local` · model `None` · prompt `None`
- **llm-v1**: version `llm-v1` · backend `claude-cli` · model `claude-sonnet-5` · prompt `2e9b97f8dcd48884`
- **llm-v2**: version `llm-v2` · backend `claude-cli` · model `claude-sonnet-5` · prompt `aa4020336ae219ec`

## Gold-referenced metrics (labeled docs only)

| method | n gold | IoU mean | IoU median | IoU≥0.9 | IoU≥0.5 | span found | validator pass | empty facts | cite fidelity | docs w/ unsupported cites | recovered (failure stratum) | auto↔human agree | cost/doc | latency/doc |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| rules_v2 | 118 | 0.565 | 0.766 | 45.8% | 56.8% | 83.0% | 83.0% | 17.0% | 1.000 | 0/62 | 0.0% (n=20) | 92.9% (n=98) | — | 0.009s |
| llm-v1 | 118 | 0.823 | 1.000 | 78.0% | 83.0% | 67.8% | 54.2% | 32.2% | 0.981 | 16/90 | 85.7% (n=20) | 43.9% (n=98) | $0.2779 | 31.704s |
| llm-v2 | 118 | 0.928 | 1.000 | 91.5% | 92.4% | 66.1% | 48.3% | 33.9% | 0.961 | 23/84 | 85.7% (n=20) | 33.7% (n=98) | $0.2753 | 34.078s |

Auto-rating thresholds: IoU ≥ 0.9 → correct, ≥ 0.5 → partially_correct, else incorrect. Span-found / validator / fidelity / cost / latency columns use **all** docs in the subset.

### rules_v2: auto-rating vs human rating (human→auto)

| pair | n |
|---|---:|
| correct->correct | 37 |
| incorrect->incorrect | 41 |
| partially_correct->correct | 4 |
| partially_correct->incorrect | 3 |
| partially_correct->partially_correct | 13 |

### llm-v1: auto-rating vs human rating (human→auto)

| pair | n |
|---|---:|
| correct->correct | 32 |
| correct->incorrect | 4 |
| correct->partially_correct | 1 |
| incorrect->correct | 29 |
| incorrect->incorrect | 9 |
| incorrect->partially_correct | 3 |
| partially_correct->correct | 15 |
| partially_correct->incorrect | 3 |
| partially_correct->partially_correct | 2 |

### llm-v2: auto-rating vs human rating (human→auto)

| pair | n |
|---|---:|
| correct->correct | 32 |
| correct->incorrect | 5 |
| incorrect->correct | 39 |
| incorrect->incorrect | 1 |
| incorrect->partially_correct | 1 |
| partially_correct->correct | 18 |
| partially_correct->incorrect | 2 |

## Agreement between methods (all docs, no gold needed)

| pair | n | IoU mean | IoU median | IoU≥0.9 |
|---|---:|---:|---:|---:|
| rules_v2 ↔ llm-v1 | 118 | 0.480 | 0.442 | 37.3% |
| rules_v2 ↔ llm-v2 | 118 | 0.515 | 0.621 | 41.5% |
| llm-v1 ↔ llm-v2 | 118 | 0.821 | 1.000 | 78.0% |

## Stratified by source (n docs/gold · gold-referenced IoU mean · span found · validator pass)

| source | rules_v2 | llm-v1 | llm-v2 |
|---|---|---|---|
| audit_set | n=98/98 · 0.548 · 100.0% · 100.0% | n=98/98 · 0.824 · 71.4% · 55.1% | n=98/98 · 0.919 · 72.5% · 52.0% |
| no_facts_span | n=20/20 · 0.650 · 0.0% · 0.0% | n=20/20 · 0.816 · 50.0% · 50.0% | n=20/20 · 0.968 · 35.0% · 30.0% |

## Stratified by confidence (n docs/gold · gold-referenced IoU mean · span found · validator pass)

| confidence | rules_v2 | llm-v1 | llm-v2 |
|---|---|---|---|
| high | n=59/59 · 0.811 · 100.0% · 100.0% | n=59/59 · 0.852 · 88.1% · 67.8% | n=59/59 · 0.905 · 84.8% · 55.9% |
| low | n=23/23 · 0.039 · 100.0% · 100.0% | n=23/23 · 0.887 · 39.1% · 30.4% | n=23/23 · 0.996 · 47.8% · 43.5% |
| medium | n=16/16 · 0.307 · 100.0% · 100.0% | n=16/16 · 0.630 · 56.2% · 43.8% | n=16/16 · 0.861 · 62.5% · 50.0% |
| none | n=20/20 · 0.650 · 0.0% · 0.0% | n=20/20 · 0.816 · 50.0% · 50.0% | n=20/20 · 0.968 · 35.0% · 30.0% |

## Stratified by len_bin (n docs/gold · gold-referenced IoU mean · span found · validator pass)

| len_bin | rules_v2 | llm-v1 | llm-v2 |
|---|---|---|---|
| long (15-30K chars) | n=31/31 · 0.764 · 100.0% · 100.0% | n=31/31 · 0.760 · 77.4% · 51.6% | n=31/31 · 0.892 · 87.1% · 61.3% |
| medium (5-15K chars) | n=37/37 · 0.537 · 100.0% · 100.0% | n=37/37 · 0.928 · 64.9% · 56.8% | n=37/37 · 0.959 · 67.6% · 54.0% |
| n/a | n=20/20 · 0.650 · 0.0% · 0.0% | n=20/20 · 0.816 · 50.0% · 50.0% | n=20/20 · 0.968 · 35.0% · 30.0% |
| short (<5K chars) | n=15/15 · 0.200 · 100.0% · 100.0% | n=15/15 · 0.733 · 66.7% · 60.0% | n=15/15 · 0.933 · 53.3% · 40.0% |
| very long (>30K chars) | n=15/15 · 0.475 · 100.0% · 100.0% | n=15/15 · 0.789 · 80.0% · 53.3% | n=15/15 · 0.867 · 73.3% · 40.0% |

## llm-v1 vs rules_v2 (paired, gold-referenced)

- pairs: 118 · IoU delta mean: 0.258 · wins 65 / ties 38 / losses 15 (±0.01)

Worst 10 docs for llm-v1:

| IoU | gold_id | source | confidence | notes |
|---:|---|---|---|---|
| 0.000 | f010 | no_facts_span | high | Facts are under heading 'II. BACKGROUND'; section is factual/procedural backgrou |
| 0.000 | f012 | no_facts_span | medium | This is a reply brief with no dedicated Statement of Facts heading; factual narr |
| 0.000 | f013 | no_facts_span | high | Document is a docket sheet plus attached Report and Recommendation; facts extrac |
| 0.000 | g008 | audit_set | low | This document is primarily an Appendix of Documents Designated for Appeal (an in |
| 0.000 | g013 | audit_set | high | Facts section merges an argumentative INTRODUCTION with the PROCEDURAL HISTORY s |
| 0.000 | g014 | audit_set | high | Facts section (STATEMENT) merged with procedural history subsection D.;Footnotes |
| 0.000 | g015 | audit_set | high | Facts are presented as a reply-brief timeline titled FACTUAL AND PROCEDURAL BACK |
| 0.000 | g019 | audit_set | high | Statement of the Case includes both a statutory-framework subsection and factual |
| 0.000 | g067 | audit_set | medium | The brief contains two distinct factual narratives separated by an argument-heav |
| 0.000 | g068 | audit_set | high | Facts section merged with detailed procedural history (STATEMENT OF THE CASE wit |

## llm-v2 vs rules_v2 (paired, gold-referenced)

- pairs: 118 · IoU delta mean: 0.363 · wins 73 / ties 37 / losses 8 (±0.01)

Worst 10 docs for llm-v2:

| IoU | gold_id | source | confidence | notes |
|---:|---|---|---|---|
| 0.000 | g033 | audit_set | high | Facts section comprises STATEMENT OF THE CASE parts A (Statutory and Regulatory  |
| 0.000 | g056 | audit_set | high | STATEMENT OF THE CASE includes both factual background (Part I) and procedural b |
| 0.000 | g067 | audit_set | medium | The brief contains two factual narratives: the numbered 'Statement of Relevant F |
| 0.000 | g078 | audit_set | high | Facts section corresponds to 'II. STATEMENT OF THE CASE' (with subsections A. As |
| 0.000 | g080 | audit_set | high | Facts section is STATEMENT OF THE CASE, comprising subsection A (Facts Alleged)  |
| 0.000 | g092 | audit_set | high | Facts section includes narrative paragraph, numbered 'Factual and Procedural Bac |
| 0.000 | g097 | audit_set | high | Document contains multiple attached filings after the appellant's brief (the cer |
| 0.376 | f019 | no_facts_span | high | Facts section combines the factual portions of the PRELIMINARY STATEMENT with th |
| 0.479 | g029 | audit_set | high | Facts section runs from the STATEMENT OF THE CASE heading through end of that se |
| 0.782 | g077 | audit_set | high | Facts extracted from subsections B (Factual Background) and C (Procedural Histor |

## Validator flags and extractor notes (all docs)

- **rules_v2** flags: {'empty_facts': 20}
- **rules_v2** notes: {'no_exact_heading': 35, 'span_starts_very_early': 27, 'toc_contamination': 23, 'merged_2_sections': 22, 'no_span_found': 20, 'no_citations_in_facts': 19, 'fallback_pre_argument': 15, 'low_alpha_ratio': 15, 'merged_3_sections': 11, 'merged_4_sections': 8, 'guardrail_truncated': 6, 'span_too_short': 6, 'merged_5_sections': 4, 'merged_6_sections': 4, 'merge_limit_warning': 3}
- **llm-v1** flags: {'nonverbatim_citation': 41, 'empty_facts': 38, 'unsupported_citation': 31, 'unparseable_date': 2}
- **llm-v1** notes: {'llm_no_facts': 27, 'end_anchor_not_found': 8, 'doc_truncated_to_window': 6, 'start_anchor_not_found': 3, 'has_facts set to false accordingly.': 1, 'Document is truncated.': 1}
- **llm-v2** flags: {'nonverbatim_citation': 152, 'unsupported_citation': 49, 'empty_facts': 40, 'unparseable_date': 1}
- **llm-v2** notes: {'llm_no_facts': 33, 'end_anchor_relaxed': 9, 'doc_truncated_to_window': 6, 'end_anchor_not_found': 6, 'start_anchor_not_found': 1}

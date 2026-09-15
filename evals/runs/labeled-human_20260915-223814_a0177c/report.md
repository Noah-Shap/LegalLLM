# Extraction eval — run labeled-human_20260915-223814_a0177c

- gold: `evals\gold\gold_v1.jsonl` · subset **labeled** · docs 35 (gold-labeled 35) · 2026-09-15T22:38:14.195460+00:00
- **rules_v2**: version `rules_v2` · backend `local` · model `None` · prompt `None`
- **llm-v1**: version `llm-v1` · backend `claude-cli` · model `claude-sonnet-5` · prompt `2e9b97f8dcd48884`
- **llm-v2**: version `llm-v2` · backend `claude-cli` · model `claude-sonnet-5` · prompt `aa4020336ae219ec`

## Gold-referenced metrics (labeled docs only)

| method | n gold | IoU mean | IoU median | IoU≥0.9 | IoU≥0.5 | span found | validator pass | empty facts | cite fidelity | docs w/ unsupported cites | recovered (failure stratum) | auto↔human agree | cost/doc | latency/doc |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| rules_v2 | 35 | 0.647 | 0.758 | 34.3% | 71.4% | 94.3% | 94.3% | 5.7% | 1.000 | 0/22 | 0.0% (n=2) | 75.8% (n=33) | — | 0.013s |
| llm-v1 | 35 | 0.826 | 1.000 | 74.3% | 85.7% | 82.9% | 62.9% | 17.1% | 0.982 | 8/32 | 100.0% (n=2) | 30.3% (n=33) | $0.3308 | 34.113s |
| llm-v2 | 35 | 0.869 | 1.000 | 85.7% | 85.7% | 80.0% | 51.4% | 20.0% | 0.970 | 12/31 | 100.0% (n=2) | 15.2% (n=33) | $0.3257 | 41.413s |

Auto-rating thresholds: IoU ≥ 0.9 → correct, ≥ 0.5 → partially_correct, else incorrect. Span-found / validator / fidelity / cost / latency columns use **all** docs in the subset.

### rules_v2: auto-rating vs human rating (human→auto)

| pair | n |
|---|---:|
| correct->correct | 7 |
| incorrect->incorrect | 5 |
| partially_correct->correct | 5 |
| partially_correct->incorrect | 3 |
| partially_correct->partially_correct | 13 |

### llm-v1: auto-rating vs human rating (human→auto)

| pair | n |
|---|---:|
| correct->correct | 6 |
| correct->incorrect | 1 |
| incorrect->correct | 3 |
| incorrect->incorrect | 1 |
| incorrect->partially_correct | 1 |
| partially_correct->correct | 15 |
| partially_correct->incorrect | 3 |
| partially_correct->partially_correct | 3 |

### llm-v2: auto-rating vs human rating (human→auto)

| pair | n |
|---|---:|
| correct->correct | 5 |
| correct->incorrect | 2 |
| incorrect->correct | 5 |
| partially_correct->correct | 18 |
| partially_correct->incorrect | 3 |

## Agreement between methods (all docs, no gold needed)

| pair | n | IoU mean | IoU median | IoU≥0.9 |
|---|---:|---:|---:|---:|
| rules_v2 ↔ llm-v1 | 35 | 0.531 | 0.652 | 22.9% |
| rules_v2 ↔ llm-v2 | 35 | 0.544 | 0.653 | 25.7% |
| llm-v1 ↔ llm-v2 | 35 | 0.811 | 1.000 | 71.4% |

## Stratified by source (n docs/gold · gold-referenced IoU mean · span found · validator pass)

| source | rules_v2 | llm-v1 | llm-v2 |
|---|---|---|---|
| audit_set | n=33/33 · 0.686 · 100.0% · 100.0% | n=33/33 · 0.817 · 81.8% · 60.6% | n=33/33 · 0.861 · 78.8% · 51.5% |
| no_facts_span | n=2/2 · 0.000 · 0.0% · 0.0% | n=2/2 · 0.969 · 100.0% · 100.0% | n=2/2 · 1.000 · 100.0% · 50.0% |

## Stratified by confidence (n docs/gold · gold-referenced IoU mean · span found · validator pass)

| confidence | rules_v2 | llm-v1 | llm-v2 |
|---|---|---|---|
| high | n=25/25 · 0.796 · 100.0% · 100.0% | n=25/25 · 0.771 · 88.0% · 68.0% | n=25/25 · 0.857 · 88.0% · 60.0% |
| low | n=3/3 · 0.000 · 100.0% · 100.0% | n=3/3 · 1.000 · 0.0% · 0.0% | n=3/3 · 1.000 · 0.0% · 0.0% |
| medium | n=5/5 · 0.551 · 100.0% · 100.0% | n=5/5 · 0.939 · 100.0% · 60.0% | n=5/5 · 0.800 · 80.0% · 40.0% |
| none | n=2/2 · 0.000 · 0.0% · 0.0% | n=2/2 · 0.969 · 100.0% · 100.0% | n=2/2 · 1.000 · 100.0% · 50.0% |

## Stratified by len_bin (n docs/gold · gold-referenced IoU mean · span found · validator pass)

| len_bin | rules_v2 | llm-v1 | llm-v2 |
|---|---|---|---|
| long (15-30K chars) | n=11/11 · 0.828 · 100.0% · 100.0% | n=11/11 · 0.785 · 81.8% · 54.5% | n=11/11 · 0.995 · 100.0% · 63.6% |
| medium (5-15K chars) | n=12/12 · 0.723 · 100.0% · 100.0% | n=12/12 · 0.986 · 83.3% · 66.7% | n=12/12 · 0.957 · 83.3% · 66.7% |
| n/a | n=2/2 · 0.000 · 0.0% · 0.0% | n=2/2 · 0.969 · 100.0% · 100.0% | n=2/2 · 1.000 · 100.0% · 50.0% |
| short (<5K chars) | n=3/3 · 0.333 · 100.0% · 100.0% | n=3/3 · 0.382 · 66.7% · 66.7% | n=3/3 · 0.667 · 33.3% · 33.3% |
| very long (>30K chars) | n=7/7 · 0.553 · 100.0% · 100.0% | n=7/7 · 0.765 · 85.7% · 57.1% | n=7/7 · 0.571 · 57.1% · 14.3% |

## llm-v1 vs rules_v2 (paired, gold-referenced)

- pairs: 35 · IoU delta mean: 0.179 · wins 21 / ties 7 / losses 7 (±0.01)

Worst 10 docs for llm-v1:

| IoU | gold_id | source | confidence | notes |
|---:|---|---|---|---|
| 0.000 | g008 | audit_set | low | This document is primarily an Appendix of Documents Designated for Appeal (an in |
| 0.000 | g019 | audit_set | high | Statement of the Case includes both a statutory-framework subsection and factual |
| 0.000 | g078 | audit_set | high | The brief's Section I (INTRODUCTION) is argumentative rather than factual, consi |
| 0.000 | g089 | audit_set | high | Facts section defined as the STATEMENT OF THE CASE (Parts I-VI), ending before S |
| 0.145 | g052 | audit_set | medium | Facts narrative (INTRODUCTION) is separated from the procedural 'Statement of th |
| 0.516 | g034 | audit_set | high | Facts section combines Statutory Background, Factual Background, and Procedural  |
| 0.694 | g095 | audit_set | high | Facts section spans Sections I-VI (STATEMENT OF THE CASE through RELEVANT FACTS  |
| 0.838 | g018 | audit_set | high | Facts section corresponds to Section IV, 'STATEMENT OF THE CASE,' which follows  |
| 0.841 | g066 | audit_set | high | STATEMENT OF FACTS follows a separate STATEMENT OF THE CASE section (procedural  |
| 0.940 | f006 | no_facts_span | high | Facts section is headed STATEMENT OF THE CASE and includes both factual narrativ |

## llm-v2 vs rules_v2 (paired, gold-referenced)

- pairs: 35 · IoU delta mean: 0.222 · wins 25 / ties 5 / losses 5 (±0.01)

Worst 10 docs for llm-v2:

| IoU | gold_id | source | confidence | notes |
|---:|---|---|---|---|
| 0.000 | g033 | audit_set | high | Facts section comprises STATEMENT OF THE CASE parts A (Statutory and Regulatory  |
| 0.000 | g034 | audit_set | high | Facts section corresponds to STATEMENT OF THE CASE, comprising A. Statutory Back |
| 0.000 | g052 | audit_set | medium | The INTRODUCTION section is a factual narrative (not argument) and was treated a |
| 0.000 | g078 | audit_set | high | Facts section corresponds to 'II. STATEMENT OF THE CASE' (with subsections A. As |
| 0.479 | g029 | audit_set | high | Facts section runs from the STATEMENT OF THE CASE heading through end of that se |
| 0.944 | g053 | audit_set | high | Facts section is IV. STATEMENT OF THE CASE, spanning A. Factual Background (with |
| 0.999 | g048 | audit_set | high | Statement of the Case includes an unusually extensive Legal Background subsectio |
| 1.000 | g001 | audit_set | high | Facts section combines 'I. Factual Background' and 'II. Procedural Background' u |
| 1.000 | f006 | no_facts_span | high | Facts section headed 'STATEMENT OF THE CASE' with heading fused onto first sente |
| 1.000 | f014 | no_facts_span | high | Facts section is 'Statement Of The Case' comprising 'I. Facts And Evidence' and  |

## Validator flags and extractor notes (all docs)

- **rules_v2** flags: {'empty_facts': 2}
- **rules_v2** notes: {'span_starts_very_early': 8, 'merged_3_sections': 8, 'no_citations_in_facts': 7, 'merged_2_sections': 7, 'toc_contamination': 6, 'no_exact_heading': 5, 'merged_4_sections': 4, 'fallback_pre_argument': 3, 'low_alpha_ratio': 3, 'merged_5_sections': 3, 'no_span_found': 2, 'merge_limit_warning': 1, 'merged_6_sections': 1, 'guardrail_truncated': 1}
- **llm-v1** flags: {'unsupported_citation': 12, 'nonverbatim_citation': 8, 'empty_facts': 6}
- **llm-v1** notes: {'doc_truncated_to_window': 4, 'llm_no_facts': 3, 'start_anchor_not_found': 2, 'has_facts set to false accordingly.': 1, 'end_anchor_not_found': 1}
- **llm-v2** flags: {'unsupported_citation': 33, 'nonverbatim_citation': 19, 'empty_facts': 7}
- **llm-v2** notes: {'llm_no_facts': 4, 'doc_truncated_to_window': 4, 'end_anchor_relaxed': 3, 'end_anchor_not_found': 3}

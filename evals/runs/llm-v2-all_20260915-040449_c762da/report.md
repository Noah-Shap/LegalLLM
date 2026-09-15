# Extraction eval — run llm-v2-all_20260915-040449_c762da

- gold: `evals\gold\gold_v1.jsonl` · subset **all** · docs 120 (gold-labeled 0) · 2026-09-15T04:04:48.930939+00:00
- **rules_v2**: version `rules_v2` · backend `local` · model `None` · prompt `None`
- **llm-v1**: version `llm-v1` · backend `claude-cli` · model `claude-sonnet-5` · prompt `2e9b97f8dcd48884`
- **llm-v2**: version `llm-v2` · backend `claude-cli` · model `claude-sonnet-5` · prompt `aa4020336ae219ec`

## Gold-referenced metrics (labeled docs only)

| method | n gold | IoU mean | IoU median | IoU≥0.9 | IoU≥0.5 | span found | validator pass | empty facts | cite fidelity | docs w/ unsupported cites | recovered (failure stratum) | auto↔human agree | cost/doc | latency/doc |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| rules_v2 | 0 | — | — | — | — | 83.3% | 83.3% | 16.7% | 1.000 | 0/63 | — (n=0) | — (n=0) | — | 0.009s |
| llm-v1 | 0 | — | — | — | — | 68.3% | 55.0% | 31.7% | 0.981 | 16/92 | — (n=0) | — (n=0) | $0.2758 | 31.632s |
| llm-v2 | 0 | — | — | — | — | 65.8% | 48.3% | 34.2% | 0.962 | 23/86 | — (n=0) | — (n=0) | $0.2742 | 34.366s |

Auto-rating thresholds: IoU ≥ 0.9 → correct, ≥ 0.5 → partially_correct, else incorrect. Span-found / validator / fidelity / cost / latency columns use **all** docs in the subset.

## Agreement between methods (all docs, no gold needed)

| pair | n | IoU mean | IoU median | IoU≥0.9 |
|---|---:|---:|---:|---:|
| rules_v2 ↔ llm-v1 | 120 | 0.478 | 0.442 | 36.7% |
| rules_v2 ↔ llm-v2 | 120 | 0.507 | 0.585 | 40.8% |
| llm-v1 ↔ llm-v2 | 120 | 0.813 | 1.000 | 76.7% |

## Stratified by source (n docs/gold · gold-referenced IoU mean · span found · validator pass)

| source | rules_v2 | llm-v1 | llm-v2 |
|---|---|---|---|
| audit_set | n=100/0 · — · 100.0% · 100.0% | n=100/0 · — · 72.0% · 56.0% | n=100/0 · — · 72.0% · 52.0% |
| no_facts_span | n=20/0 · — · 0.0% · 0.0% | n=20/0 · — · 50.0% · 50.0% | n=20/0 · — · 35.0% · 30.0% |

## Stratified by confidence (n docs/gold · gold-referenced IoU mean · span found · validator pass)

| confidence | rules_v2 | llm-v1 | llm-v2 |
|---|---|---|---|
| high | n=61/0 · — · 100.0% · 100.0% | n=61/0 · — · 88.5% · 68.8% | n=61/0 · — · 83.6% · 55.7% |
| low | n=23/0 · — · 100.0% · 100.0% | n=23/0 · — · 39.1% · 30.4% | n=23/0 · — · 47.8% · 43.5% |
| medium | n=16/0 · — · 100.0% · 100.0% | n=16/0 · — · 56.2% · 43.8% | n=16/0 · — · 62.5% · 50.0% |
| none | n=20/0 · — · 0.0% · 0.0% | n=20/0 · — · 50.0% · 50.0% | n=20/0 · — · 35.0% · 30.0% |

## Stratified by len_bin (n docs/gold · gold-referenced IoU mean · span found · validator pass)

| len_bin | rules_v2 | llm-v1 | llm-v2 |
|---|---|---|---|
| long (15-30K chars) | n=31/0 · — · 100.0% · 100.0% | n=31/0 · — · 77.4% · 51.6% | n=31/0 · — · 87.1% · 61.3% |
| medium (5-15K chars) | n=37/0 · — · 100.0% · 100.0% | n=37/0 · — · 64.9% · 56.8% | n=37/0 · — · 67.6% · 54.0% |
| n/a | n=20/0 · — · 0.0% · 0.0% | n=20/0 · — · 50.0% · 50.0% | n=20/0 · — · 35.0% · 30.0% |
| short (<5K chars) | n=16/0 · — · 100.0% · 100.0% | n=16/0 · — · 68.8% · 62.5% | n=16/0 · — · 56.2% · 43.8% |
| very long (>30K chars) | n=16/0 · — · 100.0% · 100.0% | n=16/0 · — · 81.2% · 56.2% | n=16/0 · — · 68.8% · 37.5% |

## llm-v1 vs rules_v2 (paired, gold-referenced)

- pairs: 0 · IoU delta mean: — · wins 0 / ties 0 / losses 0 (±0.01)

## llm-v2 vs rules_v2 (paired, gold-referenced)

- pairs: 0 · IoU delta mean: — · wins 0 / ties 0 / losses 0 (±0.01)

## Validator flags and extractor notes (all docs)

- **rules_v2** flags: {'empty_facts': 20}
- **rules_v2** notes: {'no_exact_heading': 35, 'span_starts_very_early': 28, 'toc_contamination': 23, 'merged_2_sections': 22, 'no_span_found': 20, 'no_citations_in_facts': 19, 'fallback_pre_argument': 15, 'low_alpha_ratio': 15, 'merged_3_sections': 11, 'merged_4_sections': 9, 'guardrail_truncated': 6, 'span_too_short': 6, 'merged_5_sections': 4, 'merged_6_sections': 4, 'merge_limit_warning': 3}
- **llm-v1** flags: {'nonverbatim_citation': 41, 'empty_facts': 38, 'unsupported_citation': 31, 'unparseable_date': 2}
- **llm-v1** notes: {'llm_no_facts': 27, 'end_anchor_not_found': 8, 'doc_truncated_to_window': 6, 'start_anchor_not_found': 3, 'has_facts set to false accordingly.': 1, 'Document is truncated.': 1}
- **llm-v2** flags: {'nonverbatim_citation': 152, 'unsupported_citation': 49, 'empty_facts': 41, 'unparseable_date': 1}
- **llm-v2** notes: {'llm_no_facts': 33, 'end_anchor_relaxed': 9, 'end_anchor_not_found': 7, 'doc_truncated_to_window': 6, 'start_anchor_not_found': 1}

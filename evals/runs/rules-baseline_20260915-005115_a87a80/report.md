# Extraction eval — run rules-baseline_20260915-005115_a87a80

- gold: `evals\gold\gold_v1.jsonl` · subset **all** · docs 120 (gold-labeled 0) · 2026-09-15T00:51:15.579170+00:00
- **rules_v2**: version `rules_v2` · backend `local` · model `None` · prompt `None`

## Gold-referenced metrics (labeled docs only)

| method | n gold | IoU mean | IoU median | IoU≥0.9 | IoU≥0.5 | span found | validator pass | empty facts | cite fidelity | docs w/ unsupported cites | recovered (failure stratum) | auto↔human agree | cost/doc | latency/doc |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| rules_v2 | 0 | — | — | — | — | 83.3% | 83.3% | 16.7% | 1.000 | 0/63 | — (n=0) | — (n=0) | — | 0.009s |

Auto-rating thresholds: IoU ≥ 0.9 → correct, ≥ 0.5 → partially_correct, else incorrect. Span-found / validator / fidelity / cost / latency columns use **all** docs in the subset.

## Stratified by source (n docs/gold · gold-referenced IoU mean · span found · validator pass)

| source | rules_v2 |
|---|---|
| audit_set | n=100/0 · — · 100.0% · 100.0% |
| no_facts_span | n=20/0 · — · 0.0% · 0.0% |

## Stratified by confidence (n docs/gold · gold-referenced IoU mean · span found · validator pass)

| confidence | rules_v2 |
|---|---|
| high | n=61/0 · — · 100.0% · 100.0% |
| low | n=23/0 · — · 100.0% · 100.0% |
| medium | n=16/0 · — · 100.0% · 100.0% |
| none | n=20/0 · — · 0.0% · 0.0% |

## Stratified by len_bin (n docs/gold · gold-referenced IoU mean · span found · validator pass)

| len_bin | rules_v2 |
|---|---|
| long (15-30K chars) | n=31/0 · — · 100.0% · 100.0% |
| medium (5-15K chars) | n=37/0 · — · 100.0% · 100.0% |
| n/a | n=20/0 · — · 0.0% · 0.0% |
| short (<5K chars) | n=16/0 · — · 100.0% · 100.0% |
| very long (>30K chars) | n=16/0 · — · 100.0% · 100.0% |

## Validator flags and extractor notes (all docs)

- **rules_v2** flags: {'empty_facts': 20}
- **rules_v2** notes: {'no_exact_heading': 35, 'span_starts_very_early': 28, 'toc_contamination': 23, 'merged_2_sections': 22, 'no_span_found': 20, 'no_citations_in_facts': 19, 'fallback_pre_argument': 15, 'low_alpha_ratio': 15, 'merged_3_sections': 11, 'merged_4_sections': 9, 'guardrail_truncated': 6, 'span_too_short': 6, 'merged_5_sections': 4, 'merged_6_sections': 4, 'merge_limit_warning': 3}

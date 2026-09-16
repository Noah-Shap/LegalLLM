# Extraction eval — run labeled-v3_20260916-001818_90b33c

- gold: `evals\gold\gold_v1.jsonl` · subset **labeled** · docs 120 (gold-labeled 120) · 2026-09-16T00:18:18.559244+00:00
- **rules_v2**: version `rules_v2` · backend `local` · model `None` · prompt `None`
- **llm-v1**: version `llm-v1` · backend `claude-cli` · model `claude-sonnet-5` · prompt `2e9b97f8dcd48884`
- **llm-v2**: version `llm-v2` · backend `claude-cli` · model `claude-sonnet-5` · prompt `aa4020336ae219ec`
- **llm-v3**: version `llm-v3` · backend `claude-cli` · model `claude-sonnet-5` · prompt `aa4020336ae219ec`

## Gold-referenced metrics (labeled docs only)

| method | n gold | IoU mean | IoU median | IoU≥0.9 | IoU≥0.5 | span found | validator pass | empty facts | cite fidelity | docs w/ unsupported cites | recovered (failure stratum) | auto↔human agree | cost/doc | latency/doc |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| rules_v2 | 120 | 0.572 | 0.804 | 46.7% | 57.5% | 83.3% | 83.3% | 16.7% | 1.000 | 0/63 | 0.0% (n=20) | 92.0% (n=100) | — | 0.009s |
| llm-v1 | 120 | 0.814 | 1.000 | 76.7% | 82.5% | 68.3% | 55.0% | 31.7% | 0.981 | 16/92 | 85.7% (n=20) | 44.0% (n=100) | $0.2758 | 31.632s |
| llm-v2 | 120 | 0.912 | 1.000 | 90.0% | 90.8% | 65.8% | 48.3% | 34.2% | 0.962 | 23/86 | 85.7% (n=20) | 33.0% (n=100) | $0.2742 | 34.366s |
| llm-v3 | 120 | 0.975 | 1.000 | 95.8% | 97.5% | 72.5% | 55.0% | 27.5% | 0.964 | 21/86 | 85.7% (n=20) | 37.0% (n=100) | $0.3314 | 37.439s |

Auto-rating thresholds: IoU ≥ 0.9 → correct, ≥ 0.5 → partially_correct, else incorrect. Span-found / validator / fidelity / cost / latency columns use **all** docs in the subset.

### rules_v2: auto-rating vs human rating (human→auto)

| pair | n |
|---|---:|
| correct->correct | 38 |
| incorrect->incorrect | 41 |
| partially_correct->correct | 5 |
| partially_correct->incorrect | 3 |
| partially_correct->partially_correct | 13 |

### llm-v1: auto-rating vs human rating (human→auto)

| pair | n |
|---|---:|
| correct->correct | 32 |
| correct->incorrect | 5 |
| correct->partially_correct | 1 |
| incorrect->correct | 29 |
| incorrect->incorrect | 9 |
| incorrect->partially_correct | 3 |
| partially_correct->correct | 15 |
| partially_correct->incorrect | 3 |
| partially_correct->partially_correct | 3 |

### llm-v2: auto-rating vs human rating (human→auto)

| pair | n |
|---|---:|
| correct->correct | 32 |
| correct->incorrect | 6 |
| incorrect->correct | 39 |
| incorrect->incorrect | 1 |
| incorrect->partially_correct | 1 |
| partially_correct->correct | 18 |
| partially_correct->incorrect | 3 |

### llm-v3: auto-rating vs human rating (human→auto)

| pair | n |
|---|---:|
| correct->correct | 36 |
| correct->incorrect | 2 |
| incorrect->correct | 40 |
| incorrect->partially_correct | 1 |
| partially_correct->correct | 20 |
| partially_correct->partially_correct | 1 |

## Agreement between methods (all docs, no gold needed)

| pair | n | IoU mean | IoU median | IoU≥0.9 |
|---|---:|---:|---:|---:|
| rules_v2 ↔ llm-v1 | 120 | 0.478 | 0.442 | 36.7% |
| rules_v2 ↔ llm-v2 | 120 | 0.507 | 0.585 | 40.8% |
| rules_v2 ↔ llm-v3 | 120 | 0.556 | 0.744 | 44.2% |
| llm-v1 ↔ llm-v2 | 120 | 0.813 | 1.000 | 76.7% |
| llm-v1 ↔ llm-v3 | 120 | 0.821 | 1.000 | 77.5% |
| llm-v2 ↔ llm-v3 | 120 | 0.933 | 1.000 | 93.3% |

## Stratified by source (n docs/gold · gold-referenced IoU mean · span found · validator pass)

| source | rules_v2 | llm-v1 | llm-v2 | llm-v3 |
|---|---|---|---|---|
| audit_set | n=100/100 · 0.557 · 100.0% · 100.0% | n=100/100 · 0.814 · 72.0% · 56.0% | n=100/100 · 0.901 · 72.0% · 52.0% | n=100/100 · 0.976 · 80.0% · 60.0% |
| no_facts_span | n=20/20 · 0.650 · 0.0% · 0.0% | n=20/20 · 0.816 · 50.0% · 50.0% | n=20/20 · 0.968 · 35.0% · 30.0% | n=20/20 · 0.968 · 35.0% · 30.0% |

## Stratified by confidence (n docs/gold · gold-referenced IoU mean · span found · validator pass)

| confidence | rules_v2 | llm-v1 | llm-v2 | llm-v3 |
|---|---|---|---|---|
| high | n=61/61 · 0.817 · 100.0% · 100.0% | n=61/61 · 0.835 · 88.5% · 68.8% | n=61/61 · 0.875 · 83.6% · 55.7% | n=61/61 · 0.966 · 93.4% · 65.6% |
| low | n=23/23 · 0.039 · 100.0% · 100.0% | n=23/23 · 0.887 · 39.1% · 30.4% | n=23/23 · 0.996 · 47.8% · 43.5% | n=23/23 · 0.996 · 47.8% · 43.5% |
| medium | n=16/16 · 0.307 · 100.0% · 100.0% | n=16/16 · 0.630 · 56.2% · 43.8% | n=16/16 · 0.861 · 62.5% · 50.0% | n=16/16 · 0.986 · 75.0% · 62.5% |
| none | n=20/20 · 0.650 · 0.0% · 0.0% | n=20/20 · 0.816 · 50.0% · 50.0% | n=20/20 · 0.968 · 35.0% · 30.0% | n=20/20 · 0.968 · 35.0% · 30.0% |

## Stratified by len_bin (n docs/gold · gold-referenced IoU mean · span found · validator pass)

| len_bin | rules_v2 | llm-v1 | llm-v2 | llm-v3 |
|---|---|---|---|---|
| long (15-30K chars) | n=31/31 · 0.764 · 100.0% · 100.0% | n=31/31 · 0.760 · 77.4% · 51.6% | n=31/31 · 0.892 · 87.1% · 61.3% | n=31/31 · 0.988 · 96.8% · 71.0% |
| medium (5-15K chars) | n=37/37 · 0.537 · 100.0% · 100.0% | n=37/37 · 0.928 · 64.9% · 56.8% | n=37/37 · 0.959 · 67.6% · 54.0% | n=37/37 · 0.986 · 70.3% · 56.8% |
| n/a | n=20/20 · 0.650 · 0.0% · 0.0% | n=20/20 · 0.816 · 50.0% · 50.0% | n=20/20 · 0.968 · 35.0% · 30.0% | n=20/20 · 0.968 · 35.0% · 30.0% |
| short (<5K chars) | n=16/16 · 0.249 · 100.0% · 100.0% | n=16/16 · 0.697 · 68.8% · 62.5% | n=16/16 · 0.875 · 56.2% · 43.8% | n=16/16 · 0.937 · 62.5% · 50.0% |
| very long (>30K chars) | n=16/16 · 0.508 · 100.0% · 100.0% | n=16/16 · 0.772 · 81.2% · 56.2% | n=16/16 · 0.812 · 68.8% · 37.5% | n=16/16 · 0.970 · 87.5% · 56.2% |

## llm-v1 vs rules_v2 (paired, gold-referenced)

- pairs: 120 · IoU delta mean: 0.242 · wins 65 / ties 38 / losses 17 (±0.01)

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

- pairs: 120 · IoU delta mean: 0.340 · wins 73 / ties 37 / losses 10 (±0.01)

Worst 10 docs for llm-v2:

| IoU | gold_id | source | confidence | notes |
|---:|---|---|---|---|
| 0.000 | g033 | audit_set | high | Facts section comprises STATEMENT OF THE CASE parts A (Statutory and Regulatory  |
| 0.000 | g034 | audit_set | high | Facts section corresponds to STATEMENT OF THE CASE, comprising A. Statutory Back |
| 0.000 | g052 | audit_set | medium | The INTRODUCTION section is a factual narrative (not argument) and was treated a |
| 0.000 | g056 | audit_set | high | STATEMENT OF THE CASE includes both factual background (Part I) and procedural b |
| 0.000 | g067 | audit_set | medium | The brief contains two factual narratives: the numbered 'Statement of Relevant F |
| 0.000 | g078 | audit_set | high | Facts section corresponds to 'II. STATEMENT OF THE CASE' (with subsections A. As |
| 0.000 | g080 | audit_set | high | Facts section is STATEMENT OF THE CASE, comprising subsection A (Facts Alleged)  |
| 0.000 | g092 | audit_set | high | Facts section includes narrative paragraph, numbered 'Factual and Procedural Bac |
| 0.000 | g097 | audit_set | high | Document contains multiple attached filings after the appellant's brief (the cer |
| 0.376 | f019 | no_facts_span | high | Facts section combines the factual portions of the PRELIMINARY STATEMENT with th |

## llm-v3 vs rules_v2 (paired, gold-referenced)

- pairs: 120 · IoU delta mean: 0.402 · wins 77 / ties 40 / losses 3 (±0.01)

Worst 10 docs for llm-v3:

| IoU | gold_id | source | confidence | notes |
|---:|---|---|---|---|
| 0.000 | g052 | audit_set | medium | The INTRODUCTION section is a factual narrative (not argument) and was treated a |
| 0.376 | f019 | no_facts_span | high | Facts section combines the factual portions of the PRELIMINARY STATEMENT with th |
| 0.479 | g029 | audit_set | high | Facts section runs from the STATEMENT OF THE CASE heading through end of that se |
| 0.516 | g034 | audit_set | high | Facts section is the STATEMENT OF THE CASE (A. Statutory Background, B. Factual  |
| 0.782 | g077 | audit_set | high | Facts extracted from subsections B (Factual Background) and C (Procedural Histor |
| 0.914 | g039 | audit_set | medium | Document has explicit 'STATEMENT OF CASE' heading, but much of the text is rende |
| 0.944 | g053 | audit_set | high | Facts section is IV. STATEMENT OF THE CASE, spanning A. Factual Background (with |
| 0.982 | f007 | no_facts_span | high | Facts section (STATEMENT OF THE CASE, I. FACTUAL BACKGROUND through G. The Fees  |
| 0.993 | g067 | audit_set | medium | Brief contains two separate factual sections: a numbered 'Statement of Relevant  |
| 0.994 | g097 | audit_set | high | Facts section is the STATEMENT OF THE CASE, comprising 'I. Nature of the Case an |

## Validator flags and extractor notes (all docs)

- **rules_v2** flags: {'empty_facts': 20}
- **rules_v2** notes: {'no_exact_heading': 35, 'span_starts_very_early': 28, 'toc_contamination': 23, 'merged_2_sections': 22, 'no_span_found': 20, 'no_citations_in_facts': 19, 'fallback_pre_argument': 15, 'low_alpha_ratio': 15, 'merged_3_sections': 11, 'merged_4_sections': 9, 'guardrail_truncated': 6, 'span_too_short': 6, 'merged_5_sections': 4, 'merged_6_sections': 4, 'merge_limit_warning': 3}
- **llm-v1** flags: {'nonverbatim_citation': 41, 'empty_facts': 38, 'unsupported_citation': 31, 'unparseable_date': 2}
- **llm-v1** notes: {'llm_no_facts': 27, 'end_anchor_not_found': 8, 'doc_truncated_to_window': 6, 'start_anchor_not_found': 3, 'has_facts set to false accordingly.': 1, 'Document is truncated.': 1}
- **llm-v2** flags: {'nonverbatim_citation': 152, 'unsupported_citation': 49, 'empty_facts': 41, 'unparseable_date': 1}
- **llm-v2** notes: {'llm_no_facts': 33, 'end_anchor_relaxed': 9, 'end_anchor_not_found': 7, 'doc_truncated_to_window': 6, 'start_anchor_not_found': 1}
- **llm-v3** flags: {'nonverbatim_citation': 150, 'unsupported_citation': 47, 'empty_facts': 33, 'unparseable_date': 1}
- **llm-v3** notes: {'routed:cheap': 112, 'llm_no_facts': 33, 'end_anchor_relaxed': 9, 'routed:strong:anchor_not_found': 8, 'doc_truncated_to_window': 6, 'Statutory addendum and tables excluded.': 1}

# Extraction eval — run labeled-v5_20260916-132745_3eac2d

- gold: `evals\gold\gold_v1.jsonl` · subset **labeled** · docs 120 (gold-labeled 120) · 2026-09-16T13:27:45.865892+00:00
- **rules_v2**: version `rules_v2` · backend `local` · model `None` · prompt `None`
- **llm-v2**: version `llm-v2` · backend `claude-cli` · model `claude-sonnet-5` · prompt `aa4020336ae219ec`
- **llm-v3**: version `llm-v3` · backend `claude-cli` · model `claude-sonnet-5` · prompt `aa4020336ae219ec`
- **llm-v4**: version `llm-v3` · backend `claude-cli` · model `claude-sonnet-5` · prompt `59532802dd12b37b`
- **llm-v5**: version `llm-v5` · backend `claude-cli` · model `claude-sonnet-5` · prompt `59532802dd12b37b`

## Gold-referenced metrics (labeled docs only)

| method | n gold | IoU mean | IoU median | IoU≥0.9 | IoU≥0.5 | span found | validator pass | empty facts | cite fidelity | docs w/ unsupported cites | recovered (failure stratum) | auto↔human agree | cost/doc | latency/doc |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| rules_v2 | 120 | 0.572 | 0.804 | 46.7% | 57.5% | 83.3% | 83.3% | 16.7% | 1.000 | 0/63 | 0.0% (n=20) | 92.0% (n=100) | — | 0.009s |
| llm-v2 | 120 | 0.912 | 1.000 | 90.0% | 90.8% | 65.8% | 48.3% | 34.2% | 0.962 | 23/86 | 85.7% (n=20) | 33.0% (n=100) | $0.2742 | 34.366s |
| llm-v3 | 120 | 0.975 | 1.000 | 95.8% | 97.5% | 72.5% | 55.0% | 27.5% | 0.964 | 21/86 | 85.7% (n=20) | 37.0% (n=100) | $0.3314 | 37.439s |
| llm-v4 | 120 | 0.953 | 1.000 | 92.5% | 95.8% | 70.0% | 59.2% | 30.0% | 0.992 | 14/87 | 100.0% (n=20) | 35.0% (n=100) | $0.4024 | 71.531s |
| llm-v5 | 120 | 0.978 | 1.000 | 95.0% | 98.3% | 72.5% | 60.8% | 27.5% | 0.992 | 14/87 | 100.0% (n=20) | 36.0% (n=100) | $0.4315 | 72.582s |

Auto-rating thresholds: IoU ≥ 0.9 → correct, ≥ 0.5 → partially_correct, else incorrect. Span-found / validator / fidelity / cost / latency columns use **all** docs in the subset.

### rules_v2: auto-rating vs human rating (human→auto)

| pair | n |
|---|---:|
| correct->correct | 38 |
| incorrect->incorrect | 41 |
| partially_correct->correct | 5 |
| partially_correct->incorrect | 3 |
| partially_correct->partially_correct | 13 |

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

### llm-v4: auto-rating vs human rating (human→auto)

| pair | n |
|---|---:|
| correct->correct | 34 |
| correct->incorrect | 3 |
| correct->partially_correct | 1 |
| incorrect->correct | 39 |
| incorrect->partially_correct | 2 |
| partially_correct->correct | 18 |
| partially_correct->incorrect | 2 |
| partially_correct->partially_correct | 1 |

### llm-v5: auto-rating vs human rating (human→auto)

| pair | n |
|---|---:|
| correct->correct | 35 |
| correct->incorrect | 2 |
| correct->partially_correct | 1 |
| incorrect->correct | 39 |
| incorrect->partially_correct | 2 |
| partially_correct->correct | 20 |
| partially_correct->partially_correct | 1 |

## Agreement between methods (all docs, no gold needed)

| pair | n | IoU mean | IoU median | IoU≥0.9 |
|---|---:|---:|---:|---:|
| rules_v2 ↔ llm-v2 | 120 | 0.507 | 0.585 | 40.8% |
| rules_v2 ↔ llm-v3 | 120 | 0.556 | 0.744 | 44.2% |
| rules_v2 ↔ llm-v4 | 120 | 0.532 | 0.652 | 42.5% |
| rules_v2 ↔ llm-v5 | 120 | 0.554 | 0.744 | 43.3% |
| llm-v2 ↔ llm-v3 | 120 | 0.933 | 1.000 | 93.3% |
| llm-v2 ↔ llm-v4 | 120 | 0.908 | 1.000 | 90.0% |
| llm-v2 ↔ llm-v5 | 120 | 0.917 | 1.000 | 90.8% |
| llm-v3 ↔ llm-v4 | 120 | 0.950 | 1.000 | 94.2% |
| llm-v3 ↔ llm-v5 | 120 | 0.975 | 1.000 | 96.7% |
| llm-v4 ↔ llm-v5 | 120 | 0.975 | 1.000 | 97.5% |

## Stratified by source (n docs/gold · gold-referenced IoU mean · span found · validator pass)

| source | rules_v2 | llm-v2 | llm-v3 | llm-v4 | llm-v5 |
|---|---|---|---|---|---|
| audit_set | n=100/100 · 0.557 · 100.0% · 100.0% | n=100/100 · 0.901 · 72.0% · 52.0% | n=100/100 · 0.976 · 80.0% · 60.0% | n=100/100 · 0.944 · 77.0% · 64.0% | n=100/100 · 0.974 · 80.0% · 66.0% |
| no_facts_span | n=20/20 · 0.650 · 0.0% · 0.0% | n=20/20 · 0.968 · 35.0% · 30.0% | n=20/20 · 0.968 · 35.0% · 30.0% | n=20/20 · 1.000 · 35.0% · 35.0% | n=20/20 · 1.000 · 35.0% · 35.0% |

## Stratified by confidence (n docs/gold · gold-referenced IoU mean · span found · validator pass)

| confidence | rules_v2 | llm-v2 | llm-v3 | llm-v4 | llm-v5 |
|---|---|---|---|---|---|
| high | n=61/61 · 0.817 · 100.0% · 100.0% | n=61/61 · 0.875 · 83.6% · 55.7% | n=61/61 · 0.966 · 93.4% · 65.6% | n=61/61 · 0.913 · 88.5% · 73.8% | n=61/61 · 0.962 · 93.4% · 77.0% |
| low | n=23/23 · 0.039 · 100.0% · 100.0% | n=23/23 · 0.996 · 47.8% · 43.5% | n=23/23 · 0.996 · 47.8% · 43.5% | n=23/23 · 0.998 · 47.8% · 43.5% | n=23/23 · 0.998 · 47.8% · 43.5% |
| medium | n=16/16 · 0.307 · 100.0% · 100.0% | n=16/16 · 0.861 · 62.5% · 50.0% | n=16/16 · 0.986 · 75.0% · 62.5% | n=16/16 · 0.986 · 75.0% · 56.2% | n=16/16 · 0.986 · 75.0% · 56.2% |
| none | n=20/20 · 0.650 · 0.0% · 0.0% | n=20/20 · 0.968 · 35.0% · 30.0% | n=20/20 · 0.968 · 35.0% · 30.0% | n=20/20 · 1.000 · 35.0% · 35.0% | n=20/20 · 1.000 · 35.0% · 35.0% |

## Stratified by len_bin (n docs/gold · gold-referenced IoU mean · span found · validator pass)

| len_bin | rules_v2 | llm-v2 | llm-v3 | llm-v4 | llm-v5 |
|---|---|---|---|---|---|
| long (15-30K chars) | n=31/31 · 0.764 · 100.0% · 100.0% | n=31/31 · 0.892 · 87.1% · 61.3% | n=31/31 · 0.988 · 96.8% · 71.0% | n=31/31 · 0.960 · 93.5% · 74.2% | n=31/31 · 0.993 · 96.8% · 74.2% |
| medium (5-15K chars) | n=37/37 · 0.537 · 100.0% · 100.0% | n=37/37 · 0.959 · 67.6% · 54.0% | n=37/37 · 0.986 · 70.3% · 56.8% | n=37/37 · 0.957 · 67.6% · 59.5% | n=37/37 · 0.984 · 70.3% · 62.2% |
| n/a | n=20/20 · 0.650 · 0.0% · 0.0% | n=20/20 · 0.968 · 35.0% · 30.0% | n=20/20 · 0.968 · 35.0% · 30.0% | n=20/20 · 1.000 · 35.0% · 35.0% | n=20/20 · 1.000 · 35.0% · 35.0% |
| short (<5K chars) | n=16/16 · 0.249 · 100.0% · 100.0% | n=16/16 · 0.875 · 56.2% · 43.8% | n=16/16 · 0.937 · 62.5% · 50.0% | n=16/16 · 0.929 · 62.5% · 50.0% | n=16/16 · 0.929 · 62.5% · 50.0% |
| very long (>30K chars) | n=16/16 · 0.508 · 100.0% · 100.0% | n=16/16 · 0.812 · 68.8% · 37.5% | n=16/16 · 0.970 · 87.5% · 56.2% | n=16/16 · 0.897 · 81.2% · 68.8% | n=16/16 · 0.960 · 87.5% · 75.0% |

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

## llm-v4 vs rules_v2 (paired, gold-referenced)

- pairs: 120 · IoU delta mean: 0.381 · wins 76 / ties 37 / losses 7 (±0.01)

Worst 10 docs for llm-v4:

| IoU | gold_id | source | confidence | notes |
|---:|---|---|---|---|
| 0.000 | g037 | audit_set | high | Document also contains a STATEMENT OF JURISDICTION and STATEMENT OF ISSUES secti |
| 0.000 | g050 | audit_set | high | Facts section is titled STATEMENT OF THE CASE with sub-headings I (Factual) and  |
| 0.000 | g067 | audit_set | medium | The brief contains two distinct factual sections: an earlier numbered 'Statement |
| 0.000 | g078 | audit_set | medium | Facts section extracted from 'II. STATEMENT OF THE CASE' (subsections A-C, inclu |
| 0.479 | g029 | audit_set | high | Facts section headed 'STATEMENT OF THE CASE' runs from that heading to 'STANDARD |
| 0.516 | g034 | audit_set | medium | Document is heavily OCR-garbled throughout (letter substitutions in party/case n |
| 0.782 | g077 | audit_set | high | Section A of the Statement of the Case ("The Fair Housing Act") is a recitation  |
| 0.841 | g066 | audit_set | high | Facts section combines STATEMENT OF THE CASE and STATEMENT OF FACTS headings; ST |
| 0.866 | g052 | audit_set | medium | The brief also contains a factual narrative under an INTRODUCTION heading (pp. 5 |
| 0.950 | g099 | audit_set | medium | Document is a pro se appellate brief; the factual narrative appears under an unl |

## llm-v5 vs rules_v2 (paired, gold-referenced)

- pairs: 120 · IoU delta mean: 0.406 · wins 79 / ties 37 / losses 4 (±0.01)

Worst 10 docs for llm-v5:

| IoU | gold_id | source | confidence | notes |
|---:|---|---|---|---|
| 0.000 | g067 | audit_set | medium | The brief contains two distinct factual sections: an earlier numbered 'Statement |
| 0.479 | g029 | audit_set | high | Facts section headed 'STATEMENT OF THE CASE' runs from that heading to 'STANDARD |
| 0.516 | g034 | audit_set | medium | Document is heavily OCR-garbled throughout (letter substitutions in party/case n |
| 0.782 | g077 | audit_set | high | Section A of the Statement of the Case ("The Fair Housing Act") is a recitation  |
| 0.841 | g066 | audit_set | high | Facts section combines STATEMENT OF THE CASE and STATEMENT OF FACTS headings; ST |
| 0.866 | g052 | audit_set | medium | The brief also contains a factual narrative under an INTRODUCTION heading (pp. 5 |
| 0.950 | g099 | audit_set | medium | Document is a pro se appellate brief; the factual narrative appears under an unl |
| 0.994 | g055 | audit_set | high | Facts section is the STATEMENT OF FACTS with subsections I-III (pp. 7-21), endin |
| 0.994 | g074 | audit_set | high | Facts section comprises the 'Statement of the Case' with subsections 'I. Factual |
| 0.995 | g097 | audit_set | high | Facts section comprises STATEMENT OF THE CASE, Parts I (Nature of the Case and R |

## Validator flags and extractor notes (all docs)

- **rules_v2** flags: {'empty_facts': 20}
- **rules_v2** notes: {'no_exact_heading': 35, 'span_starts_very_early': 28, 'toc_contamination': 23, 'merged_2_sections': 22, 'no_span_found': 20, 'no_citations_in_facts': 19, 'fallback_pre_argument': 15, 'low_alpha_ratio': 15, 'merged_3_sections': 11, 'merged_4_sections': 9, 'guardrail_truncated': 6, 'span_too_short': 6, 'merged_5_sections': 4, 'merged_6_sections': 4, 'merge_limit_warning': 3}
- **llm-v2** flags: {'nonverbatim_citation': 152, 'unsupported_citation': 49, 'empty_facts': 41, 'unparseable_date': 1}
- **llm-v2** notes: {'llm_no_facts': 33, 'end_anchor_relaxed': 9, 'end_anchor_not_found': 7, 'doc_truncated_to_window': 6, 'start_anchor_not_found': 1}
- **llm-v3** flags: {'nonverbatim_citation': 150, 'unsupported_citation': 47, 'empty_facts': 33, 'unparseable_date': 1}
- **llm-v3** notes: {'routed:cheap': 112, 'llm_no_facts': 33, 'end_anchor_relaxed': 9, 'routed:strong:anchor_not_found': 8, 'doc_truncated_to_window': 6, 'Statutory addendum and tables excluded.': 1}
- **llm-v4** flags: {'empty_facts': 36, 'unsupported_citation': 23, 'nonverbatim_citation': 17}
- **llm-v4** notes: {'llm_no_facts': 33, 'doc_truncated_to_window': 6, 'end_anchor_not_found': 3, 'end_anchor_relaxed': 1, 'start_anchor_relaxed': 1}
- **llm-v5** flags: {'empty_facts': 33, 'unsupported_citation': 23, 'nonverbatim_citation': 17}
- **llm-v5** notes: {'routed:cheap': 117, 'llm_no_facts': 33, 'doc_truncated_to_window': 6, 'routed:strong:anchor_not_found': 3, 'end_anchor_relaxed': 1, 'The end anchor spans two adjacent lines.': 1}

# Results — facts extraction: rules_v2 vs LLM

Run `labeled-v5_20260916-132745_3eac2d` · gold `evals\gold\gold_v1.jsonl` · subset **labeled** · 120 documents (120 gold-labeled: 35 human, 85 judge-accepted) · 2026-09-16T13:27:45Z

> **Gold source.** 120/120 documents are labeled: 35 by Noah (human review of the judge's hardest cases plus a sample per accept policy) and 85 accepted from the Opus 5 judge under explicit policies. Judge↔human agreement on the 35-doc overlap: rating κ 0.885, has-facts κ 1.00, span IoU 0.935. Human-only headline (n=35, run labeled-human_20260915-223814_a0177c): llm-v2 IoU 0.869 (≥0.9 on 85.7%) vs rules_v2 0.647 (34.3%). See evals/error_taxonomy.md §F.1. **Lineage:** llm-v3 = llm-v2 routed to Opus 5 on anchor failure; llm-v4 = prompt v3 (record citations as printed + page list, taxonomy §I); llm-v5 = llm-v4 with the same route.

## Methods

| method | extractor version | backend | model | prompt | docs | errors |
|---|---|---|---|---|---:|---:|
| rules_v2 | `rules_v2` | local | — | — | 120 | 0 |
| llm-v2 | `llm-v2` | claude-cli | claude-sonnet-5 | aa4020336ae219ec | 120 | 0 |
| llm-v3 | `llm-v3` | claude-cli | claude-sonnet-5 | aa4020336ae219ec | 120 | 0 |
| llm-v4 | `llm-v3` | claude-cli | claude-sonnet-5 | 59532802dd12b37b | 120 | 0 |
| llm-v5 | `llm-v5` | claude-cli | claude-sonnet-5 | 59532802dd12b37b | 120 | 0 |

## Headline table

| metric | rules_v2 | llm-v2 | llm-v3 | llm-v4 | llm-v5 |
|---|---:|---:|---:|---:|---:|
| IoU vs gold (mean) | 0.572 | 0.912 | 0.975 | 0.953 | 0.978 |
| IoU ≥ 0.9 (share of labeled docs) | 46.7% | 90.0% | 95.8% | 92.5% | 95.0% |
| span found | 83.3% | 65.8% | 72.5% | 70.0% | 72.5% |
| validator pass | 83.3% | 48.3% | 55.0% | 59.2% | 60.8% |
| citation fidelity, verbatim (mean) | 1.000 | 0.962 | 0.964 | 0.992 | 0.992 |
| citation support, verbatim + components (mean) | 1.000 | 0.985 | 0.986 | 0.995 | 0.995 |
| cites emitted / non-verbatim / unsupported | 1038 / 0 / 0 | 3978 / 152 / 49 | 3909 / 150 / 47 | 4369 / 17 / 23 | 4335 / 17 / 23 |
| docs with unsupported cites | 0/63 | 23/86 | 21/86 | 14/87 | 14/87 |
| recovered span, failure stratum | 0.0% (n=20) | 85.7% (n=20) | 85.7% (n=20) | 100.0% (n=20) | 100.0% (n=20) |
| IoU auto-rating ↔ label rating (label rates the rules span; rules_v2 row only) | 92.0% (n=100) | n/a | n/a | n/a | n/a |
| cost / doc | — | $0.274 | $0.331 | $0.402 | $0.431 |
| latency / doc (mean) | 0.01 s | 34.37 s | 37.44 s | 71.53 s | 72.58 s |

## Agreement between methods (span IoU, all docs)

| pair | n | IoU mean | IoU median | IoU ≥ 0.9 |
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

## By source (audit set vs rules failures)

| source | rules_v2: span found / validator pass / IoU vs gold (n) | llm-v2: span found / validator pass / IoU vs gold (n) | llm-v3: span found / validator pass / IoU vs gold (n) | llm-v4: span found / validator pass / IoU vs gold (n) | llm-v5: span found / validator pass / IoU vs gold (n) |
|---|---|---|---|---|---|
| audit_set | 100.0% / 100.0% / 0.557 (n=100) | 72.0% / 52.0% / 0.901 (n=100) | 80.0% / 60.0% / 0.976 (n=100) | 77.0% / 64.0% / 0.944 (n=100) | 80.0% / 66.0% / 0.974 (n=100) |
| no_facts_span | 0.0% / 0.0% / 0.650 (n=20) | 35.0% / 30.0% / 0.968 (n=20) | 35.0% / 30.0% / 0.968 (n=20) | 35.0% / 35.0% / 1.000 (n=20) | 35.0% / 35.0% / 1.000 (n=20) |

## Field coverage (LLM-only fields; the rules path emits none)

| field | rules_v2 | llm-v2 | llm-v3 | llm-v4 | llm-v5 |
|---|---:|---:|---:|---:|---:|
| parties non-empty | 0.0% | 99.2% | 99.2% | 99.2% | 99.2% |
| procedural posture present | 0.0% | 96.7% | 96.7% | 97.5% | 97.5% |
| key events / doc (mean) | 0.000 | 7.117 | 7.158 | 6.900 | 6.883 |
| record cites / doc (mean) | 0.000 | 31.583 | 30.950 | 34.858 | 34.575 |
| case cites / doc (mean) | 8.650 | 1.567 | 1.625 | 1.550 | 1.550 |

## llm-v2 vs rules_v2 on labeled docs (paired IoU)

- pairs 120 · mean IoU delta 0.340 · wins 73 / ties 37 / losses 10

## llm-v3 vs rules_v2 on labeled docs (paired IoU)

- pairs 120 · mean IoU delta 0.402 · wins 77 / ties 40 / losses 3

## llm-v4 vs rules_v2 on labeled docs (paired IoU)

- pairs 120 · mean IoU delta 0.381 · wins 76 / ties 37 / losses 7

## llm-v5 vs rules_v2 on labeled docs (paired IoU)

- pairs 120 · mean IoU delta 0.406 · wins 79 / ties 37 / losses 4

## Downstream: citation resolution and BM25 retrieval on each method's span

Spans → case citations → resolver cache (15697 entries, no network) and → masked query → BM25 fitted on the build's train split minus the gold docs; targets fixed per doc (the gold span's resolved citations). 120 gold docs, 31 retrieval queries. Build baseline on its own test split: Recall@10 0.104 (n=131).

| metric | rules_v2 | llm-v2 | llm-v3 | llm-v4 | llm-v5 | gold |
|---|---:|---:|---:|---:|---:|---:|
| docs with ≥ 1 resolved citation | 42.5% | 24.2% | 26.7% | 25.0% | 26.7% | 25.8% |
| resolved-target precision / recall vs gold span | 15.1% / 90.5% | 95.9% / 67.6% | 96.5% / 79.0% | 96.4% / 77.1% | 96.5% / 79.0% | 100.0% / 100.0% |
| spurious targets on no-facts docs | 11/33 docs | 0/33 docs | 0/33 docs | 0/33 docs | 0/33 docs | 0/33 docs |
| BM25 Recall@10 (n=31) | 0.126 | 0.120 | 0.145 | 0.145 | 0.145 | 0.143 |
| BM25 MRR@10 | 0.130 | 0.064 | 0.139 | 0.139 | 0.139 | 0.134 |
| BM25 Recall@10, queries with a span | 0.135 (n=29) | 0.133 (n=28) | 0.145 (n=31) | 0.155 (n=29) | 0.145 (n=31) | 0.143 (n=31) |

Full downstream report: `evals/runs/labeled-v5_20260916-132745_3eac2d/downstream.md`.

## Validator flags and extractor notes

- **rules_v2** flags: `{'empty_facts': 20}`
- **rules_v2** notes (top): `{'no_exact_heading': 35, 'span_starts_very_early': 28, 'toc_contamination': 23, 'merged_2_sections': 22, 'no_span_found': 20, 'no_citations_in_facts': 19, 'fallback_pre_argument': 15, 'low_alpha_ratio': 15, 'merged_3_sections': 11, 'merged_4_sections': 9, 'guardrail_truncated': 6, 'span_too_short': 6, 'merged_5_sections': 4, 'merged_6_sections': 4, 'merge_limit_warning': 3}`
- **llm-v2** flags: `{'nonverbatim_citation': 152, 'unsupported_citation': 49, 'empty_facts': 41, 'unparseable_date': 1}`
- **llm-v2** notes (top): `{'llm_no_facts': 33, 'end_anchor_relaxed': 9, 'end_anchor_not_found': 7, 'doc_truncated_to_window': 6, 'start_anchor_not_found': 1}`
- **llm-v3** flags: `{'nonverbatim_citation': 150, 'unsupported_citation': 47, 'empty_facts': 33, 'unparseable_date': 1}`
- **llm-v3** notes (top): `{'routed:cheap': 112, 'llm_no_facts': 33, 'end_anchor_relaxed': 9, 'routed:strong:anchor_not_found': 8, 'doc_truncated_to_window': 6, 'Statutory addendum and tables excluded.': 1}`
- **llm-v4** flags: `{'empty_facts': 36, 'unsupported_citation': 23, 'nonverbatim_citation': 17}`
- **llm-v4** notes (top): `{'llm_no_facts': 33, 'doc_truncated_to_window': 6, 'end_anchor_not_found': 3, 'end_anchor_relaxed': 1, 'start_anchor_relaxed': 1}`
- **llm-v5** flags: `{'empty_facts': 33, 'unsupported_citation': 23, 'nonverbatim_citation': 17}`
- **llm-v5** notes (top): `{'routed:cheap': 117, 'llm_no_facts': 33, 'doc_truncated_to_window': 6, 'routed:strong:anchor_not_found': 3, 'end_anchor_relaxed': 1, 'The end anchor spans two adjacent lines.': 1}`

## How to read this

- *IoU vs gold* compares each method's span with the gold span, on labeled documents only. Gold labels are either human (Noah) or judge-accepted (Opus 5 verdicts accepted under an explicit policy, `labeler=judge:…`); `legallm-xeval --labeler human` restricts to the human labels.
- *Agreement* is IoU between the two methods' spans on every document; high agreement with low gold IoU means both are wrong the same way.
- *Citation fidelity* is the share of emitted case/record citations that occur verbatim in the source (whitespace- and dash-insensitive). *Citation support* also accepts cites the source prints as list/range shorthand (`App.1494, 1503` → `App.1503`) when every number occurs near the same prefix; a wrong pincite or an expanded range stays unsupported. The rules path emits only regex-found cites, so both are 1.0 by construction.
- *Recovered span* is the share of `no_facts_span` failure documents with a human-located facts section where the method's span reaches IoU ≥ 0.5.
- Cost for `claude-cli` runs is the CLI's estimate at API list prices; those runs are billed to the subscription, not per token.

Full report: `C:/Users/noahm/CodingProjects/LegalLLM/evals/runs/labeled-v5_20260916-132745_3eac2d/report.md`. Regenerate: `legallm-xeval --render C:/Users/noahm/CodingProjects/LegalLLM/evals/runs/labeled-v5_20260916-132745_3eac2d`.

# Results — facts extraction: rules_v2 vs LLM

Run `llm-v1-all_20260915-021057_0c9ab4` · gold `evals\gold\gold_v1.jsonl` · subset **all** · 120 documents (0 human-labeled) · 2026-09-15T02:10:57Z

> **Labels pending.** No gold labels yet, so IoU-vs-gold, auto-rating agreement and the recovered-span rate are not available. Everything below is either operational (span found, validator pass, citation fidelity, cost, latency) or **agreement between methods**, which measures consistency, not correctness.

## Methods

| method | extractor version | backend | model | prompt | docs | errors |
|---|---|---|---|---|---:|---:|
| rules_v2 | `rules_v2` | local | — | — | 120 | 0 |
| llm-v1 | `llm-v1` | claude-cli | claude-sonnet-5 | 2e9b97f8dcd48884 | 120 | 0 |

## Headline table

| metric | rules_v2 | llm-v1 |
|---|---:|---:|
| IoU vs gold (mean) | — | — |
| IoU ≥ 0.9 (share of labeled docs) | — | — |
| span found | 83.3% | 68.3% |
| validator pass | 83.3% | 48.3% |
| citation fidelity (mean) | 1.000 | 0.981 |
| docs with unsupported cites | 0/63 | 27/92 |
| recovered span, failure stratum | — (n=0) | — (n=0) |
| auto↔human rating agreement | — (n=0) | — (n=0) |
| cost / doc | — | $0.276 |
| latency / doc (mean) | 0.01 s | 31.63 s |

## Agreement between methods (span IoU, all docs)

| pair | n | IoU mean | IoU median | IoU ≥ 0.9 |
|---|---:|---:|---:|---:|
| rules_v2 ↔ llm-v1 | 120 | 0.478 | 0.442 | 36.7% |

## By source (audit set vs rules failures)

| source | rules_v2: span found / validator pass / IoU vs gold (n) | llm-v1: span found / validator pass / IoU vs gold (n) |
|---|---|---|
| audit_set | 100.0% / 100.0% / — (n=100) | 72.0% / 48.0% / — (n=100) |
| no_facts_span | 0.0% / 0.0% / — (n=20) | 50.0% / 50.0% / — (n=20) |

## Field coverage (LLM-only fields; the rules path emits none)

| field | rules_v2 | llm-v1 |
|---|---:|---:|
| parties non-empty | 0.0% | 99.2% |
| procedural posture present | 0.0% | 98.3% |
| key events / doc (mean) | 0.000 | 7.817 |
| record cites / doc (mean) | 0.000 | 24.700 |
| case cites / doc (mean) | 8.650 | 1.500 |

## Validator flags and extractor notes

- **rules_v2** flags: `{'empty_facts': 20}`
- **rules_v2** notes (top): `{'no_exact_heading': 35, 'span_starts_very_early': 28, 'toc_contamination': 23, 'merged_2_sections': 22, 'no_span_found': 20, 'no_citations_in_facts': 19, 'fallback_pre_argument': 15, 'low_alpha_ratio': 15, 'merged_3_sections': 11, 'merged_4_sections': 9, 'guardrail_truncated': 6, 'span_too_short': 6, 'merged_5_sections': 4, 'merged_6_sections': 4, 'merge_limit_warning': 3}`
- **llm-v1** flags: `{'unsupported_citation': 72, 'empty_facts': 38, 'unparseable_date': 2}`
- **llm-v1** notes (top): `{'llm_no_facts': 27, 'end_anchor_not_found': 8, 'doc_truncated_to_window': 6, 'start_anchor_not_found': 3, 'has_facts set to false accordingly.': 1, 'Document is truncated.': 1}`

## How to read this

- *IoU vs gold* compares each method's span with the human gold span, on labeled documents only.
- *Agreement* is IoU between the two methods' spans on every document; high agreement with low gold IoU means both are wrong the same way.
- *Citation fidelity* is the share of emitted case/record citations that occur verbatim in the source (whitespace- and dash-insensitive). The rules path emits only regex-found cites, so it is 1.0 by construction.
- *Recovered span* is the share of `no_facts_span` failure documents with a human-located facts section where the method's span reaches IoU ≥ 0.5.
- Cost for `claude-cli` runs is the CLI's estimate at API list prices; those runs are billed to the subscription, not per token.

Full report: `evals/runs/llm-v1-all_20260915-021057_0c9ab4/report.md`. Regenerate: `legallm-xeval --render evals/runs/llm-v1-all_20260915-021057_0c9ab4`.

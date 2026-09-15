# Results — facts extraction: rules_v2 vs LLM

Run `labeled-any_20260915-224235_c0ac4e` · gold `evals\gold\gold_v1.jsonl` · subset **labeled** · 120 documents (120 gold-labeled: 35 human, 85 judge-accepted) · 2026-09-15T22:42:35Z

> **Gold source.** 120/120 documents are labeled: 35 by Noah (human review of the judge's hardest cases plus a sample per accept policy) and 85 accepted from the Opus 5 judge under explicit policies. Judge↔human agreement on the 35-doc overlap: rating kappa 0.885, has-facts kappa 1.00, span IoU 0.935. Human-only headline (n=35, run labeled-human_20260915-223814_a0177c): llm-v2 IoU 0.869 (≥0.9 on 85.7%) vs rules_v2 0.647 (34.3%); paired wins 25 / ties 5 / losses 5. See evals/error_taxonomy.md section F.1.

## Methods

| method | extractor version | backend | model | prompt | docs | errors |
|---|---|---|---|---|---:|---:|
| rules_v2 | `rules_v2` | local | — | — | 120 | 0 |
| llm-v1 | `llm-v1` | claude-cli | claude-sonnet-5 | 2e9b97f8dcd48884 | 120 | 0 |
| llm-v2 | `llm-v2` | claude-cli | claude-sonnet-5 | aa4020336ae219ec | 120 | 0 |

## Headline table

| metric | rules_v2 | llm-v1 | llm-v2 |
|---|---:|---:|---:|
| IoU vs gold (mean) | 0.572 | 0.814 | 0.912 |
| IoU ≥ 0.9 (share of labeled docs) | 46.7% | 76.7% | 90.0% |
| span found | 83.3% | 68.3% | 65.8% |
| validator pass | 83.3% | 55.0% | 48.3% |
| citation fidelity, verbatim (mean) | 1.000 | 0.981 | 0.962 |
| citation support, verbatim + components (mean) | 1.000 | 0.992 | 0.985 |
| cites emitted / non-verbatim / unsupported | 1038 / 0 / 0 | 3144 / 41 / 31 | 3978 / 152 / 49 |
| docs with unsupported cites | 0/63 | 16/92 | 23/86 |
| recovered span, failure stratum | 0.0% (n=20) | 85.7% (n=20) | 85.7% (n=20) |
| IoU auto-rating ↔ label rating (label rates the rules span; rules_v2 row only) | 92.0% (n=100) | n/a | n/a |
| cost / doc | — | $0.276 | $0.274 |
| latency / doc (mean) | 0.01 s | 31.63 s | 34.37 s |

## Agreement between methods (span IoU, all docs)

| pair | n | IoU mean | IoU median | IoU ≥ 0.9 |
|---|---:|---:|---:|---:|
| rules_v2 ↔ llm-v1 | 120 | 0.478 | 0.442 | 36.7% |
| rules_v2 ↔ llm-v2 | 120 | 0.507 | 0.585 | 40.8% |
| llm-v1 ↔ llm-v2 | 120 | 0.813 | 1.000 | 76.7% |

## By source (audit set vs rules failures)

| source | rules_v2: span found / validator pass / IoU vs gold (n) | llm-v1: span found / validator pass / IoU vs gold (n) | llm-v2: span found / validator pass / IoU vs gold (n) |
|---|---|---|---|
| audit_set | 100.0% / 100.0% / 0.557 (n=100) | 72.0% / 56.0% / 0.814 (n=100) | 72.0% / 52.0% / 0.901 (n=100) |
| no_facts_span | 0.0% / 0.0% / 0.650 (n=20) | 50.0% / 50.0% / 0.816 (n=20) | 35.0% / 30.0% / 0.968 (n=20) |

## Field coverage (LLM-only fields; the rules path emits none)

| field | rules_v2 | llm-v1 | llm-v2 |
|---|---:|---:|---:|
| parties non-empty | 0.0% | 99.2% | 99.2% |
| procedural posture present | 0.0% | 98.3% | 96.7% |
| key events / doc (mean) | 0.000 | 7.817 | 7.117 |
| record cites / doc (mean) | 0.000 | 24.700 | 31.583 |
| case cites / doc (mean) | 8.650 | 1.500 | 1.567 |

## llm-v1 vs rules_v2 on labeled docs (paired IoU)

- pairs 120 · mean IoU delta 0.242 · wins 65 / ties 38 / losses 17

## llm-v2 vs rules_v2 on labeled docs (paired IoU)

- pairs 120 · mean IoU delta 0.340 · wins 73 / ties 37 / losses 10

## Validator flags and extractor notes

- **rules_v2** flags: `{'empty_facts': 20}`
- **rules_v2** notes (top): `{'no_exact_heading': 35, 'span_starts_very_early': 28, 'toc_contamination': 23, 'merged_2_sections': 22, 'no_span_found': 20, 'no_citations_in_facts': 19, 'fallback_pre_argument': 15, 'low_alpha_ratio': 15, 'merged_3_sections': 11, 'merged_4_sections': 9, 'guardrail_truncated': 6, 'span_too_short': 6, 'merged_5_sections': 4, 'merged_6_sections': 4, 'merge_limit_warning': 3}`
- **llm-v1** flags: `{'nonverbatim_citation': 41, 'empty_facts': 38, 'unsupported_citation': 31, 'unparseable_date': 2}`
- **llm-v1** notes (top): `{'llm_no_facts': 27, 'end_anchor_not_found': 8, 'doc_truncated_to_window': 6, 'start_anchor_not_found': 3, 'has_facts set to false accordingly.': 1, 'Document is truncated.': 1}`
- **llm-v2** flags: `{'nonverbatim_citation': 152, 'unsupported_citation': 49, 'empty_facts': 41, 'unparseable_date': 1}`
- **llm-v2** notes (top): `{'llm_no_facts': 33, 'end_anchor_relaxed': 9, 'end_anchor_not_found': 7, 'doc_truncated_to_window': 6, 'start_anchor_not_found': 1}`

## How to read this

- *IoU vs gold* compares each method's span with the gold span, on labeled documents only. Gold labels are either human (Noah) or judge-accepted (Opus 5 verdicts accepted under an explicit policy, `labeler=judge:…`); `legallm-xeval --labeler human` restricts to the human labels.
- *Agreement* is IoU between the two methods' spans on every document; high agreement with low gold IoU means both are wrong the same way.
- *Citation fidelity* is the share of emitted case/record citations that occur verbatim in the source (whitespace- and dash-insensitive). *Citation support* also accepts cites the source prints as list/range shorthand (`App.1494, 1503` → `App.1503`) when every number occurs near the same prefix; a wrong pincite or an expanded range stays unsupported. The rules path emits only regex-found cites, so both are 1.0 by construction.
- *Recovered span* is the share of `no_facts_span` failure documents with a human-located facts section where the method's span reaches IoU ≥ 0.5.
- Cost for `claude-cli` runs is the CLI's estimate at API list prices; those runs are billed to the subscription, not per token.

Full report: `evals/runs/labeled-any_20260915-224235_c0ac4e/report.md`. Regenerate: `legallm-xeval --render evals/runs/labeled-any_20260915-224235_c0ac4e`.

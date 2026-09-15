# Results — facts extraction: rules_v2 vs LLM

Run `labeled-judge_20260915-154355_583547` · gold `evals\gold\gold_v1.jsonl` · subset **labeled** · 118 documents (118 human-labeled) · 2026-09-15T15:43:55Z

## Methods

| method | extractor version | backend | model | prompt | docs | errors |
|---|---|---|---|---|---:|---:|
| rules_v2 | `rules_v2` | local | — | — | 118 | 0 |
| llm-v1 | `llm-v1` | claude-cli | claude-sonnet-5 | 2e9b97f8dcd48884 | 118 | 0 |
| llm-v2 | `llm-v2` | claude-cli | claude-sonnet-5 | aa4020336ae219ec | 118 | 0 |

## Headline table

| metric | rules_v2 | llm-v1 | llm-v2 |
|---|---:|---:|---:|
| IoU vs gold (mean) | 0.565 | 0.823 | 0.928 |
| IoU ≥ 0.9 (share of labeled docs) | 45.8% | 78.0% | 91.5% |
| span found | 83.0% | 67.8% | 66.1% |
| validator pass | 83.0% | 54.2% | 48.3% |
| citation fidelity, verbatim (mean) | 1.000 | 0.981 | 0.961 |
| citation support, verbatim + components (mean) | 1.000 | 0.991 | 0.985 |
| cites emitted / non-verbatim / unsupported | 993 / 0 / 0 | 3117 / 41 / 31 | 3955 / 152 / 49 |
| docs with unsupported cites | 0/62 | 16/90 | 23/84 |
| recovered span, failure stratum | 0.0% (n=20) | 85.7% (n=20) | 85.7% (n=20) |
| IoU auto-rating ↔ label rating (label rates the rules span; rules_v2 row only) | 92.9% (n=98) | n/a | n/a |
| cost / doc | — | $0.278 | $0.275 |
| latency / doc (mean) | 0.01 s | 31.70 s | 34.08 s |

## Agreement between methods (span IoU, all docs)

| pair | n | IoU mean | IoU median | IoU ≥ 0.9 |
|---|---:|---:|---:|---:|
| rules_v2 ↔ llm-v1 | 118 | 0.480 | 0.442 | 37.3% |
| rules_v2 ↔ llm-v2 | 118 | 0.515 | 0.621 | 41.5% |
| llm-v1 ↔ llm-v2 | 118 | 0.821 | 1.000 | 78.0% |

## By source (audit set vs rules failures)

| source | rules_v2: span found / validator pass / IoU vs gold (n) | llm-v1: span found / validator pass / IoU vs gold (n) | llm-v2: span found / validator pass / IoU vs gold (n) |
|---|---|---|---|
| audit_set | 100.0% / 100.0% / 0.548 (n=98) | 71.4% / 55.1% / 0.824 (n=98) | 72.5% / 52.0% / 0.919 (n=98) |
| no_facts_span | 0.0% / 0.0% / 0.650 (n=20) | 50.0% / 50.0% / 0.816 (n=20) | 35.0% / 30.0% / 0.968 (n=20) |

## Field coverage (LLM-only fields; the rules path emits none)

| field | rules_v2 | llm-v1 | llm-v2 |
|---|---:|---:|---:|
| parties non-empty | 0.0% | 99.2% | 99.2% |
| procedural posture present | 0.0% | 98.3% | 96.6% |
| key events / doc (mean) | 0.000 | 7.788 | 7.085 |
| record cites / doc (mean) | 0.000 | 24.949 | 31.983 |
| case cites / doc (mean) | 8.415 | 1.466 | 1.534 |

## llm-v1 vs rules_v2 on labeled docs (paired IoU)

- pairs 118 · mean IoU delta 0.258 · wins 65 / ties 38 / losses 15

## llm-v2 vs rules_v2 on labeled docs (paired IoU)

- pairs 118 · mean IoU delta 0.363 · wins 73 / ties 37 / losses 8

## Validator flags and extractor notes

- **rules_v2** flags: `{'empty_facts': 20}`
- **rules_v2** notes (top): `{'no_exact_heading': 35, 'span_starts_very_early': 27, 'toc_contamination': 23, 'merged_2_sections': 22, 'no_span_found': 20, 'no_citations_in_facts': 19, 'fallback_pre_argument': 15, 'low_alpha_ratio': 15, 'merged_3_sections': 11, 'merged_4_sections': 8, 'guardrail_truncated': 6, 'span_too_short': 6, 'merged_5_sections': 4, 'merged_6_sections': 4, 'merge_limit_warning': 3}`
- **llm-v1** flags: `{'nonverbatim_citation': 41, 'empty_facts': 38, 'unsupported_citation': 31, 'unparseable_date': 2}`
- **llm-v1** notes (top): `{'llm_no_facts': 27, 'end_anchor_not_found': 8, 'doc_truncated_to_window': 6, 'start_anchor_not_found': 3, 'has_facts set to false accordingly.': 1, 'Document is truncated.': 1}`
- **llm-v2** flags: `{'nonverbatim_citation': 152, 'unsupported_citation': 49, 'empty_facts': 40, 'unparseable_date': 1}`
- **llm-v2** notes (top): `{'llm_no_facts': 33, 'end_anchor_relaxed': 9, 'doc_truncated_to_window': 6, 'end_anchor_not_found': 6, 'start_anchor_not_found': 1}`

## How to read this

- *IoU vs gold* compares each method's span with the human gold span, on labeled documents only.
- *Agreement* is IoU between the two methods' spans on every document; high agreement with low gold IoU means both are wrong the same way.
- *Citation fidelity* is the share of emitted case/record citations that occur verbatim in the source (whitespace- and dash-insensitive). *Citation support* also accepts cites the source prints as list/range shorthand (`App.1494, 1503` → `App.1503`) when every number occurs near the same prefix; a wrong pincite or an expanded range stays unsupported. The rules path emits only regex-found cites, so both are 1.0 by construction.
- *Recovered span* is the share of `no_facts_span` failure documents with a human-located facts section where the method's span reaches IoU ≥ 0.5.
- Cost for `claude-cli` runs is the CLI's estimate at API list prices; those runs are billed to the subscription, not per token.

Full report: `evals/runs/labeled-judge_20260915-154355_583547/report.md`. Regenerate: `legallm-xeval --render evals/runs/labeled-judge_20260915-154355_583547`.

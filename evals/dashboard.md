# Dashboard — facts extraction service

Generated 2026-09-16T00:51:21+00:00 · request log `logs/requests.jsonl` · eval runs `evals/runs`

## Requests

2 requests from 2026-09-16T00:48:07+00:00 to 2026-09-16T00:48:34+00:00 · errors 0 (0.0%).

| method | n | errors | span found | validator pass | cost total | cost / doc | latency p50 | p95 | escalated | top flags |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| llm-v3 | 1 | 0 | 100.0% | 0.0% | $0.64 | 0.639 | 27.00 s | 27.00 s | 0.0% | {'unsupported_citation': 1} |
| rules_v2 | 1 | 0 | 100.0% | 100.0% | $0.00 | — | 0.68 s | 0.68 s | — | — |

| day | n | errors | cost total | latency p50 |
|---|---:|---:|---:|---:|
| 2026-09-16 | 2 | 0 | $0.64 | 0.68 s |

## Quality over time (eval runs, IoU vs gold)

| run | when | subset | docs (gold) | llm-v1: IoU / ≥0.9 / $/doc | llm-v2: IoU / ≥0.9 / $/doc | llm-v3: IoU / ≥0.9 / $/doc | rules_v2: IoU / ≥0.9 / $/doc |
|---|---|---|---:|---|---|---|---|
| `rules-baseline_20260915-005115_a87a80` | 2026-09-15T00:51:15 | all | 120 (0) | — | — | — | — / — / — |
| `llm-v1-all_20260915-021057_0c9ab4` | 2026-09-15T02:10:57 | all | 120 (0) | — / — / 0.276 | — | — | — / — / — |
| `llm-v2-all_20260915-040449_c762da` | 2026-09-15T04:04:48 | all | 120 (0) | — / — / 0.276 | — / — / 0.274 | — | — / — / — |
| `labeled-human_20260915-223814_a0177c` | 2026-09-15T22:38:14 | labeled | 35 (35) | 0.826 / 74.3% / 0.331 | 0.869 / 85.7% / 0.326 | — | 0.647 / 34.3% / — |
| `labeled-any_20260915-224235_c0ac4e` | 2026-09-15T22:42:35 | labeled | 120 (120) | 0.814 / 76.7% / 0.276 | 0.912 / 90.0% / 0.274 | — | 0.572 / 46.7% / — |
| `labeled-v3_20260916-001818_90b33c` | 2026-09-16T00:18:18 | labeled | 120 (120) | 0.814 / 76.7% / 0.276 | 0.912 / 90.0% / 0.274 | 0.975 / 95.8% / 0.331 | 0.572 / 46.7% / — |

## How to read this

- Requests come from the service log (`legallm-api`, `legallm-ui` in-process mode); no document text is logged.
- Cost is the model's token cost at API list prices; `claude-cli` runs are subscription-billed and report the CLI's estimate.
- The drift check is the CI smoke eval (`legallm-xeval --subset smoke`); a regression there fails the build (C13).

# Iteration log (C9)

One row per prompt / model / routing / chunking change. No change ships without a before/after row
(intent.md §7.6). Numbers come from `evals/runs/<run_id>/summary.json`; "gold n" is the number of
human-labeled documents the IoU column is computed on.

| version | date | change | motivated by (taxonomy class) | run | gold n | IoU vs gold | agreement w/ rules | span found | validator pass | cite fidelity | cost/doc | latency/doc |
|---|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| rules_v2 | 2026-04 | frozen baseline (heading map → merge → validate) | — | `rules-baseline_20260915-005115_a87a80` | 0 | — | — | 83.3% | 83.3% | 1.000 | $0 | 0.01 s |
| llm-v1 | 2026-09-14 | first LLM extractor: Sonnet 5, prompt v1 (`prompt_sha` in run manifest), anchor-based span, effort=medium, head-window ≤ 400k chars, `claude-cli` backend | — (baseline) | _pending: `llm-v1-all_*`_ | 0 | — | _pending_ | _pending_ | _pending_ | _pending_ | _pending_ | _pending_ |

## Notes

- **2026-09-14 · llm-v1 design choices, logged for later ablation:** verbatim start/end anchors instead of offsets
  or full-text return (cheap output, exact offsets); system text folded into the stdin prompt for the CLI
  backend; Claude Code's own system prompt is prepended by the CLI (≈ 60k cached tokens/call), which the API
  backend would not carry.
- Rating thresholds for the auto-rating (IoU ≥ 0.9 / ≥ 0.5) are provisional until the human↔auto confusion
  table in the run report says otherwise.

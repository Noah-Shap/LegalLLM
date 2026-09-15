# Iteration log (C9)

One row per prompt / model / routing / chunking change. No change ships without a before/after row
(intent.md §7.6). Numbers come from `evals/runs/<run_id>/summary.json`; "gold n" is the number of
human-labeled documents the IoU column is computed on.

| version | date | change | motivated by (taxonomy class) | run | gold n | IoU vs gold | agreement w/ rules | span found | validator pass | cite fidelity | cost/doc | latency/doc |
|---|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| rules_v2 | 2026-04 | frozen baseline (heading map → merge → validate) | — | `rules-baseline_20260915-005115_a87a80` | 0 | — | — | 83.3% | 83.3% | 1.000 | $0 | 0.01 s |
| llm-v1 | 2026-09-14 | first LLM extractor: Sonnet 5, prompt v1 (`prompt_sha` in run manifest), anchor-based span, effort=medium, head-window ≤ 400k chars, `claude-cli` backend | — (baseline) | `llm-v1-all_20260915-021057_0c9ab4` | 0 | — | 0.478 mean / 0.442 median (≥0.9 on 36.7%) | 68.3% | 48.3% | 0.981 | $0.276 (CLI est.) | 31.6 s |

## Notes

- **2026-09-14 · llm-v1 first run, read with `evals/error_taxonomy.md` §D:** the LLM's lower span-found rate is
  dominated by 27 audit docs it declares to have *no facts section* (reply/amicus briefs where the rules emitted a
  low-confidence fallback span) and 11 anchor failures. Agreement with the rules is high exactly where the rules
  are confident (median IoU 0.98 on `high`) and low where they are not (0.11 on `low`). Gold labels decide who is
  right; until then no accuracy claim is made. Validator change in this iteration: citation fidelity ignores
  hyphens (PDF extraction drops them unpredictably), which reclassified 92 of 164 flagged cites as verbatim.

- **2026-09-14 · llm-v1 design choices, logged for later ablation:** verbatim start/end anchors instead of offsets
  or full-text return (cheap output, exact offsets); system text folded into the stdin prompt for the CLI
  backend; Claude Code's own system prompt is prepended by the CLI (≈ 60k cached tokens/call), which the API
  backend would not carry.
- Rating thresholds for the auto-rating (IoU ≥ 0.9 / ≥ 0.5) are provisional until the human↔auto confusion
  table in the run report says otherwise.

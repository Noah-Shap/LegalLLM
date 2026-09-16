# GAP — intent.md v0.2 §5 vs STATE.md (commit 9ce39a7, 2026-09-14)

> **Status (2026-09-16):** build-order items 1–14 delivered (see `docs/intent.md` §11 for each); the hosted demo (C14 push + API key) is the one open action. This file is kept as the original gap map.

> Replaces the provisional GAP.md Claude Code wrote while `intent.md` was 0 bytes.
> Columns: **Exists?** cites `STATE.md` §; **Reuse** = existing code to build on; **Effort** S ≤ 1 h · M 1–3 h · L > 3 h; **Wk** = when.

## A · Component gap

| ID | Component | Exists? | Reuse | Effort | Wk |
|---|---|---|---|---|---|
| C1 | Schema (`FactsExtraction`, pydantic, versioned) | **N** — §10 no pydantic | parquet 27-col schema §5 as field source; `extractor_confidence`/`notes` vocab | S | W1 Tue |
| C2 | LLM extractor (structured output, temp 0, chunking, retries, cheap→strong routing) | **N** — §10 | routing pattern = `ocr_decision.should_ocr_document`; retry/backoff = `download_pdf`; budget = `citation_resolver.BudgetTracker` | L | W1 Wed |
| C3 | Baseline adapter (rules_v2 → schema) | **partial** — §3 stage 8 returns span + meta | `facts_extractor.extract_facts_span`, `quality_flags` | S | W1 Tue |
| C4 | Deterministic validators (schema, bounds, citation fidelity, dates) | **partial** — §6 gate notes exist for rules path only | `validate_span` gates; `citation_extractor.extract_citations` for fidelity check | S | W1 Tue |
| C5 | Gold set (120: 100 audit + 20 failures; rubric + boundaries) | **partial** — §5: 100 sampled, **0 rated**; failures unlabeled | `reports/gold_audit_set.md` (stratified, seed 42); `facts_failures_2k.jsonl` no_facts_span rows | L (labeling ≈ 3 h) | W1 Thu |
| C6 | Metrics (IoU, rubric agreement, citation fidelity, recovered-span, downstream resolution %, Recall@10, judge + κ, cost/latency) | **partial** — §2 retrieval metrics + cost report exist; no span metrics | `eval_harness.recall_at_k…`, `generate_cost_report`, `citation_resolver` for resolution % | M | W1 Fri |
| C7 | Extraction eval harness + `legallm-xeval` | **N** — §2 harness is retrieval-only | `stratified_report`, `analyze_errors`, `compare_models`, `format_*`, `build_manifest` (+`prompt_sha`, `model_id`) | M | W1 Fri |
| C8 | Error taxonomy | **partial** — §5 notes: toc_contamination 410, fallback_pre_argument 289, span_starts_very_early 374 … = free v0 | rules notes + failure codes | S | W1 Mon (draft) → W2 |
| C9 | Iteration log | **N** | `CHANGELOG.md` pattern | S | W2 |
| C10 | FastAPI `POST /extract`, `/health`, request log | **N** — §4 CLI only; no single-file path | `extract_text_best` → `normalize_text` → extractor chain (§4) | M | W2 Mon |
| C11 | Minimal UI (side-by-side rules vs LLM + flags) | **N** | — | M | W2 Mon |
| C12 | Observability (per-request JSONL, cost/latency summary, scheduled smoke) | **partial** — §2 `ResolverMetrics`, `generate_cost_report` | extend to LLM tokens/cost | S | W2 |
| C13 | CI green + regression gate | **partial** — §8 workflow exists, **0 runs** (`main` vs `master`); mypy 3 errors would fail it | `.github/workflows/ci.yml`, `pre-commit` | S (unblock) + S (gate) | W1 Mon + W2 Fri |
| C14 | Deployment (HF Spaces / Render) | **N** | — | M | W2 Fri |
| C15 | Security (env secrets, injection guard) | **partial** — §12 secrets clean; no injection guard | `.env.example`, `CL_TOKEN` pattern | S | W2 |
| C16 | README w/ results + `ARCHITECTURE.md` | **N** — §7 README stale (badge placeholders, 4 of 13 modules) | `PROJECT_SUMMARY.md`, spec docs, `reports/m4_*` for the retrieval half | M | W2 Fri |
| C17 | Publish (public repo, LinkedIn, demo cut) | **partial** — repo public as of 2026-09-14 | — | S | W2 Fri |

Totals: N × 9 · partial × 8 · Y × 0 of the 17 target components — but the underlying pipeline, resolver, retrieval baselines, tests, and sampling are all reusable, which is why the effort column sums to roughly the 20-hour timebox.

## B · Assets that exist but were not in the v0.1 target list (now folded into C6)

| Asset | STATE § | Role in Phase 1 |
|---|---|---|
| Citation extractor + CourtListener resolver (cache 15,697, budget tracker) | §2, §3 st. 10–11 | downstream metric: resolved-citation rate, baseline 58.5 % |
| Retrieval baselines + harness (152 test queries; BM25 R@10 0.126) | §2, §7 | downstream metric: Recall@10 with LLM spans vs rule spans — end-to-end eval at near-zero build cost |
| `dataset.py` dedup + stratified split | §2 | keep the same 152-query test split for the downstream comparison |
| Build manifests | §2 | extend, don't replace, for prompt/model provenance |

## C · Hygiene to clear before building (W1 Monday, ≈ 1 h)

| # | Item | Decision ref | Action |
|---|---|---|---|
| H1 | CI has never run | D10 | rename `master`→`main`, set GitHub default, confirm first run |
| H2 | mypy 3 errors in `baselines.py` (223, 274, 340) | — | fix; CI must be green before a gate is meaningful |
| H3 | 3 legacy root scripts | D11 | delete (history keeps them) |
| H4 | `reports/gold_audit_set.md` tracked with 100 full spans + party names, now public | D9 | split: ids + ratings tracked, span text → ignored JSONL; no history rewrite |
| H5 | Stale `README.md` / old `CLAUDE.MD` (upper-case ext.) | — | keep the new `CLAUDE.md`; delete `CLAUDE.MD`; README rewritten in W2 |
| H6 | `intent.md` at root is 0 bytes | — | replace with v0.2 at `docs/intent.md`; delete root copy |
| H7 | Canonical build ambiguity | D12 | README note: April reports used build `38a720b3324a`; Phase 1 uses `46864ffb7283` |
| H8 | `citation_cache.json` (3.5 MB) untracked, not ignored pre-hygiene | — | confirm ignored after `6d01dab`; treat as regenerable |

## D · Session-2 build order (hand to Claude Code after Noah resolves D1–D13)

```
1. H1–H8                                            chore(repo): …           (~1 h)
2. C1 schema + C3 adapter + C4 validators + tests   feat(schema): …          (~2 h)
3. single-doc path: extract_from_file(path|text)    feat(pipeline): …        (~1 h)
4. C2 LLM extractor (cheap tier only first)         feat(llm): …             (~3 h)
5. C5 labeling tool (tiny Streamlit or JSONL CLI)   feat(gold): …            (~1 h)  → Noah labels (~3 h)
6. C7 harness + C6 deterministic metrics            feat(xeval): …           (~2 h)
7. first results table: rules_v2 vs llm-v1          docs(evals): …           (~1 h)
── W1 ends ──
8. C8 taxonomy from llm-v1 failures → llm-v2        feat(llm): v2            (~2 h)
9. judge + κ vs human labels                        feat(xeval): judge       (~1 h)
10. downstream: resolver % + BM25 R@10 on llm spans  feat(xeval): downstream  (~1 h)
11. routing (cheap→strong on validator fail) → v3   feat(llm): v3            (~1 h)
12. C10 API + C11 UI + C12 logging                   feat(api): …             (~2 h)
13. C13 gate + C14 deploy + C15 guard                feat(ci): …              (~2 h)
14. C16 README/ARCHITECTURE + C17 publish            docs: …                  (~1 h)
```
Cut order if time runs short: 11 → 10 → C11 UI (API-only demo is acceptable) → judge (deterministic metrics stand alone).

## E · Answers to STATE.md §14 (proposed — Noah confirms)

| Q | Proposed |
|---|---|
| 1 intent.md empty | use v0.2 from chat; place at `docs/intent.md` |
| 2 canonical build | `46864ffb7283` (on disk) — D12 |
| 3 gold audit set exposure | split text out — D9 |
| 4 legacy scripts | delete — D11 |
| 5 CI branch | rename to `main` — D10 |
| 6 repo name | keep URL; README title *Legal Facts Extraction Service* — D7 |
| 7 account | `Noah-Shap` — D13 |
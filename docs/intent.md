# INTENT — SkillBlock-1 · Legal Facts Extraction as a Deployed LLM App with Evals

> **Status:** v0.2.2 · 2026-09-14 · owner Noah Shap · supersedes v0.1 after reading `STATE.md` (commit 9ce39a7); D1–D13 resolved (see §11 log)
> **Lives at:** `docs/intent.md` in the project repo. Update the version line on every material change; append to §11 Decisions log rather than rewriting history.
> **Read with:** `STATE.md` (what exists) → `GAP.md` (STATE vs this file) → build plan.

---

## 1 · One-line intent

Turn the existing rule-based legal-brief facts-extraction pipeline into a **deployed LLM extraction service with a disciplined evals / error-analysis loop**, where the rule-based extractor is the baseline the LLM must beat on a human-labeled gold set — and ship it publicly with a results table, in ~20 hours across Sep 14–25, 2026.

## 2 · Why this project (not a fresh RAG demo)

- **Reuses real infrastructure.** PDF acquisition, multi-backend extraction with OCR routing, scope filtering, quality flags, and structured failure logging already exist. Phase 1 spends its hours on the *LLM + evals* layer, which is the skills-map's highest-signal item, not on plumbing.
- **Built-in baseline.** A heuristic extractor + its failure JSONL = a ready-made comparison target and a mined source of hard cases. "Replaced a heuristic with an LLM and can show where it wins and where it doesn't" is a stronger portfolio claim than a greenfield chatbot.
- **Honest framing.** The system is an extraction pipeline, not a trained legal model. Never describe it as "LegalLLM" in prose; use *legal facts extraction pipeline / service*.
- **The downstream eval already exists.** Citation resolution + BM25 retrieval are built and measured. Re-running them on LLM spans vs rule spans turns a component eval into an *end-to-end* eval (does better extraction raise resolution rate and Recall@10?) at near-zero build cost.
- **Feeds the long-term aim.** Facts sections are the query documents for the longer-horizon legal citation-prediction eval environment. Better, structured facts = better downstream benchmark.

## 3 · Current state (verified 2026-09-14 from `STATE.md`, commit 9ce39a7 — public at github.com/Noah-Shap/LegalLLM)

| Layer | Exists | Measured |
|---|---|---|
| Sourcing + acquisition | ✅ | CourtListener RECAP search v4; multi-host PDF download w/ retries; 7,502 PDFs local (9.5 GB, ignored) |
| Text extraction + OCR routing | ✅ | pypdf → PyMuPDF → `ocr_decision` → selective Tesseract; 1,125 OCR sidecars (15 %) |
| Scope filter | ✅ rule | metadata-only; 2k build run with `--no_scope_filter` |
| Facts extraction | ✅ `rules_v2` | 3-phase (heading map → classify/merge → validate); `extractor_confidence` + `extractor_notes` |
| Quality flags | ✅ | cite / arg-marker densities, 9 gate notes |
| **Citation extraction + resolver** | ✅ (not in v0.1) | regex + reporter normalisation; CourtListener resolver, cache 15,697 entries, budget tracker |
| **Dataset + splits** | ✅ (not in v0.1) | `dataset.py`: minhash dedup, stratified train/val/test |
| **Retrieval baselines + eval harness** | ✅ (not in v0.1) | popularity / BM25 / dense / hybrid / reranker; Recall/MRR/nDCG@K, stratified, leakage + popularity-dominance checks, error analysis, cost report |
| Build manifests | ✅ | `build_manifest.py`: params, git sha, dirty flag, dep versions |
| Tests | ✅ | 235 pass offline, ~40 s; ruff clean; **mypy 3 errors** (`baselines.py`) |
| CI | ⚠️ | workflow exists, **0 runs ever** (targets `main`; branch is `master`) |
| Gold / labels | ⚠️ | `reports/gold_audit_set.md`: 100 spans sampled by confidence × length bin (seed 42), 3-class rubric, **0/100 rated** |
| **LLM calls / pydantic** | ❌ | none anywhere (spec v1 §9 explicitly deferred LLM-assisted extraction to low-confidence/failed docs) |
| Service / UI / deploy | ❌ | CLI only; no single-file entry point |
| Extraction-quality eval | ❌ | harness measures *retrieval*, not span quality |
| Legacy clutter | ⚠️ | 3 root scripts superseded by `src/legallm/`; README + old `CLAUDE.MD` stale |

**Key numbers (2k build `46864ffb7283`):** 1,599 / 2,000 spans (80 %) · confidence high 978 / med 260 / low 361 · failures: no_facts_span 370, needs_ocr 30 · top notes: toc_contamination 410, fallback_pre_argument 289, span_starts_very_early 374, no_citations_in_facts 242 · rows with ≥1 resolved citation **58.5 %** (spec target ≥ 90 %) · retrieval: BM25 Recall@10 **0.126** / MRR@10 0.180 best; dense 0.037, hybrid 0.086, reranker 0.072 (M4 DoD unmet) · 152 test queries.
**Discrepancy:** M4 reports were computed on an overwritten 2k build (`38a720b3324a`, 1,819 spans); on-disk parquet is the later, smaller build. Pick one as canonical (D12).

## 4 · Timebox & cadence (from Google Calendar, 10 h/wk)

| Week | Blocks | Deliverables |
|---|---|---|
| **W1 · Sep 14–18** | Mon–Fri 10:00–12:00 (5 × 2 h) | Mon: resolve D1–D13, repo unblock (branch→main, mypy, legacy scripts), read 20 low/failed docs → taxonomy draft · Tue: C1 schema + C3 baseline adapter + C4 validators · Wed: C2 LLM extractor + single-doc path, first run on audit set · Thu: label the 100-doc audit set (rubric) + boundary corrections on ≥ 40 · Fri: C7 extraction harness v0, metrics table, error-analysis pass #1 |
| **W2 · Sep 21 + Sep 25** | Mon 10:00–12:30 & 13:30–16:00; Fri same (4 × 2.5 h). Elevate conf Tue–Thu | eval harness (deterministic + LLM-judge, judge validated vs human labels) · 2–3 iterations logged · deploy demo + CI eval on PRs · README w/ results table + failure analysis · GitHub public + LinkedIn post + 60-s demo |
| Overflow | Week 7 buffer (Oct 26–30) | anything unfinished; do **not** steal from W3 agentic build |

## 5 · Target state — components (this is what `GAP.md` diffs against)

| ID | Component | Definition of "exists" |
|---|---|---|
| C1 | **Schema** | Pydantic model(s) for `FactsExtraction`: `facts_span{start,end,text}`, `parties[]`, `procedural_posture`, `key_events[{date?,text}]`, `record_citations[]`, `case_citations[]`, `confidence`, `extractor_version`. Versioned. |
| C2 | **LLM extractor** | `extract_llm(doc_text) -> FactsExtraction` via structured output / tool-call; deterministic settings (temp 0); chunking strategy for long briefs; retries + timeouts; **routing**: cheap model first → escalate on validator failure (mirrors `ocr_decision.py` pattern). |
| C3 | **Baseline adapter** | `rules_v2` wrapped to emit `FactsExtraction` (span + `extractor_confidence` + `extractor_notes` map directly; other fields null). Thin — the extractor already returns structured meta. |
| C4 | **Validators (deterministic)** | schema-valid · span within doc bounds · **citation fidelity**: every emitted citation string occurs verbatim in source text (anti-hallucination) · dates parseable · non-empty facts when scope=merits. |
| C5 | **Gold set** | Seed = existing 100-doc audit set (already stratified by confidence × length bin, seed 42). Label all 100 with the 3-class rubric (correct / partially_correct / incorrect); add corrected `facts_start/facts_end` on ≥ 40 (bias to low/medium confidence). Add **20 `no_facts_span` failures** from `facts_failures_2k.jsonl` with hand-located spans (the "rules found nothing" stratum — not in the audit set). Store ids + labels as versioned JSONL under `evals/gold/`; span text stays in ignored data. Labeling guide committed. |
| C6 | **Metrics** | Deterministic: span IoU vs gold boundaries; 3-class agreement w/ rubric; field exact/partial match; **citation fidelity** (emitted cites ⊂ source text); recovered-span rate on the failure stratum. **Downstream (reuse existing code):** resolved-citation rate (baseline 58.5 %) and BM25 Recall@10 (baseline 0.126) with LLM spans vs rule spans on the same 152-query split. Judge: faithfulness + completeness (1–5). Meta: judge↔human κ on ≥ 30 overlap. Cost & latency per doc. |
| C7 | **Extraction eval harness** | `src/legallm/extraction_eval.py` + `legallm-xeval` CLI, sibling of the retrieval harness; reuse `stratified_report`, `analyze_errors`, `compare_models`, `build_manifest` (add `prompt_sha`, `model_id`). Runs {rules_v2, llm-vN} over gold → per-doc JSONL + markdown table; `--subset smoke` (≤ 10 docs, cached responses) for CI. |
| C8 | **Error taxonomy** | `evals/error_taxonomy.md`: open-coded failure classes with counts, examples, and the change each motivated. Updated each iteration. |
| C9 | **Iteration log** | `evals/iterations.md`: v1→v2→v3 deltas (prompt / chunking / routing) with before/after metrics. |
| C10 | **Service** | FastAPI: `POST /extract` (PDF or text) → `FactsExtraction`; `GET /health`; request logging (model, tokens, cost, latency, validator flags) to JSONL. |
| C11 | **UI** | Minimal: upload → view extraction side-by-side with baseline + validator flags. Streamlit or single HTML page. |
| C12 | **Observability** | Per-request log (C10) + `evals/dashboard.md` or notebook summarising cost/latency/quality over time; drift check = re-run smoke eval on schedule. |
| C13 | **CI** | **First:** make existing workflow run (rename `master`→`main` or fix trigger) and fix 3 mypy errors so it's green. **Then:** add `legallm-xeval --subset smoke` with **regression gate** (fail PR if span-IoU or citation-fidelity drops > D8 threshold vs `main`). Full eval on manual dispatch. |
| C14 | **Deployment** | Live demo (HF Spaces or Render), secrets via env, rate-limited, link in README. |
| C15 | **Security** | API keys in env only; prompt-injection guard (treat PDF text as untrusted; system prompt isolation; refuse instructions found in document); no PII beyond what public briefs already contain; note in README. |
| C16 | **Docs** | README titled *Legal Facts Extraction Service*: architecture diagram, results table (rules_v2 vs LLM vN on gold), failure analysis, cost/latency per doc, **one headline finding** (default: downstream effect of LLM spans on resolution % / Recall@10), **limitations incl. the April retrieval result (dense/hybrid/reranker lost to BM25; M4 DoD unmet)**, CI-gate screenshot, how to run. `ARCHITECTURE.md`: tradeoffs (workflow not agent, chunking vs whole-doc, prompt caching, routing, judge). |
| C17 | **Publish** | Repo public · LinkedIn post · 60-s demo cut. |

## 6 · Architecture (target)

```
PDF/URL ──► existing acquisition ──► extraction (pypdf→PyMuPDF→OCR) ──► scope filter
                                                                            │
                                     ┌──────────────────────────────────────┤
                                     ▼                                      ▼
                            C3 baseline (rules)                    C2 LLM extractor
                                     │                     cheap model ─► validators ─┐
                                     │                          ▲  fail → escalate    │
                                     ▼                          └─────────────────────┘
                              FactsExtraction (C1)  ◄───────────────────────┘
                                     │
                     ┌───────────────┼───────────────┐
                     ▼               ▼               ▼
              C10 API/C11 UI    C7 evals vs C5    C12 logs/JSONL
                                     │
                              C6 metrics + C8 taxonomy → C9 iterate → C13 CI gate
```
This is a **workflow** (predefined sequence with routing + fallbacks), deliberately not an agent harness. That point on the spectrum is a documented choice (see §8, skill 1.3).

## 7 · Eval design principles

1. **EDA before metrics.** First hour of W1 eval work = read 20 failures from `facts_failures.jsonl` and 10 successes; write the taxonomy draft *before* choosing metrics.
2. **Deterministic first, judge second, human as ground truth.** Every judge score must be validated against human labels on an overlap set; report κ. If κ < 0.4 the judge is not used as a headline metric.
3. **Evaluate the evals.** Gold set has a labeling guide + inter-annotator note (even if annotator n=1, document ambiguity rules).
4. **Regression gate in CI**, not just a dashboard.
5. **Cost/latency are metrics**, reported alongside quality — routing exists to move that frontier.
6. **Log every delta.** No prompt change without a before/after row in `evals/iterations.md`.

## 8 · Skills-map coverage matrix (DeepLearning.AI, Aug 2026)

Sources: Andrew Ng, *The AI Engineering Skills Map* (Aug 14, 2026) — https://www.deeplearning.ai/the-batch/the-ai-engineering-skills-map ; Part 1 expansion *Building and Deploying AI Applications* (Aug 21, 2026, on X); Part 2 *Software Engineering Fundamentals* (Aug 28, 2026). Map = expert synthesis of 10k+ postings + interviews; treat as guidance, not audit.

Four top-level skills: **(1) Building & deploying AI applications · (2) Software engineering fundamentals · (3) Using coding agents · (4) Shaping the build**, with a continuous-learning mindset underneath. Ng's single most-important trait: *driving a disciplined evals / error-analysis loop*.

| Skill / sub-skill | How this project exercises it | Evidence artifact | Coverage |
|---|---|---|---|
| **1.1 LLM foundations** — tokenization, context windows, caching, sampling, tool calling, model choice | context budgeting for long briefs (chunk vs whole-doc); prompt caching of system+schema; temp 0; structured output via tool call; cheap→strong routing | `ARCHITECTURE.md` §model choice; C2 code | ● full |
| **1.2 Grounding models with data** — prompt vs retrieval, doc→LLM pipelines, clean/fresh data | the whole PDF→text→LLM pipeline *is* this; decision documented: no retrieval (single-doc extraction), prompt-side grounding; data freshness = re-run path | C2, pipeline, `ARCHITECTURE.md` | ● full |
| **1.3 Building agentic systems** — workflow ↔ harness spectrum, tools, memory, orchestration, guardrails | explicit *workflow* choice with fallbacks + validators as guardrails; **no** agent loop, memory, or multi-agent (deferred to Phase 2, wk 3) | §6 note; `ARCHITECTURE.md` §why-not-an-agent | ◐ partial (by design) |
| **1.4 Evaluation-driven development** — EDA, what to measure, deterministic vs judge vs human, evaluate-the-evals | C5–C9 + §7; κ between judge and human; regression gate | `evals/`, README results table | ● full — **core of project** |
| **1.5 Operating in production** — observability, drift, incident response, regression tests/CI, cost-latency optimisation | C10 request logs, C12 dashboard + scheduled smoke eval, C13 CI gate, C15 prompt-injection guard, routing for cost/latency | logs, CI, README §ops | ◐ partial (drift is nominal in 2 wks) |
| **1.6 ML foundations** — bias/variance, error analysis, engineering data | stratified gold set; error analysis as first-class artifact; baseline vs LLM as a proper experiment; **existing** retrieval baselines + ablation + leakage checks already demonstrate this | C5, C8, `reports/m4_*` | ● full |
| **2 Software engineering fundamentals** (Part 2 sub-skills) | | | |
| 2.1 Full-stack applications | FastAPI + minimal UI | C10, C11 | ◐ minimal UI |
| 2.2 Data management | versioned gold JSONL, gitignored raw data, data/README, parquet schema | C5, repo hygiene | ● |
| 2.3 System architecture | documented tradeoffs, routing, fallback design | `ARCHITECTURE.md` | ● |
| 2.4 Security & reliability | env secrets, retries/timeouts, injection guard, validators | C2, C4, C15 | ● |
| 2.5 Scaling in production | existing resolver budget tracker + cost report pattern extended to LLM calls; batch path noted; cost per 1k docs projected | `ARCHITECTURE.md` §scaling, C12 | ◐ |
| **3 Using coding agents** — context mgmt, plan vs execute, verifiers, specs, protecting prod | Claude Code driven by `CLAUDE.md` + this file; eval harness = the verifier that lets the agent close loops; R-rules protect data; reasoning-first-then-builder workflow | `CLAUDE.md`, `primer.md`, commit history | ● |
| **4 Shaping the build** — product sense, MVP vs careful, ownership | 1-page spec; scope decisions logged (§11); explicit non-goals (§9); MVP in W1, harden in W2 | this file, `evals/iterations.md` | ● |
| Continuous learning | judge-cost / tuned-evaluator literature noted; W7 retro | README §what I'd do next | ◐ |

Legend: ● full · ◐ partial · ○ none. Two deliberate gaps: **agentic systems** (Phase 2) and **drift detection** (nominal). Both must be stated in the README rather than implied as covered.

## 9 · Non-goals (Phase 1)

- No fine-tuning, no self-hosting, no citation-prediction model.
- No agent harness / multi-agent (Phase 2, wk 3 — this repo may host it later).
- No new sourcing runs against CourtListener beyond what the gold set needs.
- No rewrite of the rule-based extractor — it is frozen as the baseline.
- No multi-jurisdiction / non-U.S. briefs.

## 10 · Definition of done (Sep 25)

- [ ] Public repo; README with architecture, **results table (baseline vs LLM v_final on gold: span-F1, field match, citation fidelity, judge score + κ, cost/doc, latency/doc)**, failure analysis, limitations
- [ ] Live demo URL works from a cold browser
- [ ] CI green on `main`; a deliberately-regressed PR fails the gate (screenshot in README)
- [ ] `evals/iterations.md` shows ≥ 2 logged deltas, each motivated by a taxonomy count
- [ ] Judge κ vs human labels reported (headline only if κ ≥ 0.4)
- [ ] README states one headline finding and the retrieval negative result
- [ ] LinkedIn post + 60-s demo published
- [ ] `intent.md` bumped to v1.0 with §11 filled

## 11 · Open decisions (resolve in W1 block 1; log outcome here)

| ID | Decision | Default if undecided | Owner |
|---|---|---|---|
| D1 | LLM provider / models for cheap + strong tiers | Anthropic API (Claude Haiku → Sonnet) via SDK with tool-call structured outputs | Noah |
| D2 | Judge model | strong tier of D1, different prompt; never the same call as the extractor | Noah |
| D3 | Serving | FastAPI + Streamlit front | Noah |
| D4 | Deploy target | HF Spaces (free tier) · fallback Render | Noah |
| D5 | Gold labeling tool | plain JSONL + a tiny Streamlit labeler, or Label Studio if < 1 h to set up | Noah |
| D6 | Gold set composition | the existing 100-doc audit set (all rubric-rated, ≥ 40 boundary-corrected) + 20 hand-located `no_facts_span` failures = 120 | Noah |
| D7 | Repo public name (keep `LegalLLM` or rename) | keep URL, fix README title to *Legal Facts Extraction Service* | Noah |
| D8 | Regression thresholds | span-IoU −2 pts or citation-fidelity −1 pt fails PR | Noah |
| D9 | `reports/gold_audit_set.md` (100 full spans, party names, tracked, now public) | move span text to `data/processed/gold_audit_text.jsonl` (ignored); keep ids + ratings tracked; no history rewrite | Noah |
| D10 | CI never ran (`main` vs `master`) | rename branch to `main` (`git branch -m master main && git push -u origin main`, set default on GitHub) | Noah |
| D11 | Legacy root scripts (`ocr_decision.py`, `pymupdf_ocr_backend_updated.py`, `run_pipeline_v3_*.py`) | delete in a `chore(repo): remove legacy scripts` commit; git history keeps them | Noah |
| D12 | Canonical 2k build | the on-disk `46864ffb7283` (1,599 rows); note in README that April reports used an earlier build | Noah |
| D13 | Owning GitHub account | `Noah-Shap` (matches resume + Cohere materials) | Noah |

Decisions log (append-only):
- 2026-09-14 · v0.1 created; scope = extend existing pipeline (chosen over sports/fintech doc-extraction alternative).
- 2026-09-14 · v0.2.1: cut order fixed (downstream protected, UI cut first); DoD adds judge κ + headline finding.
- 2026-09-14 · v0.2: repo made public; §3 rewritten from `STATE.md`; gold set re-based on existing audit set; downstream (resolution / Recall@10) metric added; D9–D13 opened.
- 2026-09-14 · v0.2.2 (session 2, block 1): Noah resolved **D1 = Claude Sonnet 5** (`claude-sonnet-5`, extractor tier), **D2 = Claude Opus 5** (`claude-opus-5`, judge), **D3–D13 = defaults confirmed** (FastAPI+Streamlit · HF Spaces · JSONL/Streamlit labeler · 120-doc gold · keep URL, retitle README · IoU −2 / fidelity −1 gate · gold text split out · branch → `main` · legacy scripts deleted · canonical build `46864ffb7283` · owner `Noah-Shap`). Open: whether Opus 5 is also the C2 *escalation* tier (D1 named one model); default assumption = yes.
- 2026-09-14 · Build order items 1–3 done (Claude Code): H1–H8 hygiene; C1 `schema.py`, C3 `baseline_adapter.py`, C4 `validators.py` + tests; single-doc path `single_doc.py` / `legallm-extract`.
- 2026-09-14 · Item 4 (C2, cheap tier) done: `llm_extractor.py` + `prompts.py` (prompt v1), registered as `llm-v1`. Design notes: (a) model returns verbatim start/end **anchors**, not offsets — located in `doc_text` with a whitespace/quote-tolerant match; unresolvable anchors ⇒ `facts_span=None` ⇒ validator `empty_facts` (the future escalation trigger). (b) Sonnet 5 rejects `temperature`, so "temp 0" is replaced by fixed `effort=medium` + `prompt_sha`/`model_id` provenance. (c) Chunking = whole doc up to 400k chars, else head window with `doc_truncated_to_window`. (d) Cost/latency/tokens recorded in `FactsExtraction.provenance` (schema 1.1). **Blocked:** first live run failed with HTTP 400 *credit balance too low* — add API credits, then run `legallm-extract data/raw/pdfs/406937652.pdf --method llm-v1`.
- 2026-09-14 · **Item 4b: `claude-cli` backend** (`claude_cli.py`), the Hustle pattern — headless `claude -p --output-format json --json-schema … --tools ''` under the claude.ai login (API key + `CLAUDECODE` stripped from the child env), run from an empty temp dir so the repo's CLAUDE.md is not pulled into the prompt, native `claude.exe` invoked directly (the `.cmd` shim breaks long args). `legallm-extract … --backend claude-cli` / `LEGALLM_LLM_BACKEND=claude-cli`. **First live result (406937652, Sonnet 5, effort medium, prompt v1):** span [19461, 25754) vs rules [19304, 25754), **IoU 0.976**; the LLM excluded the "statutory addendum" preamble that Noah's audit note on this document flagged; 5 parties, posture, 10 key events, 8+ record cites, 1 case cite; 16 s wall; CLI cost estimate $0.40 at API rates (subscription-billed, not charged). Validator change: citation fidelity now ignores whitespace and dash/quote glyphs (`1- ER-102` hyphen-break artifacts). Caveats: works only on a logged-in machine (not for C14 deploy); `--effort` exposed but no `temperature`; Claude Code's own system prompt is prepended (≈60k cached tokens/call).
- 2026-09-14 · **Item 5 (C5 gold tooling) done:** `evals/gold/gold_v1.jsonl` (120 records: g001–g100 = audit set with rules_v2 spans + strata; f001–f020 = `no_facts_span` failures sampled seed 42 from the 370 with local PDFs; ids/offsets/labels only, `doc_sha1` pins the text; all 120 verified against recomputed doc_text), `gold_v1.meta.json`, `LABELING_GUIDE.md` (rubric, 9 boundary rules incl. the g001 addendum question → *exclude, note it*, ambiguity rules), `legallm-gold init|verify|stats|label`, Streamlit labeler `labeler_app.py` (anchor-based boundary correction reusing `find_anchor`, atomic JSONL saves). **Noah's turn: label** (`pip install -e ".[label]"` → `legallm-gold label`), target 100 rated / ≥40 corrected (low+medium first) / 20 failures located.
- 2026-09-14 · **Item 6 (C7 harness + C6 deterministic metrics) done:** `extraction_eval.py` / `legallm-xeval --methods rules_v2 llm-v1 --subset labeled|all|smoke [--backend claude-cli] [--offline]`. Per doc: predicted span, **span IoU vs gold**, IoU-derived 3-class auto-rating (≥0.9 correct / ≥0.5 partial) with a human↔auto confusion table so the thresholds get calibrated, validator pass + citation fidelity, field coverage, extractor notes/flags (C8 seed), cost + latency + tokens; aggregate + stratified (source / confidence / len_bin), rules↔LLM **agreement** on unlabeled docs, paired IoU deltas with worst-docs list, **recovered-span rate** on the failure stratum. Outputs `evals/runs/<run_id>/{per_doc.jsonl,summary.json,report.md,manifest.json}` (no brief text); extractions cached under `data/processed/xeval_cache/` by (prompt_sha, model, effort, backend, doc_sha1) so re-runs are free. CI smoke = `tests/fixtures/xeval_smoke/` (3 synthetic briefs + labeled gold, no PDFs/API). Not yet in C6: field exact/partial match (gold v1 has no field labels), downstream resolution %/Recall@10 (item 10), judge (item 9).
- 2026-09-14 · **Item 7 (first results table) — scaffolding in, numbers pending the 120-doc llm-v1 run:** `results_page.py` / `legallm-xeval --render <run_dir>` writes `evals/RESULTS.md` (methods, headline table, agreement, by-source, field coverage, how-to-read; says *labels pending* when n_gold=0). `evals/error_taxonomy.md` v0 from reading all 20 rules failures: **A1 not-a-brief ×8** (clerk letters, notice-of-appeal form, docket sheet, pro se guide — leaked in via `--no_scope_filter`), **A2 heading fused with body ×6** (PDF line merge), **A3 title-case/numbered headings ×3**, **A4 headings present but extractor failed ×3** (investigate), **A5 intro-only ×1**; plus the audit-set note strata (toc_contamination 23, fallback 15, …) and hypotheses H1–H4 for the LLM run. `evals/iterations.md` seeded with the rules_v2 and llm-v1 rows.
- 2026-09-15 · **Item 7 done — first results table** (`evals/RESULTS.md`, run `llm-v1-all_20260915-021057_0c9ab4`, 120 docs, 0 labels yet): llm-v1 span found 68.3 % vs rules 83.3 %; validator pass 48.3 % vs 83.3 %; citation fidelity 0.981 (after making the check hyphen-insensitive); rules↔LLM IoU 0.478 mean (0.98 median where rules are `high`, 0.11 where `low`); cost $0.276/doc (CLI estimate, subscription-billed), 31.6 s/doc; fields: parties 97.5 %, posture 96.7 %, 7.6 key events/doc. **Headline reading:** the span-found gap is 17 audit docs the LLM says have *no facts section* (corrected 2026-09-15 from 27, which had included 10 failure-stratum docs) (reply/amicus/declarations that leaked in via `--no_scope_filter`; rules emitted low-confidence fallback spans there) plus 11 anchor failures — gold labels will adjudicate. Taxonomy §D adds R1 rules-false-positive, L1 invented span on attachment (2/8), L2 anchor not found (11), L3 non-verbatim cites (72 in 27 docs), L4 run-to-run drift, L5 transient CLI errors (2, retried OK). Anchors now stored in provenance. Labeling guide gains rules for reply/amicus/declaration/attachment docs.
- 2026-09-15 · **Item 8 done — llm-v2** (`prompts.py` v2, prompt_sha `aa4020336ae219ec`; v1 frozen and test-pinned). Prompt changes map to taxonomy classes R1/L1 (has_facts gate, no attachments), A2/A3 (heading forms), L2 (contiguous anchors), L3 (cites as printed); code: 8/6/4-word anchor relaxation, one CLI retry, anchors in provenance. Run `llm-v2-all_20260915-040449_c762da` (120 docs, 0 errors): span found 65.8 %, all 8 non-briefs now no-facts, L2 hard failures 11→8 (+9 rescued), v1↔v2 agreement median 1.0, rules↔v2 0.507. **L3 negative result:** the instruction did not stop list/range expansion (152 expansions vs 41), so the validator gained a *citation support* tier (page numbers printed near the same prefix): support 0.985 vs strict verbatim 0.962. **L4 measured:** 10 docs × 3 runs, 30/30 pairs IoU ≥ 0.999 — deterministic enough for a CI IoU gate (D8). `evals/RESULTS.md` re-rendered with three methods.
- 2026-09-15 · **Item 9 pulled forward as a pre-labeling pass (Noah's call: obvious span errors don't need human nuance).** `judge.py` / `legallm-judge`: Opus 5 reads each doc with both candidate spans marked inline, rates per rubric, codes issues, proposes anchors. Run `judge-v1_20260915-153046_975e61` (120 docs, 0 errors, 0 contradictions): rules_v2 38/21/41 correct/partial/incorrect on the audit set vs llm-v2 91/1/8; 33 docs have no facts section; every `low`-confidence rules span is wrong (23/23). Preview if accepted as gold: llm-v2 IoU 0.928 (≥0.9 on 91.5 %) vs rules 0.565. `legallm-gold prefill` attaches verdicts as suggestions (done); `legallm-gold accept-judge --policies …` bulk-accepts under an explicit policy with `labeler=judge:claude-opus-5`, kept separate from human labels; the labeler shows the suggestion with one-click accept and now saves write-through. Dry run: nonbrief 32, rules_correct 8, llm_correct 20, corrected 56 → 116 of 118 pending. **Decision (Noah, 2026-09-15): accept all four policies** → 116 judge-labeled + 2 human + 2 pending; Noah reviews a 33-doc set (`evals/gold/review_set_v1.txt`: the 2 pending, the 19 `partially_correct` verdicts, 3 sampled per policy) as human labels for κ. `evals/RESULTS.md` re-rendered on the labeled set (118 gold, 2 human): llm-v2 IoU 0.928 (≥0.9 on 91.5 %) vs rules 0.565 (45.8 %); paired wins 73 / ties 37 / losses 8.

## 12 · Provenance

- Skill plan + calendar blocks: chat "In-demand AI and tech certifications for job market competitiveness" (Sep 13, 2026).
- Repo state: `STATE.md` (Claude Code inventory, 2026-09-14, commit 9ce39a7) read directly from the now-public repo; earlier description from chat "Tailored resume for job position" (May 2026) was incomplete (predated M2–M4).
- Skills map: DeepLearning.AI letters cited in §8.
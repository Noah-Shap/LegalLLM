# CLAUDE.md — LegalLLM

LegalLLM is a rule-based data-curation pipeline for U.S. court merits briefs: it searches
CourtListener/RECAP, downloads PDFs, extracts text (pypdf → PyMuPDF → selective Tesseract OCR),
slices out the "Statement of Facts" span with heading heuristics, extracts and resolves case
citations, and evaluates retrieval baselines (popularity / BM25 / dense / hybrid). It is being
converted into a deployed LLM extraction app with a disciplined eval loop (Phase 1, Sep 2026).

**Read `docs/intent.md` and `STATE.md` before any task.** `STATE.md` is the measured inventory
(2026-09-14); `GAP.md` maps target components to what exists.

## Rules (non-negotiable)

- R1 **No destructive git.** No `push --force`, no history rewrite, no branch deletion, no
  `reset --hard` on tracked work. If history rewriting is ever needed (e.g., a leaked secret),
  **stop and report**.
- R2 **Never commit data or secrets.** PDFs, parquet, JSONL outputs, `.env`, API keys,
  CourtListener tokens → gitignored. Verify before every commit.
- R5 **Do not run the pipeline against live CourtListener/RECAP.** Inventory only. Reading
  existing outputs is fine; new network fetches are not. (Lift only when a task explicitly
  asks for a new build.)
- Never commit data; never hit live APIs in tests (mock `requests`).

## Layout

- `src/legallm/` (src layout): `pipeline.py` (end-to-end build), `facts_extractor.py`
  (rules_v2 span extractor), `ocr_decision.py` (single source of truth for OCR thresholds),
  `ocr_backend.py`, `citation_extractor.py`, `citation_resolver.py`, `build_manifest.py`,
  `dataset.py`, `baselines.py`, `eval_harness.py`, `eval_cli.py`, `cli.py`.
  Phase-1 layer: `schema.py` (C1 `FactsExtraction`, pydantic), `baseline_adapter.py` (C3 rules_v2 →
  schema; `preprocess_text` defines the offset contract), `validators.py` (C4 deterministic checks),
  `single_doc.py` (one PDF/text → extraction + validation; extractor registry for LLM methods).
  `llm_extractor.py` (C2, Sonnet 5, anchor-based spans, provenance), `prompts.py` (versioned prompts),
  `claude_cli.py` (headless `claude -p` transport; strips API key, runs in an empty temp dir).
  `routing.py` (`llm-v3`: Sonnet 5 at prompt v2 first, Opus 5 on anchor failure / validator flag / error; both passes in provenance).
  `api.py` (C10 FastAPI: `POST /extract` PDF/text → extraction + validation [+ rules baseline], `GET /health`; JSONL request log, rate limit),
  `ui_app.py` (C11 Streamlit side-by-side UI; in-process or via `LEGALLM_API_URL`), `observability.py` (C12 `evals/dashboard.md` from the request log + eval runs).
  `gold.py` + `labeler_app.py` (C5 gold manifest, verification, Streamlit labeler).
  `extraction_eval.py` (C6/C7: span IoU, auto-rating, fidelity, cost/latency; cached; `legallm-xeval`),
  `results_page.py` (evals/RESULTS.md renderer).
  `judge.py` (Opus 5 judge: rates candidate spans, names issues, proposes anchors; feeds gold prefill/accept).
  `downstream_eval.py` (C6 downstream: resolver-cache resolution % + BM25 Recall@10 on each method's span; cache only, no network).
- `evals/gold/` — tracked gold labels (ids + offsets only) and `LABELING_GUIDE.md`; `evals/runs/` — eval reports; `evals/judge/` — judge verdicts; `evals/RESULTS.md`, `evals/error_taxonomy.md`, `evals/iterations.md`.
- `tests/` — pytest, all offline (mock `requests`; PDFs built with PyMuPDF in tmp_path).
- `data/` — gitignored; see `data/README.md`. Primary build: `data/processed/facts_dataset_2k.parquet`.
- `reports/` — eval reports and the 100-doc gold audit set (unrated).
- Spec docs at repo root: `approved_spec_package_v0_2.md`, `facts_extraction_spec_v1.md`,
  `critical_evaluation_v0_2.md`, `roadmap_risk_register_stakeholder_schedule_v0_2.md`.

## Commands

```bash
pip install -e ".[dev]"                      # python >= 3.12; use .venv (3.13)
pytest tests/ -v                             # ~40 s (hybrid tests load a local sentence-transformers model)
ruff check src/ tests/ && ruff format --check src/ tests/
mypy src/legallm/                            # must be clean (CI gate)
legallm --query "..." --max_docs N [--no_scope_filter] [--resolve_citations] [--enable_ocr]   # LIVE API — see R5
legallm-eval --parquet data/processed/facts_dataset_2k.parquet --baselines popularity bm25
legallm-extract data/raw/pdfs/<id>.pdf [--json --out out.json] [--method rules_v2]   # single doc, offline
legallm-extract <pdf> --method llm-v2 --backend claude-cli   # Sonnet 5 via headless claude -p (subscription, no API credits)
legallm-extract <pdf> --method llm-v3 --backend claude-cli   # routed: Sonnet 5, escalate to Opus 5 when the cheap pass fails
legallm-extract <pdf> --method llm-v1                        # same via Messages API (needs funded ANTHROPIC_API_KEY)
legallm-gold stats | verify | label                          # gold set (evals/gold/gold_v1.jsonl); label = Streamlit UI
legallm-xeval --methods rules_v2 llm-v1 --subset labeled --backend claude-cli   # extraction eval -> evals/runs/<id>/report.md
legallm-xeval --render evals/runs/<id>                       # curated evals/RESULTS.md from a run
legallm-judge --run evals/runs/<id> --methods rules_v2 llm-v2 --backend claude-cli   # Opus 5 judge -> evals/judge/
legallm-gold prefill --judge evals/judge/<run>.jsonl ; legallm-gold accept-judge --policies nonbrief ...   # pre-labels
legallm-downstream --run evals/runs/<id> --methods rules_v2 llm-v2   # resolver % + BM25 R@10 per span source -> <run>/downstream.md (offline)
LEGALLM_LLM_BACKEND=claude-cli legallm-api --port 8000              # service; env: LEGALLM_DEFAULT_METHOD (llm-v3), LEGALLM_REQUEST_LOG (logs/requests.jsonl)
legallm-ui                                                           # Streamlit UI (in-process); LEGALLM_API_URL=http://host:8000 to use the service
legallm-dashboard                                                    # evals/dashboard.md from logs/requests.jsonl + evals/runs
```

## Environment

- `CL_TOKEN` — CourtListener API token (pipeline only; never literal in code).
- `ANTHROPIC_API_KEY` — Messages API backend (deploy); `LEGALLM_LLM_BACKEND=claude-cli` uses the subscription login instead (local only).
- `TESSDATA_PREFIX` — Tesseract data dir (OCR only).
- Conventions: `pathlib.Path` everywhere; all OCR thresholds go through `ocr_decision.py`;
  commit messages `chore(repo): …`, `docs(state): …`, `feat(...): …`.

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
  `gold.py` + `labeler_app.py` (C5 gold manifest, verification, Streamlit labeler).
  `extraction_eval.py` (C6/C7: span IoU, auto-rating, fidelity, cost/latency; cached; `legallm-xeval`).
- `evals/gold/` — tracked gold labels (ids + offsets only) and `LABELING_GUIDE.md`; `evals/runs/` — eval reports.
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
legallm-extract <pdf> --method llm-v1 --backend claude-cli   # Sonnet 5 via headless claude -p (subscription, no API credits)
legallm-extract <pdf> --method llm-v1                        # same via Messages API (needs funded ANTHROPIC_API_KEY)
legallm-gold stats | verify | label                          # gold set (evals/gold/gold_v1.jsonl); label = Streamlit UI
legallm-xeval --methods rules_v2 llm-v1 --subset labeled --backend claude-cli   # extraction eval -> evals/runs/<id>/report.md
```

## Environment

- `CL_TOKEN` — CourtListener API token (pipeline only; never literal in code).
- `TESSDATA_PREFIX` — Tesseract data dir (OCR only).
- Conventions: `pathlib.Path` everywhere; all OCR thresholds go through `ocr_decision.py`;
  commit messages `chore(repo): …`, `docs(state): …`, `feat(...): …`.

# STATE — LegalLLM — snapshot 2026-09-14 — commit 74ddfda

All numbers below come from commands run in this session on the local working tree.
`UNKNOWN` marks anything that could not be measured.

## 1. Tree

Depth-3 listing (excluding `.git`, `.venv`, caches, `__pycache__`, and the 8,627 files under `data/raw/pdfs/`):

```
.
├── .claude/settings.local.json          (tracked; permission allowlist only)
├── .env.example
├── .github/workflows/ci.yml
├── .gitignore  .pre-commit-config.yaml  pyproject.toml  requirements.txt  requirements-dev.txt
├── .coverage                            (ignored)
├── 2025.findings-acl.681.pdf            (21 MB, ignored; ACL paper)
├── test.pdf                             (0.5 MB, ignored)
├── CHANGELOG.md  CLAUDE.MD  CONTRIBUTING.md  LICENSE  README.md  PROJECT_SUMMARY.md
├── approved_spec_package_v0_2.md  critical_evaluation_v0_2.md
├── facts_extraction_spec_v1.md  roadmap_risk_register_stakeholder_schedule_v0_2.md
├── casecitationprediction_project_state.md  checklist.md  setupplan.md
├── intent.md                            (0 bytes — see §14)
├── ocr_decision.py                      (tracked LEGACY copy of src/legallm/ocr_decision.py; differs)
├── pymupdf_ocr_backend_updated.py       (tracked LEGACY copy of src/legallm/ocr_backend.py; differs)
├── run_pipeline_v3_abc_v3_updated_with_ocr.py  (tracked LEGACY pre-packaging pipeline, 960 LOC)
├── changelogs/                          (5 refactor changelogs, Feb 2026)
├── data/
│   ├── README.md
│   ├── raw/pdfs/                        (7,502 .pdf + 1,125 .txt; ignored)
│   └── processed/                       (11 parquet, 9 jsonl, 11 json, 1 log; see §5)
├── logs/pdf_parse_warnings.log          (0 bytes)
├── reports/                             (7 tracked .md eval/audit reports)
├── src/legallm/                         (13 modules; see §2)
└── tests/                               (13 files incl. conftest; empty tests/fixtures/)
```

Sizes (files, MB):

| Path | Files | MB |
|---|---:|---:|
| whole checkout incl. `.venv` and data | — | ~11,000 |
| `data/raw` | 8,628 | 9,500.8 |
| `data/processed` | 32 | 50.9 |
| `.venv` | 40,699 | 1,193.7 |
| root-level files (2 PDFs dominate) | 26 | 21.0 |
| `reports` | 7 | 1.7 |
| `.git` (161 loose objects) | 189 | 1.9 |
| `src` / `tests` | 25 / 26 | 0.4 / 0.5 |

## 2. Modules & responsibilities

LOC from `wc -l`; symbols from `grep -nE '^\s*(def |class )'`.

| Path | Purpose | Key functions / classes | LOC |
|---|---|---|---:|
| `src/legallm/__init__.py` | version string | — | 3 |
| `src/legallm/cli.py` | `legallm` entry point | imports `pipeline.main` | 6 |
| `src/legallm/pipeline.py` | end-to-end build: search → PDF → text → OCR routing → facts → citations → parquet + manifest | `cl_session`, `paged_get`, `search_recap_documents`, `derive_pdf_url`, `candidate_pdf_urls`, `download_pdf`, `extract_text_pypdf`, `extract_text_fitz`, `is_text_better`, `extract_text_best`, `doc_needs_ocr`, `in_scope_brief`, `derive_doc_type_id`, `main` | 938 |
| `src/legallm/facts_extractor.py` | rules_v2 facts-span extractor (heading map → classify/merge → validate) | `HeadingEntry`, `SectionSpan`, `ExtractionResult`, `strip_pacer_headers`, `merge_roman_heading_lines`, `build_heading_map`, `classify_sections`, `merge_fact_sections`, `validate_span`, `quality_flags`, `extract_facts_span`, `heading_candidates` | 815 |
| `src/legallm/ocr_decision.py` | pure-stdlib OCR heuristics (single source of truth) | `OcrDecisionConfig`, `page_text_metrics`, `strip_pacer_ecf_stamps`, `looks_like_garbage_text`, `looks_like_stamp_only`, `should_ocr_page`, `should_ocr_document` | 281 |
| `src/legallm/ocr_backend.py` | PyMuPDF + Tesseract selective page OCR | `check_ocr_ready`, `OcrMeta`, `extract_text_pymupdf_selective_ocr`, `extract_text_with_ocr_fallback`, `..._cached`, `_cli` | 466 |
| `src/legallm/citation_extractor.py` | regex citation extraction, reporter normalisation, dedup, masking | `ExtractedCitation`, `CitationExtractionResult`, `normalize_citation`, `extract_citations`, `deduplicate_case_citations`, `mask_citations`, `citation_summary` | 435 |
| `src/legallm/citation_resolver.py` | CourtListener citation → cluster-id resolver with cache + budget | `ResolverConfig`, `CacheEntry`, `CitationCache`, `BudgetTracker`, `ResolverMetrics`, `_fuzzy_match_result`, `_evaluate_results`, `_query_single_citation`, `resolve_citations`, `citation_to_target_dict` | 448 |
| `src/legallm/build_manifest.py` | build_id + manifest (git sha, dirty flag, dep versions, results) | `generate_build_id`, `BuildManifest`, `create_manifest`, `finalize_manifest`, `write_manifest`, `read_manifest` | 172 |
| `src/legallm/dataset.py` | row ids, minhash near-dup removal, stratified train/val/test split, loader | `generate_row_id`, `fuzzy_text_hash`, `deduplicate`, `label_cardinality_bin`, `split_dataset`, `load_dataset` | 220 |
| `src/legallm/baselines.py` | retrieval baselines | `RetrievalResult`, `aggregate_case_ids`, `PopularityBaseline`, `BM25Baseline` (TF-IDF via scikit-learn), `DenseRetrievalBaseline`, `HybridBaseline`, `RerankerBaseline` (sentence-transformers, optional) | 364 |
| `src/legallm/eval_harness.py` | Recall/MRR/nDCG@K, stratified + leakage + popularity-dominance checks, error analysis, model comparison, cost report | `recall_at_k`, `mrr_at_k`, `ndcg_at_k`, `evaluate`, `stratified_report`, `leakage_check`, `popularity_dominance_check`, `analyze_errors`, `compare_models`, `generate_cost_report`, `format_*` | 548 |
| `src/legallm/eval_cli.py` | `legallm-eval` entry point | `_make_model`, `main`, `_run_ablation` | 270 |
| `ocr_decision.py` (root) | legacy pre-packaging copy | same API as src version, `typing.Dict` style | 267 |
| `pymupdf_ocr_backend_updated.py` (root) | legacy pre-packaging copy | same API as `ocr_backend.py` | 461 |
| `run_pipeline_v3_abc_v3_updated_with_ocr.py` (root) | legacy monolithic pipeline incl. `rules_v1` extractor | `extract_facts_span` (v1), `quality_flags`, `main` | 960 |

Tests: `tests/conftest.py` (226 LOC, 11 fixtures) + 11 `test_*.py` files (see §8).

## 3. Pipeline stages (as implemented in `pipeline.main`)

| # | Stage | Entry point | Inputs → outputs | Routing / fallback |
|---|---|---|---|---|
| 0 | Manifest open | `build_manifest.create_manifest` | CLI params → `build_id` (sha256 of params, 12 hex) | records git sha + dirty flag + dependency versions |
| 1 | Sourcing | `search_recap_documents` → `paged_get` | `--query`, `--max_docs` → list of RECAP search hits (`/api/rest/v4/search/?type=rd`) | `CL_TOKEN` header; cursor pagination |
| 2 | PDF URL | `derive_pdf_url` | hit → `pdf_url`, strategy | `filepath_local` → direct fields → scrape CourtListener page; `no_pdf_url` failure |
| 3 | Scope filter | `in_scope_brief` | metadata (`short_description`/`description`) → keep/drop | skipped with `--no_scope_filter`; `out_of_scope` failure. No first-pages text gate, no sealed/encrypted check, no sha256 (spec v0.2 items not implemented) |
| 4 | PDF download | `download_pdf` + `candidate_pdf_urls` | url → `data/raw/pdfs/<search_id>.pdf` | tries www + storage hosts, `%PDF` magic check, HTTP 202 backoff, 3 retries; `pdf_pending` / `pdf_download_failed` |
| 5 | Text extraction | `extract_text_best` | pdf → (text, extractor ∈ {pypdf, pymupdf, none}, notes) | pypdf first; PyMuPDF if empty, or if `doc_needs_ocr` and `is_text_better` (alpha-count ≥1.5× or +800) |
| 6 | OCR routing | `doc_needs_ocr` → `ocr_decision.should_ocr_document`; `_maybe_run_ocr` → `ocr_backend.extract_text_with_ocr_fallback` | text → needs_ocr; pdf → OCR text + `OcrMeta` | only with `--enable_ocr` and `check_ocr_ready`; page-selective Tesseract; caps `--ocr_max_pages 300`, `--ocr_timeout_seconds 900`; `needs_ocr` failure if still low-text |
| 7 | Doc-type | `derive_doc_type_id` | court/description → one of 7 ids | drives INTRODUCTION policy in extractor; 1,563/1,599 rows in the 2k build are `UNKNOWN` |
| 8 | Facts span | `facts_extractor.extract_facts_span` | normalised text → (start,end) + meta (`rules_v2`) | Phase A heading map (exact/soft, TOC filter) → Phase B classify + merge → Phase C length guardrails + 5 quality gates → confidence high/medium/low; fallback pre-ARGUMENT slice; `no_facts_span` failure |
| 9 | Quality flags | `facts_extractor.quality_flags` | span → `cite_hits`, `arg_marker_hits`, per-10k densities | regex `RE_CASE_CITE`, `RE_ARG_MARKERS` |
| 10 | Citations | `extract_citations`, `citation_summary`, `mask_citations` | span → citation objects, counts, `facts_text_masked` | statutes/short-forms counted but excluded from case set |
| 11 | Resolution (opt.) | `citation_resolver.resolve_citations` | case citations → `targets_case_ids` (CourtListener cluster ids) | `--resolve_citations`; JSON cache, per-build/hour budget, fuzzy match, min confidence 0.90 |
| 12 | Failure log | inline `f_fail.write` | one JSON per failed hit → `facts_failures.jsonl` | codes: `no_pdf_url`, `out_of_scope`, `pdf_pending`, `pdf_download_failed`, `needs_ocr`, `no_facts_span` (NOT the spec's `FETCH_FAIL`/`DOC_TYPE_MISMATCH`/… taxonomy) |
| 13 | Output | `pd.DataFrame.to_parquet`, `write_manifest` | rows → `facts_dataset.parquet` (27 cols) + `build_manifest.json` | no `sha256_pdf`, `text_extractor`, `needs_ocr`, or `split` column in the pipeline parquet |

Post-pipeline (separate CLI): `dataset.load_dataset` (dedup + split) → `baselines.*` → `eval_harness.evaluate` → markdown report.

## 4. Entry points & run commands

| Command | What it does |
|---|---|
| `legallm --query "..." --max_docs N [--no_scope_filter] [--resolve_citations] [--enable_ocr --tessdata DIR] [--out_parquet P --failures_jsonl P --manifest_json P]` | full build (`legallm.cli:main` → `pipeline.main`) — **hits live CourtListener** |
| `legallm-eval --parquet data/processed/facts_dataset_2k.parquet --baselines popularity bm25 [dense hybrid reranker] [--error-analysis --compare --ablation] [--cost-report --manifest P] [--report-out P]` | offline evaluation (`legallm.eval_cli:main`) |
| `python -m legallm.ocr_backend <pdf>` | standalone OCR check (`_cli`) |
| `pytest tests/ -v` · `ruff check src/ tests/` · `ruff format --check src/ tests/` · `mypy src/legallm/` | QA |
| `pre-commit install` | hooks (ruff, mypy, large-file check 500 KB) |

Single-document end-to-end: no dedicated path. A single doc runs only via `legallm --query <id-specific query> --max_docs 1`, or by calling `extract_text_best` → `normalize_text` → `extract_facts_span` in Python. No Makefile, no notebooks.

## 5. Data artifacts (read-only inventory)

**Raw PDFs** — `data/raw/pdfs/`, gitignored: **Y** (`data/raw/` rule).

| Item | Value |
|---|---|
| PDF count / size | 7,502 files / 9,455.7 MB |
| `.txt` sidecars (OCR output from `--ocr_save_txt`) | 1,125 files / 45.2 MB |
| PDF mtime by month | 2026-01: 615 · 2026-02: 4,879 · 2026-04: 2,008 |
| files newer than last commit (2026-04-28) | 0 |

**Extracted text / backend distribution** — `UNKNOWN — pipeline parquet does not record text_extractor; only needs_ocr failure rows carry it.` Proxy: 1,125 `.txt` OCR sidecars exist for 7,502 PDFs (15.0%).

**Parquet outputs** (`data/processed/`, all gitignored: Y):

| File | Rows | Cols | Written | Notes |
|---|---:|---:|---|---|
| `facts_dataset_2k.parquet` | 1,599 | 27 | 2026-04-06 | **primary**: query "opening brief appellant statement of facts", 2,000 hits, no scope filter, resolver on (build `46864ffb7283`, commit 1e6d36b, dirty) |
| `facts_dataset_500_resolved.parquet` | 453 | 27 | 2026-04-05 | same query, 500 hits, resolver on |
| `facts_dataset_500_noscope.parquet` | 451 | 25 | 2026-04-05 | no resolver |
| `facts_dataset_500_v2.parquet` | 380 | 25 | 2026-04-05 | scope filter ON |
| `facts_dataset_1k.parquet` | 3 | 25 | 2026-04-05 | query "merits brief", scope filter ON → 991/1,000 out_of_scope |
| `facts_dataset.parquet` | 186 | 14 | 2026-02-21 | `rules_v1` legacy schema |
| `gold_audit_set.parquet` | 100 | 31 | 2026-04-06 | audit sample (+`targets`, `n_targets`, `facts_len`, `len_bin`) |
| `facts_dataset_test_resolve` / `facts_live` / `facts_test2` | 9 / 5 / 5 | 27 | 2026-04-05 | smoke runs |

Columns + dtypes of the primary 27-col schema: `search_result_id` int64 · `build_id` str · `short_description` str · `document_type` str · `doc_type_id` str · `pdf_url` str · `pdf_url_strategy` str · `facts_start` int64 · `facts_end` int64 · `facts_text` str · `facts_text_masked` str · `extractor_method` str · `extractor_notes` str · `extractor_confidence` str · `targets_case_ids` str (JSON list) · `resolved_citation_count` int64 · `cite_hits` int64 · `arg_marker_hits` int64 · `cite_hits_per_10k_chars` float64 · `arg_hits_per_10k_chars` float64 · `total_citations` int64 · `case_citations` int64 · `unique_case_citations` int64 · `short_form_count` int64 · `statute_count` int64 · `secondary_count` int64 · `normalized_case_cites` object.

**Failure logs** (`facts_failures*.jsonl`, gitignored: Y):

| File | Rows | `reason` value_counts |
|---|---:|---|
| `facts_failures_2k.jsonl` | 401 | no_facts_span 370 · needs_ocr 30 · pdf_download_failed 1 |
| `facts_failures_1k.jsonl` | 997 | out_of_scope 991 · no_facts_span 5 · needs_ocr 1 |
| `facts_failures_500_v2.jsonl` | 120 | out_of_scope 82 · no_facts_span 30 · needs_ocr 8 |
| `facts_failures_500_resolved.jsonl` | 47 | no_facts_span 39 · needs_ocr 8 |
| `facts_failures_500_noscope.jsonl` | 49 | no_facts_span 40 · needs_ocr 9 |
| `facts_failures.jsonl` (Feb) | 14 | no_facts_span 11 · out_of_scope 3 |
| `facts_failures_test_resolve.jsonl` | 1 | no_facts_span 1 |
| `facts_fail_live.jsonl`, `facts_fail_test2.jsonl` | 0 | — |

**Yield** (denominator = CourtListener search hits, as recorded in each `build_manifest`):

| Build | spans / hits | % | rows with ≥1 resolved target |
|---|---:|---:|---:|
| 2k, no scope filter, resolver on | 1,599 / 2,000 | 80.0 | 935 / 1,599 = 58.5 % (spec target ≥ 90 %) |
| 500 no scope | 451 / 500 | 90.2 | — |
| 500 scope filter on | 380 / 500 | 76.0 | — |
| 1k "merits brief" scope on | 3 / 1,000 | 0.3 | — |

Unique `search_result_id` in the 2k parquet: 1,506 of 1,599 rows (93 duplicate ids). 2k `extractor_confidence`: high 978 · low 361 · medium 260. `extractor_notes` top tokens (2k): toc_contamination 410 · merged_2_sections 399 · span_starts_very_early 374 · fallback_pre_argument 289 · low_alpha_ratio 249 · no_citations_in_facts 242 · guardrail_truncated 88 · merge_limit_warning 13.

**Discrepancy:** `reports/m4_cost_report.md` cites build `38a720b3324a` (1,819 / 2,000 spans, 7,649 API calls) — no manifest for that build exists on disk; the on-disk 2k manifest (`46864ffb7283`, 1,599 spans, 4,151 calls) was written after the reports (17:03 UTC vs 13:22 UTC on 2026-04-06). The eval reports were therefore produced from an earlier 2k build that was overwritten.

**Citation cache:** `citation_cache.json` 15,697 entries, `resolver_version` 1.0.0 (3.5 MB; untracked, not ignored before this session).

**Gold / labeled data:** `reports/gold_audit_set.md` (tracked, 35,786 lines, 1.7 MB) = 100 sampled spans with a rating slot each. Ratings filled: **0 / 100**. One free-text note added (uncommitted diff on Document 1). No other human labels exist.

## 6. Quality signals present

| Signal | Where | How computed | Distribution (2k build) |
|---|---|---|---|
| `cite_hits`, `cite_hits_per_10k_chars` | `quality_flags` | `RE_CASE_CITE` = `\b\d{1,4}\s+[A-Z][A-Za-z\.\s]{0,20}\s+\d{1,5}\b` | per-10k: mean 6.57, median 3.14, max 114.9 |
| `arg_marker_hits`, `arg_hits_per_10k_chars` | `quality_flags` | `RE_ARG_MARKERS` regex | per-10k: mean 0.24, 75th pct 0, max 9.0 |
| `extractor_confidence` | `validate_span` | heading match (1.0/0.7/0.5) minus gate downgrades | high 978 · medium 260 · low 361 |
| `extractor_notes` | `validate_span` | gates: toc_contamination, no_citations_in_facts, excessive_citations, possible/high_argument_contamination, low_alpha_ratio, span_starts_very_early, span_ends_very_late, guardrail_truncated, merge_limit_warning | see §5 |
| facts length | `facts_end - facts_start` | guardrails min 300–800, max `min(0.6·len, 50k)` | mean 16,883, median 13,810, min 329, max 49,993 |
| `resolved_citation_count` | resolver | count of ≥0.90-confidence CourtListener matches | mean 7.3, median 1, 41.5 % of rows = 0 |
| doc-type strata | `derive_doc_type_id` | court/description rules | UNKNOWN 1,563 · MERITS_SCOTUS 34 · DISTRICT_COURT 2 |
| eval leakage check | `eval_harness.leakage_check` | scans `facts_text_masked` for unmasked cites | run in `legallm-eval` unless `--skip-leakage-check` |

## 7. Spec & docs

| File | Title | Version | Last modified | Status |
|---|---|---|---|---|
| `approved_spec_package_v0_2.md` | Problem + Scope Spec | v0.2 | 2026-02-21 | master spec; several items not implemented (sha256, sealed check, first-pages gate, spec failure taxonomy, `targets_all`) |
| `facts_extraction_spec_v1.md` | Facts Span Extraction Specification | v1 | 2026-02-22 | implemented as `facts_extractor.py` (`rules_v2`) |
| `critical_evaluation_v0_2.md` | Critical Evaluation of v0.2 | — | 2026-02-22 | review; recommendations partly actioned |
| `roadmap_risk_register_stakeholder_schedule_v0_2.md` | Roadmap + Risk Register | v0.2 | 2026-02-21 | M0–M4 milestones; M1–M4 code exists, M1/M2 DoD thresholds not met (see §5 yield) |
| `PROJECT_SUMMARY.md` | Exhaustive repository summary | — | 2026-04-05 | most recent narrative; predates M3/M4 commits and 2k build |
| `casecitationprediction_project_state.md` | Project state | as of 2026-02-21 | 2026-02-21 | historical, pre-packaging |
| `checklist.md` / `setupplan.md` | Repo setup checklist / plan | — | 2026-02-21 | historical |
| `README.md` | LegalLLM | — | 2026-02-21 | stale: badge placeholders `<your-username>`, lists 4 modules of 13, no M2–M4 |
| `CLAUDE.MD` | Project context | — | 2026-02-21 | stale: "62 tests" (235 now), 4 modules listed; upper-case extension |
| `CONTRIBUTING.md`, `CHANGELOG.md` (0.1.0 only), `LICENSE` (MIT, 2026 Noah M), `data/README.md` | — | — | 2026-02-21 | data README lists only the v0 schema |
| `changelogs/*.md` (5) | per-file refactor changelogs | — | 2026-02-22 | historical |
| `reports/m3_baseline_report*.md`, `m4_all_baselines.md`, `m4_full_eval.md`, `m4_ablation.md`, `m4_cost_report.md` | eval reports | — | 2026-04-05/06 | 152 test queries; BM25 Recall@10 0.126 / MRR@10 0.180; hybrid 0.086; reranker 0.072; dense 0.037; popularity 0.019. BM25 best; dense/hybrid/reranker do NOT beat BM25 (M4 DoD unmet) |
| `reports/gold_audit_set.md` | Gold Audit Set | — | 2026-05-12 (uncommitted edit) | 100 docs, 0 rated |
| `intent.md` | — | — | 2026-09-14 | **0 bytes** |

## 8. Tests & CI

| Item | Value |
|---|---|
| framework | pytest 9.0.2 (+ pytest-cov), config in `pyproject.toml` |
| test files | `test_baselines`, `test_build_manifest`, `test_citation_extractor`, `test_citation_resolver`, `test_dataset`, `test_eval_cli`, `test_eval_harness`, `test_facts_extractor`, `test_ocr_backend`, `test_ocr_decision`, `test_pipeline` + `conftest.py` |
| `pytest --co -q` | **235 tests collected** |
| `pytest tests/ -q` | **235 passed, 1 warning, 40.66 s** (network calls are mocked; hybrid/reranker tests load a local sentence-transformers model) |
| `ruff check` / `ruff format --check` | pass / 26 files formatted |
| `mypy src/legallm/` | **3 errors** in `baselines.py` (lines 223, 274, 340: `no-any-return`, `union-attr`) |
| CI | `.github/workflows/ci.yml`: lint (ruff+mypy, py3.13) + test matrix (3.12/3.13) + codecov. **Triggers on branch `main` only; repo default branch is `master` → `gh run list` shows 0 runs ever.** mypy step would fail if it ran. |
| pre-commit | configured (ruff v0.5.0, mypy v1.10.0, large-file 500 KB); `reports/gold_audit_set.md` (1.7 MB) exceeds that limit |

## 9. Dependencies & environment

| Item | Value |
|---|---|
| build | hatchling, src layout, `requires-python >=3.12`, version 0.1.0 |
| runtime deps | requests ≥2.31, pandas ≥2.1, pypdf ≥4.0, PyMuPDF ≥1.24, tqdm ≥4.66, scikit-learn ≥1.4, numpy ≥1.26 (pyarrow pulled transitively; not declared) |
| optional | `[dense]` sentence-transformers ≥3.0 · `[dev]` pytest, pytest-cov, ruff, mypy, pre-commit, types-requests |
| lockfile | none (`requirements.txt` mirrors an older 5-dep list; no pins) |
| `.venv` python | 3.13.14; installed: legallm 0.1.0 editable, pandas 3.0.0, pyarrow 23.0.0, PyMuPDF 1.27.1, pypdf 6.6.2, scikit-learn 1.8.0, numpy 2.4.1, ruff 0.15.2, mypy 1.19.1, sentence-transformers (present; hybrid tests ran) |
| system python | 3.11.5 (below `requires-python`; do not use) |
| system deps | Tesseract v5.5.0 on PATH, `TESSDATA_PREFIX` set; poppler (`pdftoppm`) not on PATH (not required) |
| `pip install -e .` | UNKNOWN this session — not re-run; package is already installed editable from this path |

## 10. LLM usage

`grep -rniE 'anthropic|openai|langchain|litellm|transformers|instructor|pydantic'` over `src/`, `tests/`, `pyproject.toml`: **no anthropic / openai / langchain / litellm / instructor / pydantic references.** Only hits: `sentence-transformers` (optional dense/hybrid/reranker baselines in `baselines.py`, `eval_cli.py`, `test_baselines.py`). No LLM calls anywhere in the pipeline; facts extraction is entirely rule-based. (`facts_extraction_spec_v1.md` §9 lists LLM-assisted extraction as deferred.)

## 11. Git state

| Item | Value |
|---|---|
| remote | `origin` = https://github.com/Noah-Shap/LegalLLM.git |
| GitHub | owner `Noah-Shap`, **visibility PRIVATE**, default branch `master`, last push 2026-04-28T15:15:07Z |
| local branch | `master`, ahead 0 / behind 0 vs `origin/master` |
| HEAD | `74ddfda` "Add spec documents, evaluation reports, project summary, and gold audit set" — 2026-04-28 11:14 -0400 |
| history | 12 commits since `a7a0694` Initial commit (2026-02-21) |
| tracked files | 65 |
| uncommitted (at session start) | `M reports/gold_audit_set.md` (+3/−2, audit note on Document 1) |
| untracked (at session start) | 11 files in `data/processed/` (6 build manifests, 3 citation caches, 2 smoke manifests — `.json` was not ignored) + `intent.md` |
| ignored | 32 paths (`data/raw/`, parquet/jsonl, `.venv`, root PDFs, `.coverage`, caches) |
| `gh auth` | logged in as `Noah-Shap` (active) and `noahmattshap` |
| **after this session** | pushed `74ddfda..a77518d` to `origin/master` (4 commits: hygiene, audit note, STATE.md, CLAUDE.md+GAP.md) plus this STATE.md update. Visibility still **PRIVATE** (R3: not changed without Noah). Archive for chat-side Claude: `C:\Users\noahm\CodingProjects\legalllm_a77518d.zip` (78 tracked files, 0.7 MB, no data). |

## 12. Secrets & PII scan

| Check | Result |
|---|---|
| `grep -rniE 'api[_-]?key|token|secret|password'` (excluding `.git`, `.venv`, data text) | only `.env.example` placeholder (`CL_TOKEN=your_token_here`) and `CL_TOKEN` env lookups in code; tokens are never literal |
| `.env`, `credentials*.json`, `*.pem`, `*.key` in working tree | none |
| git history (`git log -p -S 'CL_TOKEN='`; added-file names) | only placeholder values; no `.env`/credential file ever committed |
| `.claude/settings.local.json` | tracked; contains a Bash permission allowlist only |
| committed data with party names | **Yes.** `reports/gold_audit_set.md` (tracked, 1.7 MB) embeds full facts spans from 100 RECAP briefs including party/attorney names and PDF URLs. `reports/m4_full_eval.md` contains CourtListener case ids only. Briefs are public court records, but the roadmap's licensing section classes facts-span text as *internal-only by default* — this file should be reviewed before the repo goes public. |
| gitignored PDFs/parquet | contain party names (public record); not tracked |

## 13. Delta since last known snapshot

`intent.md §3` is empty, so the comparison baseline is `PROJECT_SUMMARY.md` (2026-04-05) and `casecitationprediction_project_state.md` (2026-02-21):

- **New since PROJECT_SUMMARY:** M2 citation extraction + resolver (`citation_extractor.py`, `citation_resolver.py`), build manifests, `dataset.py` splits, M3 baselines + eval harness, M4 hybrid/reranker/ablation/cost report, `legallm-eval` CLI, `derive_doc_type_id` now wired into the pipeline, 235 tests (was 92), reports/, gold audit set (100 docs, unrated), 2k-hit build with 1,599 spans, 7,502 PDFs (was 5,644).
- **Changed:** `extractor_method` `rules_v1` → `rules_v2`; scope filter relaxed and 2k build run with `--no_scope_filter`; merge limit raised (notes show `merged_5/6_sections`).
- **Unchanged / still missing vs spec v0.2:** sha256 provenance, sealed/encrypted detection, first-pages doc-type gate, spec failure taxonomy codes, `targets_all` objects with `excluded_reason`, `needs_ocr`/`text_extractor` columns in the modeling row, exclusion-rate report, CI actually running.
- **Activity gap:** no code commits or data since 2026-04-28; only the gold-audit note (2026-05-12) and the empty `intent.md` (2026-09-14).

## 14. Open questions for Noah

1. `intent.md` is 0 bytes (the IDE shows it open as `INtENT.md`). Paste the content so `docs/intent.md`, GAP.md's component list, and §13 can be finalised.
2. Which build is canonical for Phase 1: the on-disk `facts_dataset_2k.parquet` (1,599 rows, build `46864ffb7283`) or the overwritten build `38a720b3324a` that the M4 reports were computed on?
3. `reports/gold_audit_set.md` embeds 100 full facts spans (party names, 1.7 MB) and is tracked. Keep it in a public repo, or move the text to an ignored data file and keep only ids + ratings tracked?
4. Should the three legacy root scripts (`ocr_decision.py`, `pymupdf_ocr_backend_updated.py`, `run_pipeline_v3_abc_v3_updated_with_ocr.py`) be removed? They are superseded by `src/legallm/` (not done this session per "no reorganisation").
5. CI has never run because the workflow targets `main` while the branch is `master`. Rename branch to `main`, or change the workflow? (Not changed this session.)
6. Repo name: keep `LegalLLM` for the public repo, or choose a product name?
7. Which GitHub account should own the public repo — `Noah-Shap` (current) or `noahmattshap` (also authenticated)?


## 12 · Phase-1 outcome (2026-09-16, appended)

The inventory above is the 2026-09-14 snapshot. Phase 1 (build-order items 1–14 in `GAP.md` §D) is complete except the
hosted demo: LLM extractor (`llm-v1` → `llm-v2` → routed `llm-v3`), 120-doc gold set (35 human + 85 judge-accepted,
κ 0.885), extraction eval harness, Opus 5 judge, downstream eval, FastAPI service + Streamlit UI + request log,
CI smoke gate, injection guard, deploy package. Current numbers: `evals/RESULTS.md`; history: `docs/intent.md` §11;
tradeoffs: `ARCHITECTURE.md`. Tests: 472 offline.

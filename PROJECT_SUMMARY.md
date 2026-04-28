# LegalLLM Repository — Exhaustive Summary

## 1. Project Purpose & Research Goal

LegalLLM is a data pipeline that builds a **benchmark-grade dataset** of "Statement of Facts" sections extracted from U.S. court merits briefs for **legal citation prediction research**. The core research question: given a factual narrative from a brief, can a model predict which cases/opinions will be cited?

The pipeline sources documents from **CourtListener/RECAP** (the Free Law Project's open legal data ecosystem), extracts text from PDFs, isolates the factual narrative section via rule-based heading detection, and outputs structured datasets suitable for training retrieval and classification models.

---

## 2. Repository State & Git History

- **Single commit**: `a7a0694` ("Initial commit") on `master` branch, dated 2026-02-21.
- **Uncommitted changes** (working tree): A major refactor is in progress — facts extraction logic has been extracted from `pipeline.py` into a new dedicated `facts_extractor.py` module, with corresponding test restructuring. Specifically:
  - `pipeline.py`: 263 lines removed (all facts extraction code moved out)
  - `conftest.py`: 153 lines added (6 new test fixtures)
  - `test_pipeline.py`: 118 lines removed (facts-related tests moved to new file)
  - New untracked files: `src/legallm/facts_extractor.py`, `tests/test_facts_extractor.py`, plus several spec/planning documents and changelogs
- **Version**: 0.1.0 (as declared in `pyproject.toml` and `__init__.py`)

---

## 3. Architecture & Source Code

### 3.1 Package Structure (src layout)

```
src/legallm/
  __init__.py          # Version string ("0.1.0")
  cli.py               # Thin CLI entry point, delegates to pipeline.main()
  ocr_decision.py      # Shared OCR heuristics (pure stdlib, ~280 lines)
  ocr_backend.py       # PyMuPDF + Tesseract selective OCR (~465 lines)
  pipeline.py          # End-to-end pipeline (~768 lines)
  facts_extractor.py   # Facts extraction module (NEW, untracked, ~799 lines)
```

### 3.2 Pipeline (`pipeline.py`) — End-to-End Flow

The pipeline implements a 7-stage process:

1. **Search** — Queries CourtListener REST v4 API (`/search/?type=rd`) for RECAP documents. Uses paginated GET with configurable `max_docs`. Requires `CL_TOKEN` env var for auth.

2. **PDF URL Derivation** — Multi-strategy URL resolution:
   - Prefers `filepath_local` → `https://storage.courtlistener.com/<path>`
   - Falls back to direct PDF fields (`download_url`, `file_url`, etc.)
   - Last resort: scrapes the public CourtListener webpage for a `.pdf` href

3. **Scope Filtering** — `in_scope_brief()` function aggressively selects merits briefs and excludes:
   - Non-brief filings (orders, mandates, transcripts, appendices)
   - Motion/memo filings masquerading as briefs
   - Amicus briefs, reply briefs
   - Claim construction briefs
   - Requires role keywords (opening, response, appellant, appellee, initial, opposition)

4. **PDF Download** — Robust download with:
   - Candidate URL generation (tries both `www.courtlistener.com` and `storage.courtlistener.com`)
   - `%PDF` magic byte validation
   - HTTP 202 ("pending") detection with exponential backoff
   - 3 retry attempts

5. **Text Extraction** — Multi-strategy with quality comparison:
   - Primary: `pypdf` (PdfReader)
   - Fallback: `PyMuPDF` (fitz) if pypdf produces no text or garbage
   - `is_text_better()` compares alpha-char counts with a substantial improvement threshold (1.5x or +800 alpha chars)
   - Delegates OCR decisions to `ocr_decision.py`

6. **OCR Integration** (optional, `--enable_ocr`):
   - Uses PyMuPDF's Tesseract integration for selective page-level OCR
   - Shared `OcrDecisionConfig` ensures page-level and doc-level criteria stay aligned
   - Safety limits: `--ocr_max_pages` (300), `--ocr_timeout_seconds` (900)
   - Optional `.txt` output persistence

7. **Facts Extraction + Output**:
   - Calls `extract_facts_span()` on normalized text
   - Computes quality flags (citation density, argument markers)
   - Outputs `facts_dataset.parquet` (successes) + `facts_failures.jsonl` (structured failure log)

**CLI flags**: 20+ configurable parameters including query, max_docs, output paths, scope filtering, OCR settings, and search field selection.

### 3.3 OCR Decision Module (`ocr_decision.py`)

A pure-stdlib module (no PyMuPDF/pypdf imports) providing centralized OCR heuristics:

- **`OcrDecisionConfig`** — Frozen dataclass with ~17 tunable thresholds for page-level and document-level decisions
- **`page_text_metrics()`** — Computes chars, alpha_ratio, weird_token_ratio, word_count, unique_word_count, nonempty_lines
- **`strip_pacer_ecf_stamps()`** — Removes PACER/ECF header stamp lines using regex patterns
- **`looks_like_garbage_text()`** — Detects broken extraction (PDF internals like `/i255` tokens, very low alpha ratio)
- **`looks_like_stamp_only()`** — Detects pages where only PACER stamps were extracted
- **`should_ocr_page()`** — Page-level OCR decision based on 6 checks (garbage, stamp-only, few chars, few words, low alpha, weird tokens)
- **`should_ocr_document()`** — Document-level decision with additional density checks; can override weak reasons if chars_per_page is sufficient

### 3.4 OCR Backend (`ocr_backend.py`)

PyMuPDF + Tesseract selective OCR backend:

- **`check_ocr_ready()`** — Validates all OCR dependencies (fitz importable, `get_textpage_ocr` method exists, tesseract on PATH, tessdata directory found, language traineddata present)
- **`extract_text_pymupdf_selective_ocr()`** — Core extraction: native text first, OCR only on "bad" pages per `should_ocr_page()`. Supports force_ocr, max_pages, timeout, debug metrics collection
- **`extract_text_with_ocr_fallback()`** — Convenience wrapper used by pipeline
- **`extract_text_pymupdf_selective_ocr_cached()`** — SHA1-based caching for repeat runs
- **`OcrMeta`** dataclass — Rich metadata (backend, pages attempted/succeeded, elapsed time, per-page metrics)
- Standalone CLI interface

### 3.5 Facts Extractor (`facts_extractor.py`) — NEW, Untracked

Implements the v1 facts extraction specification with a three-phase architecture replacing the previous three-tier waterfall:

**Phase A: Build Heading Map**
- Scans entire document for candidate headings using combined exact regex + soft keyword matching
- 24 exact start headings (e.g., STATEMENT OF FACTS, NATURE OF THE CASE, PRELIMINARY STATEMENT, COUNTER-STATEMENT OF FACTS)
- 1 conditional heading: INTRODUCTION (classified per document type via `DOC_TYPE_HEADING_POLICY`)
- 18 exact stop headings (e.g., ARGUMENT, STANDARD OF REVIEW, PRAYER FOR RELIEF)
- 7 soft start keywords and 7 soft stop keywords, all using regex word-boundary matching (fix from v0's bare substring matching)
- 12 bad heading fragments filtered (TABLE OF CONTENTS, CERTIFICATE, etc.)
- TOC entry detection (dot-leader + page number patterns within 15k chars of a TOC marker)
- Deduplication of overlapping heading entries

**Phase B: Section Classification + Merge**
- Walks heading map, classifies each inter-heading span by role (facts, procedural_history, argument, standard_of_review, conclusion, other)
- Merges adjacent fact-like sections (facts + procedural_history)
- Merge limit of 4 sections (warns if exceeded)
- Does not merge across stop headings

**Phase C: Validation + Quality Gates**
- Min length: 400 chars (exact), 300 chars (soft), 800 chars (fallback)
- Max length: `min(0.60 * full_text_len, 50_000)` with paragraph-break-aligned truncation
- Gate 1: TOC contamination (>5 dot-leader lines)
- Gate 2: Citation density (warnings for 0 citations or >80 per 10k chars)
- Gate 3: Argument contamination (>5.0 hits/10k -> medium, >15.0 -> low confidence)
- Gate 4: Alpha ratio (<0.50 -> downgrade)
- Gate 5: Position sanity (span starts <5% or ends >95% of document)
- Composite confidence: high/medium/low based on heading match + quality gate downgrades

**Fallback**: If no fact-like sections found but ARGUMENT heading exists, takes pre-ARGUMENT slice (low confidence, 0.5)

**Document-type reference table**: 7 document types (FEDERAL_APPELLATE_OPENING/RESPONSE, STATE_APPELLATE, CERT_PETITION, MERITS_SCOTUS, DISTRICT_COURT, UNKNOWN) controlling INTRODUCTION classification. Not yet connected to the pipeline's main loop (defaults to UNKNOWN).

---

## 4. Test Suite

**92 tests total** (collected), across 4 test files:

### `tests/test_ocr_decision.py` — 24 tests
- `page_text_metrics`: normal text, empty, whitespace-only, garbage
- `strip_pacer_ecf_stamps`: stamp removal, no stamps, empty, None
- `looks_like_garbage_text`: true/false/empty/PDF internals
- `looks_like_stamp_only`: true/false
- `should_ocr_page`: good text, empty, garbage, too few chars, custom config
- `should_ocr_document`: good, empty, too little, page count override, garbage
- `OcrDecisionConfig`: defaults, custom, frozen immutability

### `tests/test_ocr_backend.py` — 3 tests
- `OcrMeta` dataclass defaults and custom values
- `check_ocr_ready` with mocked fitz=None

### `tests/test_pipeline.py` — 19 tests (after refactor, down from 32)
- `normalize_text`: 6 tests (hyphen break, whitespace, newlines, CRLF, trailing spaces, empty)
- `in_scope_brief`: 9 tests (opening, response, amicus, reply, motion, no keyword, no description, claim construction, description fallback)
- `candidate_pdf_urls`: 4 tests (www, storage, other, no duplicates)

### `tests/test_facts_extractor.py` — 46 tests (NEW, untracked)
- `TestBuildHeadingMap`: 11 tests (exact/soft headings, TOC filtering, new headings, PACER headers, word boundary, INTRODUCTION tracking, stop headings)
- `TestClassifyAndMerge`: 5 tests (single section, multi-section merge, stops at argument, merge limit, counter-statement)
- `TestValidation`: 5 tests (min length, max length, TOC contamination, argument contamination, high confidence)
- `TestExtractFactsSpan`: 12 tests (exact match, no match, TOC skip, soft headings, fallback, multi-section, counter-statement, nature of case, introduction factual/argumentative, schema, max length)
- `TestQualityFlags`: 4 tests (citations, arg markers, empty, no matches)
- `TestHeadingCandidates`: 4 tests (finds, excludes bad, empty, limit)
- `TestPreprocessing`: 3 tests (strip PACER, merge roman, preserve normal)

### Shared Fixtures (`conftest.py`) — 11 fixtures
- `sample_brief_text`, `sample_brief_multi_section`, `sample_brief_counter_statement`, `sample_brief_nature_of_case`, `sample_brief_introduction_factual`, `sample_brief_introduction_argumentative`, `sample_brief_very_long_facts`, `sample_brief_soft_headings`, `sample_pacer_stamp`, `sample_garbage_text`, `normal_english_text`

---

## 5. Data & Pipeline Run Results

### Downloaded Data
- **5,644 PDFs** in `data/raw/pdfs/`
- **1,125 .txt files** (OCR output saved alongside PDFs)
- Files named by CourtListener search result ID (numeric)

### Pipeline Output
- **`facts_failures.jsonl`**: 14 failure records from a recorded run
  - `no_facts_span`: 11 (heading detection couldn't find facts section)
  - `out_of_scope`: 3 (filtered by scope policy)
- **`facts_dataset.parquet`**: Present (gitignored, generated locally)

### Failure Taxonomy
The pipeline logs structured failures with these codes: `no_pdf_url`, `out_of_scope`, `pdf_pending`, `pdf_download_failed`, `needs_ocr`, `no_facts_span`. Each failure includes diagnostic metadata (search ID, PDF URL, heading candidates, text snippets, OCR metrics).

---

## 6. CI/CD & Tooling

### GitHub Actions CI (`.github/workflows/ci.yml`)
- **Lint job**: ruff check, ruff format, mypy (Python 3.13)
- **Test job**: Matrix on Python 3.12 + 3.13, pytest with coverage, Codecov upload

### Pre-commit Hooks (`.pre-commit-config.yaml`)
- ruff (lint + format, v0.5.0)
- trailing-whitespace, end-of-file-fixer, check-yaml, check-toml
- check-added-large-files (500KB limit)
- mypy (v1.10.0)

### Build System
- Hatchling backend (`pyproject.toml`)
- Console entry point: `legallm = "legallm.cli:main"`
- Python >=3.12 required

### Dependencies
- **Runtime**: requests, pandas, pypdf, PyMuPDF, tqdm
- **Dev**: pytest, pytest-cov, ruff, mypy, pre-commit, types-requests

---

## 7. Specification & Planning Documents

### `approved_spec_package_v0_2.md` — Problem + Scope Spec
The master spec defining:
- **Dataset Inclusion Policy**: Deterministic, rule-based doc-type validation. Only party-filed merits briefs eligible. Explicit exclusion of amicus, appendices, TOA/TOC, motions, sealed/restricted docs.
- **Label semantics**: Phase-1 targets are judicial opinions only. Short-form cites excluded. Parallel citations collapsed to single canonical ID.
- **Resolver architecture**: Local extraction -> normalization -> API verification with normalized strings only. Chunked batching, exponential backoff, 0.90 confidence threshold, persisted cache.
- **Data contracts**: 6 schemas (pdf_manifest, inclusion_validation, extraction, facts_span, citation_targets, modeling_row)
- **Success metrics**: PDF acquisition >=98%, text extraction >=92%, facts span >=85%, citation targets >=90%, 100% failure taxonomy coverage
- **Modeling targets**: Recall@10 >= 0.10, MRR@10 >= 0.05 for lexical baseline; dense retrieval beats lexical by +10% relative
- **Gold Audit Set**: 50-200 briefs, stratified sampling, >=80% facts correctness, >=95% resolution correctness
- **Leakage controls**: Citation masking, near-duplicate split prevention, no citation-graph features
- **Operational envelope**: 1K briefs MVP / 10K stretch; 300-page hard cap; $100/week OCR; 25K resolver lookups/day

### `facts_extraction_spec_v1.md` — Facts Extractor Design
Detailed specification for the `facts_extractor.py` module (described in Section 3.5 above). Includes heading vocabulary, algorithm pseudocode, quality gates, acceptance criteria, and regression coverage requirements.

### `roadmap_risk_register_stakeholder_schedule_v0_2.md` — Project Planning
- **Milestones**: M0 (spec approved) -> M1 (dataset builder v1) -> M2 (citation resolver v1) -> M3 (baselines + eval harness) -> M4 (beta modeling)
- **Sprint plan**: 2-week sprints, 4 sprints outlined
- **Risk register**: 8 risks (PDF quality, OCR cost, API limits, label leakage, citation ambiguity, doc-type noise, licensing, sealed docs)
- **RACI-lite**: PM/RM, Data Engineering, ML Engineering, Infra/DevOps, Legal/Governance
- **Licensing**: RECAP briefs default internal-only (text); publishable artifacts are identifiers/hashes/labels only. 180-day retention for raw PDFs/text.

### `critical_evaluation_v0_2.md` — Spec Review
Self-critical evaluation identifying:
- Facts span extraction was underspecified (now addressed by facts_extraction_spec_v1)
- Citation masking scope incomplete
- Resolver confidence threshold (0.90) unvalidated
- Gold Audit Set may be too small for 10+ strata
- Schema gaps (modeling_row missing needs_ocr/document_type; cache_hit_rate misplaced)
- Sprint 1 overloaded (recommends descoping)
- Missing risks (API stability, facts accuracy plateau, bus factor, data drift)
- Cross-document inconsistencies between spec and roadmap

### `casecitationprediction_project_state.md` — Historical Project State
Snapshot from 2026-02-21 documenting the pre-packaging state: 3 Python scripts at repo root, no version control. Describes the original file names (`run_pipeline_v3_abc_v3_updated_with_ocr.py`, `pymupdf_ocr_backend_updated.py`).

### `checklist.md` — Repository Setup Checklist
62-item checklist used to professionalize the repository (version control, src layout, packaging, testing, CI, docs, data management, logging, security, code cleanup). Audit dated 2026-02-21.

---

## 8. Changelogs

Five detailed changelogs in `changelogs/` documenting the facts extractor refactor:
- **pipeline_changelog.md**: ~250 lines of facts code removed, replaced with import from facts_extractor
- **facts_extractor_changelog.md**: Documents the new 3-phase architecture, heading vocabulary expansion, soft keyword fix, quality gates, and 2 critical bugs found+fixed (roman numeral prefix consuming heading chars, max-length guardrail on short documents)
- **conftest_changelog.md**: 6 new fixtures added, documents the max-length guardrail fixture issue
- **test_facts_extractor_changelog.md**: 43 tests across 7 classes, documents 4 issues encountered during testing
- **test_pipeline_changelog.md**: 13 tests removed (moved to facts_extractor tests), 19 retained

---

## 9. Current Project Status

### What is complete (committed)
- Full pipeline: search -> download -> extract -> OCR -> facts -> output
- OCR decision standardization across modules
- Scope filtering for merits briefs
- 62 tests passing (committed state)
- CI/CD, pre-commit hooks, linting, type checking
- Professional packaging (src layout, pyproject.toml, CLI entry point)
- Comprehensive documentation (README, CONTRIBUTING, CHANGELOG, data README)

### What is in progress (uncommitted)
- **Facts extractor refactor** — extraction logic moved from pipeline.py to dedicated facts_extractor.py with major improvements:
  - 3-phase architecture (heading map -> classify+merge -> validate)
  - 13 new start headings, 10 new stop headings
  - Conditional INTRODUCTION handling per document type
  - Word-boundary enforcement for soft keywords
  - Multi-section merging (up to 4 adjacent fact-like sections)
  - 5 quality gates with composite confidence scoring
  - Min/max length guardrails
- Test suite expanded from 62 -> 92 tests
- `doc_type_id` not yet passed from main loop (defaults to UNKNOWN)

### What is not yet started (per roadmap)
- Citation extraction and normalization (M2)
- Citation resolver integration with confidence policy (M2)
- Train/eval splits with deduplication controls (M3)
- Baseline models: popularity, BM25/lexical, dense retrieval (M3)
- Evaluation harness with leakage enforcement (M3)
- Citation masking (`[CITATION]` replacement)
- Build manifest generation (`build_manifest.json`)
- Gold Audit Set tooling and first audit readout
- Stratified metric reporting

### Key Technical Decisions Made
1. **Rule-based extraction only** — No LLM in the extraction pipeline (per spec: "non-LLM steps must be deterministic")
2. **Selective OCR** — OCR only pages where native extraction fails, not whole documents
3. **Conservative scope filtering** — Only merits briefs with role keywords; excludes amicus, reply, motions
4. **PyPDF primary, PyMuPDF fallback** — With alpha-count comparison to decide which extraction is better
5. **Facts-only dataset** — Not full brief segmentation; explicitly a non-goal
6. **Phase-1 targets are judicial opinions only** — Statutes, regulations, secondary sources excluded from labels

---

## 10. Key Metrics & Numbers

| Metric | Value |
|--------|-------|
| Python version | >=3.12 |
| Package version | 0.1.0 |
| Source files | 6 (.py in src/legallm/) |
| Test files | 4 |
| Tests (current) | 92 |
| Tests (committed) | 62 |
| Downloaded PDFs | 5,644 |
| OCR .txt outputs | 1,125 |
| Recorded failures | 14 (11 no_facts_span, 3 out_of_scope) |
| Start headings | 24 exact + 1 conditional + 7 soft |
| Stop headings | 18 exact + 7 soft |
| Document type policies | 7 |
| Quality gates | 5 |
| CI matrix | Python 3.12 + 3.13 on ubuntu-latest |
| Dependencies (runtime) | 5 |
| Dependencies (dev) | 6 |

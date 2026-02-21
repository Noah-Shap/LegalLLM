# LegalLLM — Repository Setup Implementation Plan

> Reference: see `checklist.md` for the full audit of missing components.
> This document provides the ordered, step-by-step plan to execute that checklist.

---

## Phase 0: Code Cleanup (before any restructuring)

Fix issues in the existing source files so the code is clean before moving it into the package layout. All changes in this phase are to files in their **current** locations.

### Step 0.1 — Remove dead / duplicate code from pipeline

**File:** `run_pipeline_v3_abc_v3_updated_with_ocr.py`

1. **Delete the duplicate `looks_like_garbage_text()`** (lines ~540-557). This function already exists in `ocr_decision.py` and is imported via `should_ocr_document`. The pipeline's copy includes a redundant inline `import re as _re`.
2. **Delete unreachable code in `looks_like_header_only()`** (lines ~656-683). The function returns on line 654 (`return bool(needs)`); everything after is dead code from a previous implementation.
3. **Delete the trailing comment URL** on line 1002 (`#https://storage.courtlistener.com/...`).
4. **Replace hardcoded Windows paths** in `argparse` defaults:
   - `r".\data\processed\facts_dataset.parquet"` → `"data/processed/facts_dataset.parquet"`
   - `r".\data\processed\facts_failures.jsonl"` → `"data/processed/facts_failures.jsonl"`
   - `r".\data\raw\pdfs"` → `"data/raw/pdfs"`
   - `r".\data\processed\pdf_parse_warnings.log"` (line 890) → `"data/processed/pdf_parse_warnings.log"`
5. **Replace `print()` calls** with `logging.info()` / `logging.warning()` for pipeline status output (search hits count, OCR readiness, final stats). Keep `tqdm` for progress bars.

### Step 0.2 — Clean up OCR backend naming

**File:** `pymupdf_ocr_backend_updated.py`

1. No code changes needed yet — renaming happens during the move in Phase 1.

### Step 0.3 — Verify nothing is broken

Run the pipeline dry (or import-test each module) to confirm edits didn't break anything.

```bash
python -c "from ocr_decision import OcrDecisionConfig; print('OK')"
python -c "from run_pipeline_v3_abc_v3_updated_with_ocr import normalize_text; print('OK')"
```

---

## Phase 1: Project Structure & Packaging

### Step 1.1 — Create the src layout

Create the following directory structure:

```
src/
  legallm/
    __init__.py
    ocr_decision.py
    ocr_backend.py
    pipeline.py
    cli.py
```

**Actions:**

1. `mkdir -p src/legallm`
2. Move and rename files:
   - `ocr_decision.py` → `src/legallm/ocr_decision.py`
   - `pymupdf_ocr_backend_updated.py` → `src/legallm/ocr_backend.py`
   - `run_pipeline_v3_abc_v3_updated_with_ocr.py` → `src/legallm/pipeline.py`
3. Create `src/legallm/__init__.py`:
   ```python
   """LegalLLM — Legal citation prediction dataset pipeline."""

   __version__ = "0.1.0"
   ```
4. Create `src/legallm/cli.py`:
   ```python
   """CLI entry point for the LegalLLM pipeline."""

   from legallm.pipeline import main

   if __name__ == "__main__":
       main()
   ```

### Step 1.2 — Fix all imports

After moving files, update import statements:

**`src/legallm/ocr_backend.py`** (was `pymupdf_ocr_backend_updated.py`):
- Change: `from ocr_decision import ...` → `from legallm.ocr_decision import ...`

**`src/legallm/pipeline.py`** (was `run_pipeline_v3_abc_v3_updated_with_ocr.py`):
- Change: `from ocr_decision import ...` → `from legallm.ocr_decision import ...`
- Change: `from pymupdf_ocr_backend_updated import ...` → `from legallm.ocr_backend import ...`
- Change the fallback `from pymupdf_ocr_backend import ...` → remove entirely (legacy compat not needed in packaged form)

### Step 1.3 — Create `pyproject.toml`

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "legallm"
version = "0.1.0"
description = "Benchmark-grade legal facts dataset pipeline for citation prediction research"
readme = "README.md"
license = { text = "MIT" }
requires-python = ">=3.12"
authors = [
    { name = "Noah M" },
]
dependencies = [
    "requests>=2.31",
    "pandas>=2.1",
    "pypdf>=4.0",
    "PyMuPDF>=1.24",
    "tqdm>=4.66",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-cov>=5.0",
    "ruff>=0.5",
    "mypy>=1.10",
    "pre-commit>=3.7",
]

[project.scripts]
legallm = "legallm.cli:main"

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-v --tb=short"

[tool.ruff]
target-version = "py312"
line-length = 120
src = ["src"]

[tool.ruff.lint]
select = ["E", "F", "W", "I", "UP", "B", "SIM"]

[tool.ruff.lint.isort]
known-first-party = ["legallm"]

[tool.mypy]
python_version = "3.12"
warn_return_any = true
warn_unused_configs = true
ignore_missing_imports = true
```

### Step 1.4 — Create dependency files

**`requirements.txt`** (production):
```
requests>=2.31
pandas>=2.1
pypdf>=4.0
PyMuPDF>=1.24
tqdm>=4.66
```

**`requirements-dev.txt`** (development):
```
-r requirements.txt
pytest>=8.0
pytest-cov>=5.0
ruff>=0.5
mypy>=1.10
pre-commit>=3.7
```

### Step 1.5 — Verify the package installs

```bash
# Create a fresh venv
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows

# Install in editable mode
pip install -e ".[dev]"

# Verify
python -c "import legallm; print(legallm.__version__)"
legallm --help  # CLI entry point should work
```

---

## Phase 2: Version Control & Git Setup

### Step 2.1 — Create `.gitignore`

```gitignore
# Python
__pycache__/
*.py[cod]
*.egg-info/
dist/
build/
.eggs/

# Virtual environments
.venv/
venv/
env/

# Data (generated, not tracked)
data/raw/
data/processed/*.parquet
data/processed/*.jsonl
data/processed/*.log
logs/

# Large files
*.pdf

# IDE
.vscode/
.idea/
*.swp
*.swo

# OS
.DS_Store
Thumbs.db

# Environment / secrets
.env
*.env

# uv
uv.lock
```

### Step 2.2 — Create `.gitkeep` files for directory structure

```bash
touch data/raw/.gitkeep
touch data/processed/.gitkeep
touch logs/.gitkeep
```

### Step 2.3 — Create `.env.example`

```env
# CourtListener API token (required)
CL_TOKEN=your_token_here

# Tesseract OCR data directory (optional, for OCR features)
TESSDATA_PREFIX=/path/to/tessdata
```

### Step 2.4 — Remove large files from repo root

- Delete (or move elsewhere) `2025.findings-acl.681.pdf` (21 MB research paper). Add a reference link in `README.md` instead.
- Delete `test.pdf` from root. If needed for tests, place a small test fixture in `tests/fixtures/`.

### Step 2.5 — Initialize git and make initial commit

```bash
git init
git add .
git commit -m "Initial commit: LegalLLM project with src layout and packaging"
```

### Step 2.6 — Create GitHub repo and push

```bash
gh repo create LegalLLM --private --source=. --push
```

---

## Phase 3: Testing

### Step 3.1 — Create test directory structure

```
tests/
  __init__.py
  conftest.py
  fixtures/
    sample_brief_text.txt
  test_ocr_decision.py
  test_pipeline.py
  test_ocr_backend.py
```

### Step 3.2 — Write `tests/conftest.py`

Shared pytest fixtures:

```python
import pytest

@pytest.fixture
def sample_brief_text():
    """A minimal mock brief with a facts section."""
    return (
        "IN THE UNITED STATES COURT OF APPEALS\n\n"
        "I. STATEMENT OF FACTS\n\n"
        "On January 1, 2024, Appellant filed a complaint alleging that "
        "Respondent violated 42 U.S.C. § 1983. The district court held a "
        "hearing on March 15, 2024. Witness testimony established that "
        "the events occurred on the premises of Respondent.\n\n"
        "II. ARGUMENT\n\n"
        "This Court should reverse because the lower court erred.\n"
    )

@pytest.fixture
def sample_pacer_stamp():
    """A PACER/ECF header stamp line."""
    return "Case 1:24-cv-00123-ABC Document 45 Filed 01/15/2024 Page 1 of 20 PageID #: 300"

@pytest.fixture
def sample_garbage_text():
    """Text that looks like broken PDF extraction."""
    return "/i255 /i128 /i064 /i032 /i255 " * 50

@pytest.fixture
def empty_text():
    return ""
```

### Step 3.3 — Write `tests/test_ocr_decision.py`

Test all public functions in `ocr_decision.py`:

| Test | What it validates |
|------|------------------|
| `test_page_text_metrics_normal_text` | Correct char count, alpha ratio, word count for normal English text |
| `test_page_text_metrics_empty` | All zeros for empty string |
| `test_page_text_metrics_garbage` | Low alpha ratio, high weird token ratio |
| `test_strip_pacer_ecf_stamps` | Stamp lines removed, body text preserved |
| `test_strip_pacer_ecf_stamps_no_stamps` | Text unchanged when no stamps present |
| `test_looks_like_garbage_true` | Returns True for PDF internal tokens |
| `test_looks_like_garbage_false` | Returns False for normal English text |
| `test_looks_like_garbage_empty` | Returns True for empty/whitespace-only text |
| `test_looks_like_stamp_only_true` | Returns True when only stamp lines present |
| `test_looks_like_stamp_only_false` | Returns False when substantial body text exists |
| `test_should_ocr_page_good_text` | Returns (False, ...) for well-extracted page |
| `test_should_ocr_page_bad_text` | Returns (True, ...) with appropriate reasons |
| `test_should_ocr_page_custom_config` | Custom thresholds change decision |
| `test_should_ocr_document_good` | Returns (False, ...) for sufficient text |
| `test_should_ocr_document_empty` | Returns (True, reasons=["no_text", ...]) |
| `test_should_ocr_document_with_page_count_override` | High chars_per_page overrides weak reasons |

### Step 3.4 — Write `tests/test_pipeline.py`

Test pure functions from `pipeline.py`:

| Test | What it validates |
|------|------------------|
| `test_normalize_text_hyphen_break` | `"exam-\nple"` → `"example"` |
| `test_normalize_text_whitespace` | Multiple spaces/newlines collapsed |
| `test_normalize_text_crlf` | `\r\n` converted to `\n` |
| `test_extract_facts_span_exact_headings` | Returns correct span for `STATEMENT OF FACTS ... ARGUMENT` |
| `test_extract_facts_span_soft_headings` | Finds facts via soft heading detection |
| `test_extract_facts_span_fallback_pre_argument` | Falls back to pre-ARGUMENT slice |
| `test_extract_facts_span_no_match` | Returns None when no facts section found |
| `test_extract_facts_span_skips_toc` | TOC entries not mistaken for section headings |
| `test_quality_flags_with_citations` | Correct cite_hits count |
| `test_quality_flags_empty` | Zero hits for empty text |
| `test_in_scope_brief_opening_brief` | Returns True for opening merits brief |
| `test_in_scope_brief_amicus` | Returns False for amicus brief |
| `test_in_scope_brief_motion` | Returns False for motion |
| `test_in_scope_brief_no_description` | Returns False when no "brief" keyword |
| `test_candidate_pdf_urls_www` | Generates both www and storage variants |
| `test_candidate_pdf_urls_storage` | Generates both storage and www variants |
| `test_candidate_pdf_urls_other` | Returns single URL for non-courtlistener URLs |

### Step 3.5 — Write `tests/test_ocr_backend.py`

Test non-OCR-dependent functions (mock PyMuPDF where needed):

| Test | What it validates |
|------|------------------|
| `test_ocr_meta_defaults` | Default dataclass values are sensible |
| `test_check_ocr_ready_no_fitz` | Returns (False, ...) when fitz is None |

### Step 3.6 — Run tests and verify

```bash
pytest tests/ -v --cov=legallm --cov-report=term-missing
```

Target: all tests pass, >80% coverage on `ocr_decision.py` and pure functions in `pipeline.py`.

---

## Phase 4: Code Quality & Linting

### Step 4.1 — Run ruff and fix issues

```bash
ruff check src/ tests/ --fix
ruff format src/ tests/
```

Review any remaining issues and fix manually. Common expected findings:
- Unused imports
- Import ordering
- Line length violations
- f-string vs `.format()` inconsistencies

### Step 4.2 — Run mypy

```bash
mypy src/legallm/
```

Address type errors. Start with `ocr_decision.py` (already well-typed) and work outward. For the pipeline and OCR backend, use `# type: ignore` sparingly for third-party library calls that lack stubs.

### Step 4.3 — Set up pre-commit

Create `.pre-commit-config.yaml`:

```yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.5.0
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format

  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.6.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-toml
      - id: check-added-large-files
        args: ['--maxkb=500']

  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.10.0
    hooks:
      - id: mypy
        additional_dependencies: []
        args: [--ignore-missing-imports]
```

Install and run:

```bash
pre-commit install
pre-commit run --all-files
```

---

## Phase 5: CI/CD

### Step 5.1 — Create GitHub Actions CI workflow

**`.github/workflows/ci.yml`**:

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.13"
      - run: pip install ruff mypy
      - run: ruff check src/ tests/
      - run: ruff format --check src/ tests/
      - run: mypy src/legallm/ --ignore-missing-imports

  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.12", "3.13"]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
      - run: pip install -e ".[dev]"
      - run: pytest tests/ -v --cov=legallm --cov-report=xml
      - uses: codecov/codecov-action@v4
        if: matrix.python-version == '3.13'
        with:
          file: ./coverage.xml
```

### Step 5.2 — (Optional) Create release workflow

**`.github/workflows/release.yml`** — triggers on `v*` tags, builds wheel, uploads as GitHub release artifact. Add this later when the project is ready for distribution.

---

## Phase 6: Documentation

### Step 6.1 — Create `README.md`

Sections to include:
1. **Title & badges** (CI status, Python version, license)
2. **Overview** — 2-3 sentences on what the project does
3. **Features** — bullet list (CourtListener search, PDF extraction, OCR fallback, facts-span extraction, quality flags)
4. **Quick start** — install, set env vars, run pipeline
5. **Usage** — CLI flags and examples
6. **Project structure** — tree diagram of `src/legallm/`
7. **Data** — output formats (parquet, jsonl), directory layout
8. **Development** — clone, install dev deps, run tests, run linter
9. **License**

### Step 6.2 — Create `CHANGELOG.md`

```markdown
# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/).

## [0.1.0] — 2026-02-21

### Added
- Initial packaged release of the LegalLLM pipeline
- `src/legallm/` package with src layout
- `ocr_decision.py` — shared OCR decision heuristics
- `ocr_backend.py` — PyMuPDF + Tesseract selective OCR
- `pipeline.py` — end-to-end CourtListener → facts dataset pipeline
- `pyproject.toml` with full project metadata
- Unit tests for OCR decision logic, text normalization, facts extraction, scope filtering
- CI/CD via GitHub Actions (lint + test)
- Pre-commit hooks (ruff, mypy, standard checks)
- README, CONTRIBUTING, and LICENSE documentation
```

### Step 6.3 — Create `CONTRIBUTING.md`

Cover:
- Prerequisites (Python 3.12+, git)
- Dev setup (`git clone`, `pip install -e ".[dev]"`, `pre-commit install`)
- Code style (ruff rules, mypy expectations)
- Testing (`pytest tests/ -v`)
- Branch naming and PR process
- Commit message conventions

### Step 6.4 — Add `LICENSE` (MIT)

Standard MIT license text with current year and author.

### Step 6.5 — Populate `CLAUDE.md`

```markdown
# CLAUDE.md — Project Context for AI Assistants

## What is this project?
LegalLLM is a data pipeline that builds a benchmark-grade dataset of "facts" sections
from U.S. court merits briefs (via CourtListener/RECAP) for legal citation prediction research.

## Key architecture
- `src/legallm/ocr_decision.py` — shared OCR heuristics (pure stdlib, no heavy deps)
- `src/legallm/ocr_backend.py` — PyMuPDF + Tesseract selective OCR
- `src/legallm/pipeline.py` — end-to-end pipeline: search → download → extract → facts-span → dataset

## Important conventions
- All OCR threshold decisions go through `ocr_decision.py` (single source of truth)
- Pipeline outputs: `facts_dataset.parquet` (successes) + `facts_failures.jsonl` (failures with diagnostics)
- Cross-platform paths: always use `pathlib.Path`, never hardcoded Windows backslashes
- Tests must pass before merging: `pytest tests/ -v`
- Lint must pass: `ruff check src/ tests/` and `ruff format --check src/ tests/`

## Environment variables
- `CL_TOKEN` — CourtListener API token (required for pipeline)
- `TESSDATA_PREFIX` — Tesseract OCR data directory (required for OCR features)
```

### Step 6.6 — Create `data/README.md`

```markdown
# Data Directory

This directory is gitignored. Data files are generated by running the pipeline.

## Structure
- `raw/pdfs/` — Downloaded PDF court filings (one per search result ID)
- `processed/facts_dataset.parquet` — Extracted facts spans + metadata + quality flags
- `processed/facts_failures.jsonl` — Per-document failure reasons + diagnostics
- `processed/pdf_parse_warnings.log` — pypdf/fitz parsing warnings

## Generating data
```bash
legallm --query "merits brief" --max_docs 100 --enable_ocr
```
```

---

## Phase 7: Final Validation

### Step 7.1 — Full test suite

```bash
pytest tests/ -v --cov=legallm --cov-report=term-missing
```

### Step 7.2 — Full lint pass

```bash
ruff check src/ tests/
ruff format --check src/ tests/
mypy src/legallm/
```

### Step 7.3 — Pre-commit on all files

```bash
pre-commit run --all-files
```

### Step 7.4 — Clean install test

```bash
# From a fresh venv
pip install -e ".[dev]"
pytest tests/ -v
legallm --help
```

### Step 7.5 — Commit, push, verify CI

```bash
git add -A
git commit -m "Complete professional repo setup: packaging, tests, CI, docs"
git push
```

Verify GitHub Actions CI passes on the push.

---

## Execution Order Summary

| Phase | Description | Estimated Effort | Depends On |
|-------|-------------|-----------------|------------|
| 0     | Code cleanup | Small | — |
| 1     | Project structure & packaging | Medium | Phase 0 |
| 2     | Git setup | Small | Phase 1 |
| 3     | Testing | Medium-Large | Phase 1 |
| 4     | Code quality & linting | Medium | Phase 1 |
| 5     | CI/CD | Small | Phases 3, 4 |
| 6     | Documentation | Medium | Phase 1 |
| 7     | Final validation | Small | All phases |

Phases 3, 4, and 6 can be worked on **in parallel** after Phase 1 is complete.

---

## Target End State

```
LegalLLM/
├── .github/
│   └── workflows/
│       └── ci.yml
├── src/
│   └── legallm/
│       ├── __init__.py
│       ├── cli.py
│       ├── ocr_decision.py
│       ├── ocr_backend.py
│       └── pipeline.py
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── fixtures/
│   ├── test_ocr_decision.py
│   ├── test_pipeline.py
│   └── test_ocr_backend.py
├── data/
│   ├── README.md
│   ├── raw/.gitkeep
│   └── processed/.gitkeep
├── .env.example
├── .gitignore
├── .pre-commit-config.yaml
├── CHANGELOG.md
├── CLAUDE.md
├── CONTRIBUTING.md
├── LICENSE
├── README.md
├── pyproject.toml
├── requirements.txt
└── requirements-dev.txt
```

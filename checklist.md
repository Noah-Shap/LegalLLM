# LegalLLM — Professional Repository Setup Checklist

> Audit date: 2026-02-21
> Current state: 3 Python scripts at repo root, no version control, no packaging, no tests, no CI/CD.

---

## 1. Version Control

- [ ] Initialize git repository (`git init`)
- [ ] Create a comprehensive `.gitignore` (Python bytecode, `.venv/`, `data/raw/`, `data/processed/`, `*.parquet`, `*.jsonl`, `*.pdf`, logs, OS files, IDE configs)
- [ ] Make initial commit with clean working tree
- [ ] Create remote repository on GitHub
- [ ] Push initial commit and set upstream

---

## 2. Project Structure (src layout)

- [ ] Create `src/legallm/` package directory
- [ ] Add `src/legallm/__init__.py` with package version
- [ ] Move `ocr_decision.py` → `src/legallm/ocr_decision.py`
- [ ] Move `pymupdf_ocr_backend_updated.py` → `src/legallm/ocr_backend.py` (clean name)
- [ ] Move `run_pipeline_v3_abc_v3_updated_with_ocr.py` → `src/legallm/pipeline.py` (clean name)
- [ ] Create `src/legallm/cli.py` to serve as the CLI entry point
- [ ] Fix all intra-package imports to use relative or `legallm.` qualified imports
- [ ] Remove hardcoded Windows-style paths (`r".\data\..."`) in favor of `Path` / CLI args with cross-platform defaults

---

## 3. Dependency & Environment Management

- [ ] Create `pyproject.toml` with:
  - `[project]` metadata (name, version, description, authors, license, Python requires, dependencies)
  - `[project.optional-dependencies]` for `dev` extras (pytest, ruff, mypy, pre-commit)
  - `[project.scripts]` console entry point (e.g. `legallm = "legallm.cli:main"`)
  - `[tool.pytest.ini_options]` configuration
  - `[tool.ruff]` linter/formatter configuration
  - `[tool.mypy]` type-checking configuration
- [ ] Create `requirements.txt` (pinned production deps for easy `pip install -r`)
- [ ] Create `requirements-dev.txt` (dev/test deps)
- [ ] Evaluate and decide on uv vs poetry vs plain pip (recommend uv for speed; add `uv.lock` if using uv)
- [ ] Delete `.venv/` from tracked files (should be gitignored, recreated locally)
- [ ] Remove `__pycache__/` from tracked files

---

## 4. Testing

- [ ] Create `tests/` directory at repo root
- [ ] Create `tests/__init__.py`
- [ ] Create `tests/conftest.py` with shared fixtures (sample texts, mock PDF paths, temp directories)
- [ ] Create `tests/test_ocr_decision.py` — unit tests for:
  - `page_text_metrics()` (known inputs → expected metrics)
  - `strip_pacer_ecf_stamps()` (stamp removal)
  - `looks_like_garbage_text()` (garbage detection edge cases)
  - `looks_like_stamp_only()` (stamp-only detection)
  - `should_ocr_page()` (page-level decisions)
  - `should_ocr_document()` (document-level decisions with/without page count)
  - `OcrDecisionConfig` custom thresholds
- [ ] Create `tests/test_pipeline.py` — unit tests for:
  - `normalize_text()` (hyphen breaks, whitespace, newlines)
  - `extract_facts_span()` (exact headings, soft headings, fallback, TOC skipping)
  - `quality_flags()` (citation + argument marker counting)
  - `in_scope_brief()` (scope filtering logic)
  - `candidate_pdf_urls()` (URL variant generation)
  - `heading_candidates()` (heading extraction)
- [ ] Create `tests/test_ocr_backend.py` — unit tests for:
  - `check_ocr_ready()` (dependency checks, mocked)
  - `OcrMeta` dataclass defaults
- [ ] Add sample test fixtures in `tests/fixtures/` (small text snippets, mock brief texts)
- [ ] Verify all tests pass with `pytest` from repo root
- [ ] Add test coverage reporting (`pytest-cov`)

---

## 5. Code Quality & Linting

- [ ] Configure `ruff` in `pyproject.toml` (linting rules, line length, import sorting)
- [ ] Configure `mypy` in `pyproject.toml` (strict mode or gradual typing)
- [ ] Create `.pre-commit-config.yaml` with hooks:
  - ruff (lint + format)
  - mypy
  - trailing-whitespace / end-of-file-fixer
  - check-yaml / check-toml
  - detect-secrets (prevent accidental API token commits)
- [ ] Run `ruff check` and `ruff format` on all source files — fix issues
- [ ] Run `mypy` and address type errors (at minimum, no errors on `ocr_decision.py`)
- [ ] Remove dead/unreachable code (e.g. `looks_like_header_only` has unreachable code after early return)

---

## 6. CI/CD (GitHub Actions)

- [ ] Create `.github/workflows/ci.yml`:
  - Trigger on push to `main` and on pull requests
  - Matrix: Python 3.12, 3.13
  - Steps: checkout → setup Python → install deps → ruff check → ruff format --check → mypy → pytest
- [ ] Create `.github/workflows/release.yml` (optional):
  - Trigger on tag push (`v*`)
  - Build wheel/sdist and publish to PyPI (or just build as artifact)
- [ ] Add status badges to README

---

## 7. Documentation

- [ ] Create `README.md` with:
  - Project title, description, and purpose
  - Quick-start / installation instructions
  - Usage examples (CLI commands for running the pipeline)
  - Environment variables (`CL_TOKEN`, `TESSDATA_PREFIX`)
  - Data directory structure explanation
  - Project architecture overview
  - Contributing section (or link to CONTRIBUTING.md)
  - License
- [ ] Create `CHANGELOG.md` with initial `v0.1.0` entry
- [ ] Create `CONTRIBUTING.md` with:
  - Dev environment setup instructions
  - Code style guidelines (ruff, mypy)
  - Testing expectations
  - PR process
- [ ] Add `LICENSE` file (recommend MIT for research projects)
- [ ] Populate `CLAUDE.md` with project context for AI-assisted development

---

## 8. Data Management

- [ ] Create `data/README.md` explaining:
  - Directory structure (`raw/pdfs/`, `processed/`)
  - How data is generated (pipeline run)
  - File formats (parquet schema, jsonl structure)
  - That data files are gitignored and must be generated locally
- [ ] Ensure all data files are properly gitignored
- [ ] Add `.gitkeep` files to `data/raw/` and `data/processed/` so directory structure is preserved in git
- [ ] Remove `2025.findings-acl.681.pdf` from repo root (21 MB research paper — store reference in README instead)
- [ ] Remove or gitignore `test.pdf` from repo root (move test fixtures to `tests/fixtures/` if needed)

---

## 9. Logging & Configuration

- [ ] Consolidate duplicate log paths (`data/processed/pdf_parse_warnings.log` vs `logs/pdf_parse_warnings.log`)
- [ ] Create a logging configuration module or use `pyproject.toml` / env-var-driven log level
- [ ] Replace `print()` statements in pipeline with proper `logging` calls

---

## 10. Security & Secrets

- [ ] Ensure `CL_TOKEN` is only read from env vars (already the case — good)
- [ ] Add `.env.example` showing required environment variables (without real values)
- [ ] Confirm `.env` is in `.gitignore`

---

## 11. Code Cleanup (Pre-Migration)

- [ ] Remove duplicate `looks_like_garbage_text()` in pipeline (already in `ocr_decision.py`)
- [ ] Remove unreachable code in `looks_like_header_only()` (lines after `return bool(needs)`)
- [ ] Remove inline `import re as _re` inside function body (pipeline line 551)
- [ ] Standardize all path handling to use `pathlib.Path` consistently
- [ ] Remove trailing comment URL at end of pipeline file (line 1002)

---

## Summary

| Category                  | Items | Priority |
|---------------------------|-------|----------|
| Version Control           | 5     | P0       |
| Project Structure         | 8     | P0       |
| Dependency Management     | 6     | P0       |
| Testing                   | 11    | P1       |
| Code Quality & Linting    | 7     | P1       |
| CI/CD                     | 3     | P1       |
| Documentation             | 6     | P1       |
| Data Management           | 5     | P2       |
| Logging & Configuration   | 3     | P2       |
| Security & Secrets        | 3     | P2       |
| Code Cleanup              | 5     | P0       |

**P0** = Must be done first (foundational)
**P1** = Should follow immediately (quality & safety)
**P2** = Important but can be done incrementally

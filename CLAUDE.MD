# CLAUDE.md - Project Context for AI Assistants

## What is this project?

LegalLLM is a data pipeline that builds a benchmark-grade dataset of "facts" sections
extracted from U.S. court merits briefs (via CourtListener/RECAP) for legal citation
prediction research.

## Key architecture

- `src/legallm/ocr_decision.py` - shared OCR heuristics (pure stdlib, no heavy deps).
  Single source of truth for all OCR threshold decisions.
- `src/legallm/ocr_backend.py` - PyMuPDF + Tesseract selective OCR. Only OCRs pages
  where native extraction is insufficient.
- `src/legallm/pipeline.py` - end-to-end pipeline: CourtListener search, PDF download,
  text extraction (pypdf -> PyMuPDF -> OCR), facts-span detection, dataset output.
- `src/legallm/cli.py` - CLI entry point that delegates to `pipeline.main()`.

## Important conventions

- All OCR threshold decisions go through `ocr_decision.py` (never duplicate the logic).
- Pipeline outputs: `facts_dataset.parquet` (successes) + `facts_failures.jsonl` (failures with diagnostics).
- Cross-platform paths: always use `pathlib.Path`, never hardcoded Windows backslashes.
- Tests must pass before merging: `pytest tests/ -v` (62 tests).
- Lint must pass: `ruff check src/ tests/` and `ruff format --check src/ tests/`.
- Package uses src layout: all code lives under `src/legallm/`.

## Environment variables

- `CL_TOKEN` - CourtListener API token (required for pipeline runs).
- `TESSDATA_PREFIX` - Tesseract OCR data directory (required for OCR features).

## Commands

- `pytest tests/ -v` - run tests
- `ruff check src/ tests/ --fix` - lint with autofix
- `ruff format src/ tests/` - format code
- `mypy src/legallm/` - type check
- `pip install -e ".[dev]"` - install in editable mode with dev deps
- `legallm --help` - CLI usage

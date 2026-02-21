# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/).

## [0.1.0] - 2026-02-21

### Added
- Initial packaged release of the LegalLLM pipeline.
- `src/legallm/` package with src layout.
- `ocr_decision.py` - shared OCR decision heuristics for court filings.
- `ocr_backend.py` - PyMuPDF + Tesseract selective page-level OCR.
- `pipeline.py` - end-to-end CourtListener search, download, extract, facts-span pipeline.
- `pyproject.toml` with full project metadata and tool configuration.
- Unit tests for OCR decision logic, text normalization, facts extraction, and scope filtering (62 tests).
- CI/CD via GitHub Actions (lint + test matrix on Python 3.12/3.13).
- Pre-commit hooks (ruff, mypy, standard checks).
- README, CONTRIBUTING, CHANGELOG, and LICENSE documentation.

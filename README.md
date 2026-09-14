# LegalLLM

[![CI](https://github.com/Noah-Shap/LegalLLM/actions/workflows/ci.yml/badge.svg)](https://github.com/Noah-Shap/LegalLLM/actions/workflows/ci.yml)
[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Benchmark-grade legal facts dataset pipeline for citation prediction research.

**Status (2026-09-14):** rule-based v0 (CourtListener/RECAP → PDF → text/OCR → rule-based facts span → citation targets → retrieval baselines) → **LLM extraction app + eval loop in progress**.

**Canonical build (D12):** Phase 1 uses `data/processed/facts_dataset_2k.parquet`, build `46864ffb7283` (1,599 spans). The April 2026 retrieval reports in `reports/m4_*` were computed on an earlier, overwritten 2k build (`38a720b3324a`, 1,819 spans); numbers there are not directly comparable to the on-disk parquet.

Start here: [`STATE.md`](STATE.md) (measured inventory of the current repo), [`GAP.md`](GAP.md) (target vs. existing components), [`docs/intent.md`](docs/intent.md) (target state for the LLM app).

Extracts "Statement of Facts" sections from U.S. court merits briefs sourced via [CourtListener](https://www.courtlistener.com/)/RECAP, producing structured datasets for legal citation prediction experiments.

## Features

- **CourtListener API integration** - searches RECAP documents with paginated result handling
- **Multi-strategy PDF acquisition** - resolves PDF URLs via `filepath_local`, direct fields, or webpage scraping
- **Robust text extraction** - pypdf primary, PyMuPDF fallback, with intelligent quality comparison
- **Selective OCR** - page-level OCR via PyMuPDF + Tesseract only where native extraction fails
- **Rule-based facts extraction** - 3-tier heading detection (exact, soft, fallback) with TOC skipping
- **Scope filtering** - focuses on merits briefs, excludes motions, amicus, and administrative filings
- **Quality flags** - citation density and argument marker metrics per extracted span
- **Structured diagnostics** - detailed failure logs (JSONL) for iterative pipeline improvement

## Quick Start

```bash
# Install
pip install -e ".[dev]"

# Set your CourtListener API token
export CL_TOKEN=your_courtlistener_api_token

# Run the pipeline
legallm --query "merits brief" --max_docs 100
```

## Usage

```bash
# Basic run
legallm --query "patent infringement" --max_docs 500

# With OCR enabled
legallm --query "merits brief" --max_docs 200 --enable_ocr --tessdata /path/to/tessdata

# Custom output paths
legallm --query "merits brief" --out_parquet output/facts.parquet --failures_jsonl output/failures.jsonl
```

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `CL_TOKEN` | Yes | CourtListener API authentication token |
| `TESSDATA_PREFIX` | For OCR | Path to Tesseract tessdata directory |

## Project Structure

```
src/legallm/
  __init__.py          # Package init with version
  cli.py               # CLI entry point
  ocr_decision.py      # Shared OCR decision heuristics
  ocr_backend.py       # PyMuPDF + Tesseract selective OCR
  pipeline.py          # End-to-end extraction pipeline
tests/
  conftest.py          # Shared test fixtures
  test_ocr_decision.py # OCR decision logic tests
  test_pipeline.py     # Pipeline function tests
  test_ocr_backend.py  # OCR backend tests
```

## Output Data

- **`facts_dataset.parquet`** - extracted facts spans with metadata and quality flags
- **`facts_failures.jsonl`** - per-document failure reasons with diagnostics

See [data/README.md](data/README.md) for full schema details.

## Development

```bash
# Clone and install
git clone https://github.com/Noah-Shap/LegalLLM.git
cd LegalLLM
pip install -e ".[dev]"
pre-commit install

# Run tests
pytest tests/ -v

# Lint and format
ruff check src/ tests/
ruff format src/ tests/

# Type check
mypy src/legallm/
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for full development guidelines.

## License

[MIT](LICENSE)

# Contributing to LegalLLM

## Development Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/<your-username>/LegalLLM.git
   cd LegalLLM
   ```

2. Create a virtual environment and install dependencies:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # or .venv\Scripts\activate on Windows
   pip install -e ".[dev]"
   ```

3. Install pre-commit hooks:
   ```bash
   pre-commit install
   ```

4. Set up environment variables:
   ```bash
   cp .env.example .env
   # Edit .env with your CourtListener API token
   ```

## Code Style

- **Linter/Formatter**: [Ruff](https://docs.astral.sh/ruff/) (configured in `pyproject.toml`)
- **Type checking**: [mypy](https://mypy-lang.org/) with `--ignore-missing-imports`
- **Line length**: 120 characters
- **Python version**: 3.12+

Run checks locally:
```bash
ruff check src/ tests/
ruff format src/ tests/
mypy src/legallm/
```

## Testing

All changes should include tests. Run the test suite with:
```bash
pytest tests/ -v
```

For coverage reporting:
```bash
pytest tests/ -v --cov=legallm --cov-report=term-missing
```

## Pull Request Process

1. Create a feature branch from `main`.
2. Make your changes and add tests.
3. Ensure all checks pass: `ruff check`, `ruff format --check`, `mypy`, `pytest`.
4. Open a PR with a clear description of the changes.
5. CI will run automatically on the PR.

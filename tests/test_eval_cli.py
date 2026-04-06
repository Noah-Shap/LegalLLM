"""Tests for legallm.eval_cli module."""

import json

import pandas as pd
import pytest

from legallm.eval_cli import main


@pytest.fixture
def synthetic_parquet(tmp_path):
    """Create a synthetic parquet file for CLI smoke testing."""
    rows = []
    for i in range(30):
        n_targets = (i % 5) + 1
        targets = [str(1000 + j + (i * 3)) for j in range(n_targets)]
        rows.append(
            {
                "search_result_id": i,
                "build_id": "test_build",
                "facts_text": f"The plaintiff in case {i} filed a complaint. " * 20,
                "facts_text_masked": f"The plaintiff in case {i} filed a complaint [CITATION]. " * 20,
                "targets_case_ids": json.dumps(targets),
                "doc_type_id": "UNKNOWN",
                "document_type": "PACER Document",
                "resolved_citation_count": n_targets,
            }
        )
    path = tmp_path / "test.parquet"
    pd.DataFrame(rows).to_parquet(path)
    return path


class TestEvalCLI:
    def test_smoke_popularity_only(self, synthetic_parquet, capsys):
        main(["--parquet", str(synthetic_parquet), "--baselines", "popularity", "--skip-leakage-check"])
        captured = capsys.readouterr()
        assert "popularity" in captured.out.lower()
        assert "Recall@K" in captured.out

    def test_smoke_bm25(self, synthetic_parquet, capsys):
        main(["--parquet", str(synthetic_parquet), "--baselines", "bm25", "--skip-leakage-check"])
        captured = capsys.readouterr()
        assert "bm25" in captured.out.lower()

    def test_report_output_file(self, synthetic_parquet, tmp_path):
        report_path = tmp_path / "report.md"
        main(
            [
                "--parquet",
                str(synthetic_parquet),
                "--baselines",
                "popularity",
                "--report-out",
                str(report_path),
                "--skip-leakage-check",
            ]
        )
        assert report_path.exists()
        content = report_path.read_text()
        assert "Evaluation Report" in content

    def test_empty_dataset_handled(self, tmp_path, capsys):
        # All rows have empty targets
        rows = [
            {
                "search_result_id": 1,
                "build_id": "b",
                "facts_text_masked": "text",
                "targets_case_ids": "[]",
            }
        ]
        path = tmp_path / "empty_targets.parquet"
        pd.DataFrame(rows).to_parquet(path)
        main(["--parquet", str(path), "--baselines", "popularity"])
        captured = capsys.readouterr()
        assert "No rows" in captured.out

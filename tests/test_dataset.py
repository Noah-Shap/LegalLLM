"""Tests for legallm.dataset module."""

import json

import pandas as pd
import pytest

from legallm.dataset import (
    deduplicate,
    fuzzy_text_hash,
    generate_row_id,
    label_cardinality_bin,
    load_dataset,
    split_dataset,
)


@pytest.fixture
def sample_df():
    """A minimal DataFrame mimicking pipeline parquet output with resolved targets."""
    rows = []
    for i in range(20):
        n_targets = (i % 10) + 1
        targets = [str(1000 + j) for j in range(n_targets)]
        rows.append(
            {
                "search_result_id": i,
                "build_id": "abc123",
                "facts_text": f"Facts for document {i}. " * 50,
                "facts_text_masked": f"Facts for document {i} with [CITATION] masked. " * 50,
                "targets_case_ids": json.dumps(targets),
                "doc_type_id": "UNKNOWN",
                "document_type": "PACER Document",
                "resolved_citation_count": n_targets,
            }
        )
    return pd.DataFrame(rows)


class TestGenerateRowId:
    def test_deterministic(self):
        id1 = generate_row_id(123, "build1", "some text")
        id2 = generate_row_id(123, "build1", "some text")
        assert id1 == id2

    def test_different_inputs_different_ids(self):
        id1 = generate_row_id(123, "build1", "text1")
        id2 = generate_row_id(456, "build1", "text1")
        assert id1 != id2

    def test_length(self):
        rid = generate_row_id(1, "b", "t")
        assert len(rid) == 16
        assert all(c in "0123456789abcdef" for c in rid)


class TestFuzzyTextHash:
    def test_identical_texts(self):
        assert fuzzy_text_hash("hello world test") == fuzzy_text_hash("hello world test")

    def test_very_different_texts(self):
        h1 = fuzzy_text_hash("the quick brown fox jumps over the lazy dog" * 10)
        h2 = fuzzy_text_hash("completely unrelated text about legal proceedings" * 10)
        # Different texts should (very likely) have different hashes
        assert h1 != h2

    def test_empty(self):
        h = fuzzy_text_hash("")
        assert len(h) == 16


class TestDeduplicate:
    def test_removes_exact_dupes(self, sample_df):
        df = pd.concat([sample_df, sample_df.iloc[:3]]).reset_index(drop=True)
        df["targets"] = df["targets_case_ids"].apply(json.loads)
        result = deduplicate(df)
        assert len(result) <= len(sample_df)

    def test_keeps_row_with_more_targets(self):
        df = pd.DataFrame(
            {
                "search_result_id": [1, 1],
                "facts_text_masked": ["same text", "same text"],
                "targets": [["a"], ["a", "b", "c"]],
            }
        )
        result = deduplicate(df)
        assert len(result) == 1
        assert len(result.iloc[0]["targets"]) == 3

    def test_empty_df(self):
        df = pd.DataFrame(columns=["search_result_id", "facts_text_masked", "targets"])
        result = deduplicate(df)
        assert result.empty


class TestLabelCardinalityBin:
    def test_bins(self):
        assert label_cardinality_bin(0) == "1"
        assert label_cardinality_bin(1) == "1"
        assert label_cardinality_bin(2) == "2-3"
        assert label_cardinality_bin(3) == "2-3"
        assert label_cardinality_bin(4) == "4-7"
        assert label_cardinality_bin(7) == "4-7"
        assert label_cardinality_bin(8) == "8+"
        assert label_cardinality_bin(30) == "8+"


class TestSplitDataset:
    def test_all_rows_assigned(self, sample_df):
        sample_df["targets"] = sample_df["targets_case_ids"].apply(json.loads)
        result = split_dataset(sample_df)
        assert all(result["split"].isin(["train", "val", "test"]))
        assert len(result) == len(sample_df)

    def test_reproducible(self, sample_df):
        sample_df["targets"] = sample_df["targets_case_ids"].apply(json.loads)
        r1 = split_dataset(sample_df, seed=42)
        r2 = split_dataset(sample_df, seed=42)
        assert list(r1["split"]) == list(r2["split"])

    def test_different_seeds_different_splits(self, sample_df):
        sample_df["targets"] = sample_df["targets_case_ids"].apply(json.loads)
        r1 = split_dataset(sample_df, seed=42)
        r2 = split_dataset(sample_df, seed=99)
        assert list(r1["split"]) != list(r2["split"])

    def test_proportions_reasonable(self, sample_df):
        sample_df["targets"] = sample_df["targets_case_ids"].apply(json.loads)
        result = split_dataset(sample_df)
        counts = result["split"].value_counts()
        assert counts.get("train", 0) >= len(sample_df) * 0.5


class TestLoadDataset:
    def test_filters_empty_targets(self, sample_df, tmp_path):
        # Add rows with empty targets
        extra = pd.DataFrame(
            [
                {
                    "search_result_id": 100,
                    "build_id": "abc123",
                    "facts_text": "no targets",
                    "facts_text_masked": "no targets",
                    "targets_case_ids": "[]",
                    "doc_type_id": "UNKNOWN",
                    "document_type": "PACER Document",
                    "resolved_citation_count": 0,
                }
            ]
        )
        full = pd.concat([sample_df, extra]).reset_index(drop=True)
        path = tmp_path / "test.parquet"
        full.to_parquet(path)

        result = load_dataset(path, min_targets=1)
        assert len(result) <= len(sample_df)
        assert all(result["label_cardinality"] >= 1)

    def test_has_required_columns(self, sample_df, tmp_path):
        path = tmp_path / "test.parquet"
        sample_df.to_parquet(path)

        result = load_dataset(path)
        assert "row_id" in result.columns
        assert "targets" in result.columns
        assert "label_cardinality" in result.columns
        assert "label_cardinality_bin" in result.columns
        assert "split" in result.columns

    def test_empty_dataset(self, tmp_path):
        df = pd.DataFrame(
            {
                "search_result_id": [],
                "build_id": [],
                "facts_text_masked": [],
                "targets_case_ids": [],
            }
        )
        path = tmp_path / "empty.parquet"
        df.to_parquet(path)

        result = load_dataset(path)
        assert result.empty

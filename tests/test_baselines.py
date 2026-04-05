"""Tests for legallm.baselines module."""

import numpy as np
import pandas as pd
import pytest

from legallm.baselines import (
    BM25Baseline,
    PopularityBaseline,
    RetrievalResult,
    aggregate_case_ids,
)


@pytest.fixture
def train_df():
    """Synthetic training DataFrame with known targets."""
    rows = [
        {
            "row_id": "r0",
            "facts_text_masked": "The plaintiff filed a complaint alleging breach of contract [CITATION].",
            "targets": ["case_100", "case_200"],
        },
        {
            "row_id": "r1",
            "facts_text_masked": "The defendant moved to dismiss the breach of contract claim [CITATION].",
            "targets": ["case_100", "case_300"],
        },
        {
            "row_id": "r2",
            "facts_text_masked": "Patent infringement action regarding semiconductor technology [CITATION].",
            "targets": ["case_400", "case_500"],
        },
        {
            "row_id": "r3",
            "facts_text_masked": "Employment discrimination under Title VII of the Civil Rights Act [CITATION].",
            "targets": ["case_600"],
        },
        {
            "row_id": "r4",
            "facts_text_masked": "Securities fraud class action involving material misstatements [CITATION].",
            "targets": ["case_200", "case_700"],
        },
    ]
    return pd.DataFrame(rows)


@pytest.fixture
def test_df():
    """Synthetic test DataFrame."""
    return pd.DataFrame(
        [
            {
                "row_id": "t0",
                "facts_text_masked": "Breach of contract dispute regarding employment agreement [CITATION].",
                "targets": ["case_100", "case_300"],
            },
            {
                "row_id": "t1",
                "facts_text_masked": "Patent infringement claim for software methods [CITATION].",
                "targets": ["case_400"],
            },
        ]
    )


# ============================================================================
# aggregate_case_ids
# ============================================================================


class TestAggregateCaseIds:
    def test_basic_aggregation(self):
        sim_scores = np.array([0.9, 0.5, 0.1])
        train_targets = [["a", "b"], ["b", "c"], ["d"]]
        ids, scores = aggregate_case_ids(sim_scores, train_targets, k=3, n_retrieve=3)
        # "b" appears in rows 0 (0.9) and 1 (0.5) = 1.4 total
        # "a" appears in row 0 (0.9) = 0.9
        # "c" appears in row 1 (0.5) = 0.5
        assert ids[0] == "b"  # highest score
        assert len(ids) <= 3

    def test_k_truncation(self):
        sim_scores = np.array([1.0, 0.5])
        train_targets = [["a", "b", "c"], ["d", "e"]]
        ids, scores = aggregate_case_ids(sim_scores, train_targets, k=2, n_retrieve=2)
        assert len(ids) == 2

    def test_empty_scores(self):
        sim_scores = np.array([])
        train_targets = []
        ids, scores = aggregate_case_ids(sim_scores, train_targets, k=5, n_retrieve=5)
        assert ids == []

    def test_zero_scores_ignored(self):
        sim_scores = np.array([0.0, 0.0])
        train_targets = [["a"], ["b"]]
        ids, scores = aggregate_case_ids(sim_scores, train_targets, k=5, n_retrieve=2)
        assert ids == []


# ============================================================================
# PopularityBaseline
# ============================================================================


class TestPopularityBaseline:
    def test_fit_counts_frequencies(self, train_df):
        model = PopularityBaseline()
        model.fit(train_df)
        # case_100 appears in r0 and r1 = 2 times
        # case_200 appears in r0 and r4 = 2 times
        assert model._ranked_ids[0] in ("case_100", "case_200")

    def test_predict_same_for_all(self, train_df, test_df):
        model = PopularityBaseline()
        model.fit(train_df)
        results = model.predict(test_df, k=3)
        assert len(results) == 2
        assert results[0].ranked_ids == results[1].ranked_ids

    def test_predict_returns_retrieval_results(self, train_df, test_df):
        model = PopularityBaseline()
        model.fit(train_df)
        results = model.predict(test_df, k=5)
        for r in results:
            assert isinstance(r, RetrievalResult)
            assert len(r.ranked_ids) <= 5


# ============================================================================
# BM25Baseline
# ============================================================================


class TestBM25Baseline:
    def test_fit_predict(self, train_df, test_df):
        model = BM25Baseline(max_features=100, n_retrieve=3)
        model.fit(train_df)
        results = model.predict(test_df, k=5)
        assert len(results) == 2
        for r in results:
            assert isinstance(r, RetrievalResult)

    def test_similar_query_retrieves_relevant(self, train_df):
        model = BM25Baseline(max_features=100, n_retrieve=3)
        model.fit(train_df)

        # Query very similar to r0 (breach of contract)
        query_df = pd.DataFrame(
            [
                {
                    "row_id": "q0",
                    "facts_text_masked": "The plaintiff alleged breach of contract [CITATION].",
                    "targets": ["case_100"],
                }
            ]
        )
        results = model.predict(query_df, k=10)
        # case_100 should appear in results since r0 and r1 (which cite case_100) are similar
        assert "case_100" in results[0].ranked_ids

    def test_predict_before_fit_raises(self):
        model = BM25Baseline()
        with pytest.raises(RuntimeError):
            model.predict(pd.DataFrame([{"row_id": "x", "facts_text_masked": "text"}]), k=5)

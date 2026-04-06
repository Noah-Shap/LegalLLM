"""Tests for legallm.eval_harness module."""

import math

import pandas as pd
import pytest

from legallm.baselines import RetrievalResult
from legallm.eval_harness import (
    AggregateMetrics,
    MetricsResult,
    evaluate,
    format_report,
    leakage_check,
    mrr_at_k,
    ndcg_at_k,
    popularity_dominance_check,
    recall_at_k,
    stratified_report,
)

# ============================================================================
# Core metrics
# ============================================================================


class TestRecallAtK:
    def test_all_found(self):
        assert recall_at_k(["a", "b", "c"], {"a", "b"}, 3) == 1.0

    def test_partial(self):
        assert recall_at_k(["a", "x", "y"], {"a", "b"}, 3) == 0.5

    def test_none_found(self):
        assert recall_at_k(["x", "y", "z"], {"a", "b"}, 3) == 0.0

    def test_empty_true_ids(self):
        assert recall_at_k(["a", "b"], set(), 3) == 0.0

    def test_k_truncates(self):
        # "b" is at position 2 (0-indexed), k=1 should miss it
        assert recall_at_k(["x", "b"], {"b"}, 1) == 0.0
        assert recall_at_k(["x", "b"], {"b"}, 2) == 1.0


class TestMrrAtK:
    def test_first_position(self):
        assert mrr_at_k(["a", "b", "c"], {"a"}, 3) == 1.0

    def test_third_position(self):
        assert mrr_at_k(["x", "y", "a"], {"a"}, 3) == pytest.approx(1 / 3)

    def test_no_hit(self):
        assert mrr_at_k(["x", "y", "z"], {"a"}, 3) == 0.0

    def test_empty_true_ids(self):
        assert mrr_at_k(["a"], set(), 3) == 0.0


class TestNdcgAtK:
    def test_perfect_ranking(self):
        # All 2 relevant at positions 0, 1
        assert ndcg_at_k(["a", "b", "x"], {"a", "b"}, 3) == 1.0

    def test_no_relevant(self):
        assert ndcg_at_k(["x", "y", "z"], {"a"}, 3) == 0.0

    def test_empty_true_ids(self):
        assert ndcg_at_k(["a", "b"], set(), 3) == 0.0

    def test_single_relevant_at_position_2(self):
        # DCG = 1/log2(3) = 0.630, IDCG = 1/log2(2) = 1.0
        result = ndcg_at_k(["x", "a"], {"a"}, 2)
        expected = (1.0 / math.log2(3)) / (1.0 / math.log2(2))
        assert result == pytest.approx(expected)


# ============================================================================
# Evaluate
# ============================================================================


class TestEvaluate:
    def test_basic_evaluation(self):
        df = pd.DataFrame(
            {
                "row_id": ["r1", "r2"],
                "targets": [["a", "b"], ["c"]],
                "label_cardinality": [2, 1],
                "label_cardinality_bin": ["2-3", "1"],
                "doc_type_id": ["UNKNOWN", "UNKNOWN"],
            }
        )
        results = [
            RetrievalResult(query_row_id="r1", ranked_ids=["a", "x", "b"], scores=[1.0, 0.5, 0.3]),
            RetrievalResult(query_row_id="r2", ranked_ids=["y", "c"], scores=[1.0, 0.5]),
        ]
        metrics = evaluate(results, df, ks=[1, 3])
        assert metrics.n_queries == 2
        assert 1 in metrics.mean_recall
        assert 3 in metrics.mean_recall

    def test_empty_results(self):
        df = pd.DataFrame(columns=["row_id", "targets", "label_cardinality", "label_cardinality_bin", "doc_type_id"])
        metrics = evaluate([], df)
        assert metrics.n_queries == 0


# ============================================================================
# Stratified report
# ============================================================================


class TestStratifiedReport:
    def test_groups_by_bin(self):
        m1 = MetricsResult(row_id="r1", recall={10: 0.5}, mrr={10: 0.5}, ndcg={10: 0.5}, label_cardinality_bin="1")
        m2 = MetricsResult(row_id="r2", recall={10: 1.0}, mrr={10: 1.0}, ndcg={10: 1.0}, label_cardinality_bin="8+")
        agg = AggregateMetrics(n_queries=2, per_query=[m1, m2])

        report = stratified_report(agg, stratify_by=["label_cardinality_bin"])
        assert "label_cardinality_bin" in report
        assert "1" in report["label_cardinality_bin"]
        assert "8+" in report["label_cardinality_bin"]
        assert report["label_cardinality_bin"]["1"].mean_recall[10] == 0.5
        assert report["label_cardinality_bin"]["8+"].mean_recall[10] == 1.0


# ============================================================================
# Leakage check
# ============================================================================


class TestLeakageCheck:
    def test_clean_text_passes(self):
        df = pd.DataFrame(
            {
                "row_id": ["r1"],
                "facts_text_masked": ["The court found [CITATION] that the standard applies."],
            }
        )
        result = leakage_check(df)
        assert result == []

    def test_leaked_citation_detected(self):
        df = pd.DataFrame(
            {
                "row_id": ["r1"],
                "facts_text_masked": ["The court in 500 U.S. 100 found that the standard applies."],
            }
        )
        with pytest.raises(AssertionError, match="leakage"):
            leakage_check(df)


# ============================================================================
# Popularity dominance check
# ============================================================================


class TestPopularityDominanceCheck:
    def test_beats_popularity(self):
        model = AggregateMetrics(mean_recall={10: 0.15})
        pop = AggregateMetrics(mean_recall={10: 0.10})
        result = popularity_dominance_check(model, pop)
        assert result["beats_popularity"] is True
        assert result["relative_improvement"] > 0

    def test_does_not_beat(self):
        model = AggregateMetrics(mean_recall={10: 0.05})
        pop = AggregateMetrics(mean_recall={10: 0.10})
        result = popularity_dominance_check(model, pop)
        assert result["beats_popularity"] is False


# ============================================================================
# Report formatting
# ============================================================================


class TestAnalyzeErrors:
    def test_basic_analysis(self):
        from legallm.eval_harness import analyze_errors

        df = pd.DataFrame(
            {
                "row_id": ["r1", "r2"],
                "targets": [["a", "b"], ["c"]],
                "label_cardinality_bin": ["2-3", "1"],
            }
        )
        results = [
            RetrievalResult(query_row_id="r1", ranked_ids=["a", "x"], scores=[1.0, 0.5]),
            RetrievalResult(query_row_id="r2", ranked_ids=["x", "y"], scores=[1.0, 0.5]),
        ]
        analysis = analyze_errors(results, df, k=10)
        assert analysis["total_queries"] == 2
        assert analysis["zero_hit_queries"] == 1  # r2 has no hits
        assert analysis["total_hits_in_top_k"] == 1  # only "a" found for r1

    def test_hardest_targets(self):
        from legallm.eval_harness import analyze_errors

        df = pd.DataFrame(
            {
                "row_id": ["r1", "r2", "r3"],
                "targets": [["hard_case"], ["hard_case"], ["easy_case"]],
                "label_cardinality_bin": ["1", "1", "1"],
            }
        )
        results = [
            RetrievalResult(query_row_id="r1", ranked_ids=["x"], scores=[1.0]),
            RetrievalResult(query_row_id="r2", ranked_ids=["x"], scores=[1.0]),
            RetrievalResult(query_row_id="r3", ranked_ids=["easy_case"], scores=[1.0]),
        ]
        analysis = analyze_errors(results, df, k=10)
        # hard_case missed 2/2 times
        assert any(t[0] == "hard_case" for t in analysis["hardest_targets"])


class TestCompareModels:
    def test_comparison(self):
        from legallm.eval_harness import compare_models

        df = pd.DataFrame(
            {
                "row_id": ["r1", "r2"],
                "targets": [["a"], ["b"]],
            }
        )
        results_a = [
            RetrievalResult(query_row_id="r1", ranked_ids=["a"], scores=[1.0]),
            RetrievalResult(query_row_id="r2", ranked_ids=["x"], scores=[1.0]),
        ]
        results_b = [
            RetrievalResult(query_row_id="r1", ranked_ids=["x"], scores=[1.0]),
            RetrievalResult(query_row_id="r2", ranked_ids=["b"], scores=[1.0]),
        ]
        comp = compare_models(results_a, results_b, df, "A", "B", k=10)
        assert comp["a_wins"] == 1
        assert comp["b_wins"] == 1
        assert comp["ties"] == 0


class TestCostReport:
    def test_generates_report(self, tmp_path):
        import json

        from legallm.eval_harness import generate_cost_report

        manifest = {
            "build_id": "test123",
            "timestamp_utc": "2026-01-01T00:00:00",
            "parameters": {"resolver_budget_per_build": 10000},
            "results_summary": {
                "total_hits": 500,
                "extracted_spans": 450,
                "failures": 50,
                "resolver_enabled": True,
                "resolver_api_calls": 3000,
                "resolver_cache_entries": 5000,
                "resolver_cache_hit_rate": 0.4,
            },
        }
        path = tmp_path / "manifest.json"
        path.write_text(json.dumps(manifest))
        report = generate_cost_report(str(path))
        assert "Budget" in report
        assert "3000" in report


class TestFormatReport:
    def test_produces_markdown(self):
        agg = AggregateMetrics(
            n_queries=10,
            mean_recall={10: 0.15},
            mean_mrr={10: 0.08},
            mean_ndcg={10: 0.12},
        )
        report = format_report("BM25", agg)
        assert "BM25" in report
        assert "Recall@K" in report
        assert "0.1500" in report

"""Evaluation harness: retrieval metrics, leakage checks, stratified reporting.

Computes Recall@K, MRR@K, nDCG@K for retrieval baseline results.
Enforces leakage controls and produces stratified metric reports.

Reference: approved_spec_package_v0_2.md §Success metrics + acceptance thresholds
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from legallm.citation_extractor import RE_FULL_CASE_CITE

# ---------------------------------------------------------------------------
# Core metrics
# ---------------------------------------------------------------------------


def recall_at_k(ranked_ids: list[str], true_ids: set[str], k: int) -> float:
    """Fraction of true_ids found in ranked_ids[:k]."""
    if not true_ids:
        return 0.0
    hits = sum(1 for rid in ranked_ids[:k] if rid in true_ids)
    return hits / len(true_ids)


def mrr_at_k(ranked_ids: list[str], true_ids: set[str], k: int) -> float:
    """Reciprocal rank of the first hit in ranked_ids[:k]."""
    for i, rid in enumerate(ranked_ids[:k]):
        if rid in true_ids:
            return 1.0 / (i + 1)
    return 0.0


def ndcg_at_k(ranked_ids: list[str], true_ids: set[str], k: int) -> float:
    """Normalized discounted cumulative gain at k (binary relevance)."""
    if not true_ids:
        return 0.0

    # DCG
    dcg = 0.0
    for i, rid in enumerate(ranked_ids[:k]):
        if rid in true_ids:
            dcg += 1.0 / math.log2(i + 2)  # i+2 because log2(1) = 0

    # Ideal DCG (all relevant items at the top)
    ideal_k = min(len(true_ids), k)
    idcg = sum(1.0 / math.log2(i + 2) for i in range(ideal_k))

    return dcg / idcg if idcg > 0 else 0.0


# ---------------------------------------------------------------------------
# Result dataclasses
# ---------------------------------------------------------------------------


@dataclass
class MetricsResult:
    """Metrics for a single query."""

    row_id: str
    recall: dict[int, float] = field(default_factory=dict)
    mrr: dict[int, float] = field(default_factory=dict)
    ndcg: dict[int, float] = field(default_factory=dict)
    label_cardinality: int = 0
    label_cardinality_bin: str = ""
    doc_type_id: str | None = None


@dataclass
class AggregateMetrics:
    """Aggregated metrics across a set of queries."""

    n_queries: int = 0
    mean_recall: dict[int, float] = field(default_factory=dict)
    mean_mrr: dict[int, float] = field(default_factory=dict)
    mean_ndcg: dict[int, float] = field(default_factory=dict)
    per_query: list[MetricsResult] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------


def evaluate(
    results: list[Any],  # list[RetrievalResult] — avoid circular import
    df: pd.DataFrame,
    *,
    ks: list[int] | None = None,
) -> AggregateMetrics:
    """Compute all metrics for a list of retrieval results.

    Matches results by query_row_id to df rows to get ground truth.
    """
    if ks is None:
        ks = [1, 3, 5, 10, 20, 50]

    # Build lookup from row_id to ground truth
    row_lookup: dict[str, dict[str, Any]] = {}
    for _, row in df.iterrows():
        row_lookup[row["row_id"]] = {
            "targets": set(row["targets"]),
            "label_cardinality": row.get("label_cardinality", len(row["targets"])),
            "label_cardinality_bin": row.get("label_cardinality_bin", ""),
            "doc_type_id": row.get("doc_type_id"),
        }

    per_query: list[MetricsResult] = []

    for result in results:
        info = row_lookup.get(result.query_row_id)
        if info is None:
            continue

        true_ids = info["targets"]
        mr = MetricsResult(
            row_id=result.query_row_id,
            label_cardinality=info["label_cardinality"],
            label_cardinality_bin=info["label_cardinality_bin"],
            doc_type_id=info["doc_type_id"],
        )

        for k in ks:
            mr.recall[k] = recall_at_k(result.ranked_ids, true_ids, k)
            mr.mrr[k] = mrr_at_k(result.ranked_ids, true_ids, k)
            mr.ndcg[k] = ndcg_at_k(result.ranked_ids, true_ids, k)

        per_query.append(mr)

    # Aggregate
    agg = AggregateMetrics(n_queries=len(per_query), per_query=per_query)
    if per_query:
        for k in ks:
            agg.mean_recall[k] = sum(m.recall[k] for m in per_query) / len(per_query)
            agg.mean_mrr[k] = sum(m.mrr[k] for m in per_query) / len(per_query)
            agg.mean_ndcg[k] = sum(m.ndcg[k] for m in per_query) / len(per_query)

    return agg


# ---------------------------------------------------------------------------
# Stratified reporting
# ---------------------------------------------------------------------------


def stratified_report(
    metrics: AggregateMetrics,
    *,
    stratify_by: list[str] | None = None,
) -> dict[str, dict[str, AggregateMetrics]]:
    """Group per-query metrics by stratification columns."""
    if stratify_by is None:
        stratify_by = ["label_cardinality_bin", "doc_type_id"]

    report: dict[str, dict[str, AggregateMetrics]] = {}

    for col in stratify_by:
        groups: dict[str, list[MetricsResult]] = {}
        for m in metrics.per_query:
            val = str(getattr(m, col, None) or "unknown")
            groups.setdefault(val, []).append(m)

        col_report: dict[str, AggregateMetrics] = {}
        for val, group_metrics in groups.items():
            agg = AggregateMetrics(n_queries=len(group_metrics), per_query=group_metrics)
            if group_metrics:
                ks = list(group_metrics[0].recall.keys())
                for k in ks:
                    agg.mean_recall[k] = sum(m.recall[k] for m in group_metrics) / len(group_metrics)
                    agg.mean_mrr[k] = sum(m.mrr[k] for m in group_metrics) / len(group_metrics)
                    agg.mean_ndcg[k] = sum(m.ndcg[k] for m in group_metrics) / len(group_metrics)
            col_report[val] = agg

        report[col] = col_report

    return report


# ---------------------------------------------------------------------------
# Leakage checks
# ---------------------------------------------------------------------------


def leakage_check(df: pd.DataFrame, *, text_col: str = "facts_text_masked") -> list[dict[str, Any]]:
    """Citation leakage gate.

    Scans masked text for patterns that look like unmasked case citations.
    Returns list of {row_id, leaked_citations} for rows with leakage.
    Raises AssertionError if any leakage is found.
    """
    leaks: list[dict[str, Any]] = []

    for _, row in df.iterrows():
        text = row.get(text_col, "")
        if not isinstance(text, str):
            continue

        found = RE_FULL_CASE_CITE.findall(text)
        if found:
            leaks.append(
                {
                    "row_id": row.get("row_id", "unknown"),
                    "leaked_citations": [m if isinstance(m, str) else str(m) for m in found[:10]],
                }
            )

    if leaks:
        raise AssertionError(f"Citation leakage detected in {len(leaks)} rows. First: {leaks[0]}")

    return leaks


# ---------------------------------------------------------------------------
# Popularity dominance check
# ---------------------------------------------------------------------------


def popularity_dominance_check(
    model_metrics: AggregateMetrics,
    popularity_metrics: AggregateMetrics,
    *,
    reference_k: int = 10,
) -> dict[str, Any]:
    """Compare a model's metrics against the popularity baseline."""
    model_recall = model_metrics.mean_recall.get(reference_k, 0.0)
    pop_recall = popularity_metrics.mean_recall.get(reference_k, 0.0)

    if pop_recall > 0:
        relative_improvement = (model_recall - pop_recall) / pop_recall
    else:
        relative_improvement = float("inf") if model_recall > 0 else 0.0

    return {
        "beats_popularity": model_recall > pop_recall,
        "model_recall_at_k": round(model_recall, 4),
        "popularity_recall_at_k": round(pop_recall, 4),
        "relative_improvement": round(relative_improvement, 4),
        "reference_k": reference_k,
    }


# ---------------------------------------------------------------------------
# Report formatting
# ---------------------------------------------------------------------------


def format_report(
    model_name: str,
    aggregate: AggregateMetrics,
    stratified: dict[str, dict[str, AggregateMetrics]] | None = None,
    popularity_check: dict[str, Any] | None = None,
) -> str:
    """Format metrics into a markdown report string."""
    lines: list[str] = []
    lines.append(f"## {model_name}")
    lines.append(f"Queries evaluated: {aggregate.n_queries}")
    lines.append("")

    # Overall metrics table
    lines.append("### Overall Metrics")
    lines.append("| K | Recall@K | MRR@K | nDCG@K |")
    lines.append("|---|---------|-------|--------|")
    for k in sorted(aggregate.mean_recall.keys()):
        r = aggregate.mean_recall.get(k, 0)
        m = aggregate.mean_mrr.get(k, 0)
        n = aggregate.mean_ndcg.get(k, 0)
        lines.append(f"| {k} | {r:.4f} | {m:.4f} | {n:.4f} |")
    lines.append("")

    # Popularity dominance check
    if popularity_check:
        lines.append("### Popularity Dominance Check")
        beats = "Yes" if popularity_check["beats_popularity"] else "No"
        lines.append(f"- Beats popularity: {beats}")
        lines.append(f"- Model Recall@{popularity_check['reference_k']}: {popularity_check['model_recall_at_k']}")
        pop_r = popularity_check["popularity_recall_at_k"]
        lines.append(f"- Popularity Recall@{popularity_check['reference_k']}: {pop_r}")
        lines.append(f"- Relative improvement: {popularity_check['relative_improvement']:.1%}")
        lines.append("")

    # Stratified reports
    if stratified:
        for col, groups in stratified.items():
            lines.append(f"### Stratified by {col}")
            lines.append(f"| {col} | N | Recall@10 | MRR@10 | nDCG@10 |")
            lines.append("|---|---|---------|-------|--------|")
            for val, agg in sorted(groups.items()):
                r = agg.mean_recall.get(10, 0)
                m = agg.mean_mrr.get(10, 0)
                n = agg.mean_ndcg.get(10, 0)
                lines.append(f"| {val} | {agg.n_queries} | {r:.4f} | {m:.4f} | {n:.4f} |")
            lines.append("")

    return "\n".join(lines)

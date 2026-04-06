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


# ---------------------------------------------------------------------------
# Error analysis
# ---------------------------------------------------------------------------


def analyze_errors(
    results: list[Any],  # list[RetrievalResult]
    df: pd.DataFrame,
    k: int = 10,
) -> dict[str, Any]:
    """Analyze retrieval errors: what targets are missed and why.

    Returns dict with failure statistics, hardest targets, and position distribution.
    """
    row_lookup: dict[str, dict[str, Any]] = {}
    for _, row in df.iterrows():
        row_lookup[row["row_id"]] = {
            "targets": set(row["targets"]),
            "label_cardinality_bin": row.get("label_cardinality_bin", ""),
        }

    total_queries = 0
    zero_hit_queries = 0
    hit_positions: list[int] = []  # position of each hit (1-indexed)
    target_miss_counts: dict[str, int] = {}
    target_total_counts: dict[str, int] = {}
    failures_by_bin: dict[str, int] = {}
    queries_by_bin: dict[str, int] = {}

    for result in results:
        info = row_lookup.get(result.query_row_id)
        if info is None:
            continue

        true_ids = info["targets"]
        cardinality_bin = info["label_cardinality_bin"]
        total_queries += 1
        queries_by_bin[cardinality_bin] = queries_by_bin.get(cardinality_bin, 0) + 1

        # Track hits and misses
        hits_in_k = set()
        for pos, rid in enumerate(result.ranked_ids[:k]):
            if rid in true_ids:
                hits_in_k.add(rid)
                hit_positions.append(pos + 1)

        if not hits_in_k:
            zero_hit_queries += 1
            failures_by_bin[cardinality_bin] = failures_by_bin.get(cardinality_bin, 0) + 1

        # Track per-target miss rates
        for tid in true_ids:
            target_total_counts[tid] = target_total_counts.get(tid, 0) + 1
            if tid not in hits_in_k:
                target_miss_counts[tid] = target_miss_counts.get(tid, 0) + 1

    # Compute hardest targets (highest miss rate, min 2 appearances)
    hardest: list[tuple[str, float, int]] = []
    for tid, total in target_total_counts.items():
        if total >= 2:
            misses = target_miss_counts.get(tid, 0)
            hardest.append((tid, misses / total, total))
    hardest.sort(key=lambda x: (-x[1], -x[2]))

    # Position distribution
    pos_dist: dict[str, int] = {"1": 0, "2-3": 0, "4-5": 0, "6-10": 0}
    for p in hit_positions:
        if p == 1:
            pos_dist["1"] += 1
        elif p <= 3:
            pos_dist["2-3"] += 1
        elif p <= 5:
            pos_dist["4-5"] += 1
        else:
            pos_dist["6-10"] += 1

    return {
        "total_queries": total_queries,
        "zero_hit_queries": zero_hit_queries,
        "zero_hit_rate": zero_hit_queries / max(total_queries, 1),
        "total_hits_in_top_k": len(hit_positions),
        "hit_position_distribution": pos_dist,
        "hardest_targets": hardest[:20],
        "failures_by_cardinality": failures_by_bin,
        "queries_by_cardinality": queries_by_bin,
    }


def compare_models(
    results_a: list[Any],
    results_b: list[Any],
    df: pd.DataFrame,
    name_a: str,
    name_b: str,
    k: int = 10,
) -> dict[str, Any]:
    """Head-to-head comparison of two models on the same test set."""
    row_lookup: dict[str, set[str]] = {}
    for _, row in df.iterrows():
        row_lookup[row["row_id"]] = set(row["targets"])

    # Build per-query recall maps
    recall_a: dict[str, float] = {}
    for r in results_a:
        true_ids = row_lookup.get(r.query_row_id, set())
        recall_a[r.query_row_id] = recall_at_k(r.ranked_ids, true_ids, k) if true_ids else 0.0

    recall_b: dict[str, float] = {}
    for r in results_b:
        true_ids = row_lookup.get(r.query_row_id, set())
        recall_b[r.query_row_id] = recall_at_k(r.ranked_ids, true_ids, k) if true_ids else 0.0

    a_wins = 0
    b_wins = 0
    ties = 0
    for qid in recall_a:
        ra = recall_a.get(qid, 0)
        rb = recall_b.get(qid, 0)
        if ra > rb + 1e-9:
            a_wins += 1
        elif rb > ra + 1e-9:
            b_wins += 1
        else:
            ties += 1

    total = a_wins + b_wins + ties
    return {
        "name_a": name_a,
        "name_b": name_b,
        "a_wins": a_wins,
        "b_wins": b_wins,
        "ties": ties,
        "total": total,
        "a_win_rate": a_wins / max(total, 1),
        "b_win_rate": b_wins / max(total, 1),
    }


def format_error_report(analysis: dict[str, Any], model_name: str) -> str:
    """Format error analysis as markdown."""
    lines = [f"## Error Analysis: {model_name}", ""]
    lines.append(f"- Total queries: {analysis['total_queries']}")
    lines.append(f"- Zero-hit queries: {analysis['zero_hit_queries']} ({analysis['zero_hit_rate']:.1%})")
    lines.append(f"- Total hits in top-K: {analysis['total_hits_in_top_k']}")
    lines.append("")

    lines.append("### Hit Position Distribution")
    lines.append("| Position | Count |")
    lines.append("|----------|-------|")
    for pos, count in analysis["hit_position_distribution"].items():
        lines.append(f"| {pos} | {count} |")
    lines.append("")

    lines.append("### Zero-Hit Rate by Cardinality")
    lines.append("| Cardinality | Queries | Zero-Hit | Rate |")
    lines.append("|-------------|---------|----------|------|")
    for bin_val in sorted(analysis["queries_by_cardinality"].keys()):
        q = analysis["queries_by_cardinality"][bin_val]
        f = analysis["failures_by_cardinality"].get(bin_val, 0)
        lines.append(f"| {bin_val} | {q} | {f} | {f / max(q, 1):.1%} |")
    lines.append("")

    if analysis["hardest_targets"]:
        lines.append("### Hardest Targets (top 10)")
        lines.append("| Case ID | Miss Rate | Appearances |")
        lines.append("|---------|-----------|-------------|")
        for tid, miss_rate, total in analysis["hardest_targets"][:10]:
            lines.append(f"| {tid} | {miss_rate:.1%} | {total} |")
        lines.append("")

    return "\n".join(lines)


def format_comparison_report(comparison: dict[str, Any]) -> str:
    """Format model comparison as markdown."""
    lines = [f"## Model Comparison: {comparison['name_a']} vs {comparison['name_b']}", ""]
    lines.append("| Metric | Value |")
    lines.append("|--------|-------|")
    lines.append(f"| {comparison['name_a']} wins | {comparison['a_wins']} ({comparison['a_win_rate']:.1%}) |")
    lines.append(f"| {comparison['name_b']} wins | {comparison['b_wins']} ({comparison['b_win_rate']:.1%}) |")
    lines.append(f"| Ties | {comparison['ties']} |")
    lines.append(f"| Total queries | {comparison['total']} |")
    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Cost reporting
# ---------------------------------------------------------------------------


def generate_cost_report(manifest_path: str, *, cost_per_api_call: float = 0.0) -> str:
    """Generate a budget/cost report from a build manifest.

    Since CourtListener API is free, 'cost' here means API budget utilization
    rather than dollar cost. OCR cost is estimated if OCR was used.
    """
    import json
    from pathlib import Path

    data = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    results = data.get("results_summary", {})
    params = data.get("parameters", {})

    lines = ["## Budget & Cost Report", ""]
    lines.append(f"- Build ID: {data.get('build_id', 'unknown')}")
    lines.append(f"- Timestamp: {data.get('timestamp_utc', 'unknown')}")
    lines.append("")

    lines.append("### Pipeline Summary")
    lines.append("| Metric | Value |")
    lines.append("|--------|-------|")
    lines.append(f"| Total search hits | {results.get('total_hits', 'N/A')} |")
    lines.append(f"| Extracted spans | {results.get('extracted_spans', 'N/A')} |")
    lines.append(f"| Failures | {results.get('failures', 'N/A')} |")
    lines.append("")

    if results.get("resolver_enabled"):
        api_calls = results.get("resolver_api_calls", 0)
        cache_entries = results.get("resolver_cache_entries", 0)
        hit_rate = results.get("resolver_cache_hit_rate", 0)
        budget = params.get("resolver_budget_per_build", 10_000) if isinstance(params, dict) else 10_000

        lines.append("### Resolver Budget")
        lines.append("| Metric | Value |")
        lines.append("|--------|-------|")
        lines.append(f"| API calls made | {api_calls} |")
        lines.append(f"| Budget ceiling | {budget} |")
        lines.append(f"| Budget utilization | {api_calls / max(budget, 1):.1%} |")
        lines.append(f"| Cache entries | {cache_entries} |")
        lines.append(f"| Cache hit rate | {hit_rate:.1%} |")
        saved = int(cache_entries * hit_rate) if cache_entries else 0
        lines.append(f"| Estimated calls saved by cache | {saved} |")
        lines.append("")

    lines.append("### Exclusion Rates")
    total = results.get("total_hits", 0)
    extracted = results.get("extracted_spans", 0)
    failures = results.get("failures", 0)
    if total > 0:
        lines.append(f"- Extraction success: {extracted}/{total} ({extracted / total:.1%})")
        lines.append(f"- Failure rate: {failures}/{total} ({failures / total:.1%})")
    lines.append("")

    return "\n".join(lines)

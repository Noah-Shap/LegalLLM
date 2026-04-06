"""CLI entry point for running baseline evaluation.

Usage:
    legallm-eval --parquet data/processed/facts_dataset.parquet
    legallm-eval --parquet data/processed/facts_dataset.parquet --baselines popularity bm25 hybrid
    legallm-eval --parquet data/processed/facts_dataset.parquet --error-analysis --report-out report.md
    legallm-eval --parquet data/processed/facts_dataset.parquet --ablation --report-out ablation.md
    legallm-eval --cost-report --manifest data/processed/build_manifest.json
"""

from __future__ import annotations

import argparse
import sys

from legallm.baselines import BM25Baseline, PopularityBaseline, RetrievalResult
from legallm.dataset import load_dataset
from legallm.eval_harness import (
    analyze_errors,
    compare_models,
    evaluate,
    format_comparison_report,
    format_error_report,
    format_report,
    generate_cost_report,
    leakage_check,
    popularity_dominance_check,
    stratified_report,
)

ALL_BASELINES = ["popularity", "bm25", "dense", "hybrid", "reranker"]


def _make_model(name: str, args: argparse.Namespace):
    """Instantiate a baseline model by name."""
    if name == "popularity":
        return PopularityBaseline()
    if name == "bm25":
        return BM25Baseline(max_features=args.bm25_max_features, n_retrieve=args.bm25_n_retrieve)
    if name == "dense":
        from legallm.baselines import DenseRetrievalBaseline

        return DenseRetrievalBaseline()
    if name == "hybrid":
        from legallm.baselines import HybridBaseline

        return HybridBaseline(
            alpha=args.hybrid_alpha,
            bm25_max_features=args.bm25_max_features,
            bm25_n_retrieve=args.bm25_n_retrieve,
        )
    if name == "reranker":
        from legallm.baselines import RerankerBaseline

        return RerankerBaseline(
            n_retrieve=args.bm25_n_retrieve,
            bm25_max_features=args.bm25_max_features,
        )
    raise ValueError(f"Unknown baseline: {name}")


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description="LegalLLM evaluation harness")
    ap.add_argument("--parquet", type=str, default=None, help="Path to pipeline output parquet")
    ap.add_argument(
        "--baselines",
        nargs="+",
        default=["popularity", "bm25"],
        choices=ALL_BASELINES,
        help="Which baselines to run (default: popularity bm25)",
    )
    ap.add_argument("--ks", nargs="+", type=int, default=[1, 3, 5, 10, 20, 50])
    ap.add_argument("--min-targets", type=int, default=1)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--report-out", type=str, default=None)
    ap.add_argument("--skip-leakage-check", action="store_true")

    # BM25 tuning
    ap.add_argument("--bm25-max-features", type=int, default=10_000)
    ap.add_argument("--bm25-n-retrieve", type=int, default=100)

    # Hybrid tuning
    ap.add_argument("--hybrid-alpha", type=float, default=0.5, help="BM25 weight in hybrid (0-1)")

    # M4 modes
    ap.add_argument("--error-analysis", action="store_true", help="Run error analysis on each baseline")
    ap.add_argument("--compare", action="store_true", help="Produce head-to-head comparison between baselines")
    ap.add_argument("--ablation", action="store_true", help="Run BM25/hybrid parameter sweep")
    ap.add_argument("--cost-report", action="store_true", help="Generate budget/cost report from manifest")
    ap.add_argument("--manifest", type=str, default=None, help="Path to build_manifest.json (for --cost-report)")

    args = ap.parse_args(argv)

    # Cost report mode (no parquet needed)
    if args.cost_report:
        if not args.manifest:
            print("--manifest is required for --cost-report", file=sys.stderr)
            sys.exit(1)
        report = generate_cost_report(args.manifest)
        if args.report_out:
            with open(args.report_out, "w", encoding="utf-8") as f:
                f.write(f"# Cost Report\n\n{report}\n")
            print(f"Report written to {args.report_out}")
        else:
            print(report)
        return

    if not args.parquet:
        print("--parquet is required", file=sys.stderr)
        sys.exit(1)

    # Load dataset
    print(f"Loading dataset from {args.parquet}...")
    df = load_dataset(args.parquet, min_targets=args.min_targets, seed=args.seed)
    print(f"  Rows after filtering: {len(df)}")

    if df.empty:
        print("No rows with sufficient targets. Exiting.")
        return

    print(f"  Split distribution: {df['split'].value_counts().to_dict()}")
    print(f"  Label cardinality bins: {df['label_cardinality_bin'].value_counts().to_dict()}")

    # Leakage check
    if not args.skip_leakage_check:
        print("Running leakage check...")
        try:
            leakage_check(df)
            print("  Leakage check passed.")
        except AssertionError as e:
            print(f"  LEAKAGE DETECTED: {e}", file=sys.stderr)
            sys.exit(1)

    train_df = df[df["split"] == "train"]
    test_df = df[df["split"] == "test"]
    print(f"  Train: {len(train_df)}, Test: {len(test_df)}")

    if test_df.empty:
        print("No test rows. Try a larger dataset.")
        return

    # Ablation mode
    if args.ablation:
        _run_ablation(train_df, test_df, args)
        return

    # Standard evaluation
    all_reports: list[str] = []
    all_results: dict[str, list[RetrievalResult]] = {}
    all_metrics: dict[str, object] = {}
    popularity_metrics = None

    for baseline_name in args.baselines:
        print(f"\nRunning {baseline_name} baseline...")
        try:
            model = _make_model(baseline_name, args)
        except ImportError as e:
            print(f"  Skipping {baseline_name}: {e}")
            continue

        model.fit(train_df)
        results = model.predict(test_df, k=max(args.ks))
        metrics = evaluate(results, test_df, ks=args.ks)

        all_results[baseline_name] = results
        all_metrics[baseline_name] = metrics

        print(f"  Recall@10: {metrics.mean_recall.get(10, 0):.4f}")
        print(f"  MRR@10: {metrics.mean_mrr.get(10, 0):.4f}")

        strat = stratified_report(metrics)
        pop_check = None
        if baseline_name == "popularity":
            popularity_metrics = metrics
        elif popularity_metrics is not None:
            pop_check = popularity_dominance_check(metrics, popularity_metrics)

        report = format_report(baseline_name, metrics, strat, pop_check)
        all_reports.append(report)

        # Error analysis
        if args.error_analysis:
            err = analyze_errors(results, test_df, k=10)
            all_reports.append(format_error_report(err, baseline_name))

    # Model comparison
    if args.compare and len(all_results) >= 2:
        names = list(all_results.keys())
        for i in range(len(names) - 1):
            comp = compare_models(all_results[names[i]], all_results[names[i + 1]], test_df, names[i], names[i + 1])
            all_reports.append(format_comparison_report(comp))

    # Output
    full_report = "\n---\n\n".join(all_reports)
    if args.report_out:
        from pathlib import Path

        Path(args.report_out).parent.mkdir(parents=True, exist_ok=True)
        with open(args.report_out, "w", encoding="utf-8") as f:
            f.write(f"# Evaluation Report\n\n{full_report}\n")
        print(f"\nReport written to {args.report_out}")
    else:
        print(f"\n{'=' * 60}")
        print(full_report)


def _run_ablation(train_df, test_df, args):
    """Run parameter sweep for BM25 and hybrid models."""
    from legallm.eval_harness import evaluate

    configs = []
    # BM25 sweep
    for n_ret in [50, 100, 200]:
        for max_feat in [5000, 10_000, 20_000]:
            configs.append(("bm25", {"max_features": max_feat, "n_retrieve": n_ret}))

    # Hybrid sweep (if sentence-transformers available)
    try:
        from legallm.baselines import HybridBaseline

        for alpha in [0.3, 0.5, 0.7]:
            configs.append(("hybrid", {"alpha": alpha, "n_retrieve": 100}))
    except ImportError:
        print("  Skipping hybrid ablation (sentence-transformers not installed)")

    lines = ["## Ablation Study", ""]
    lines.append("| Model | Config | Recall@10 | MRR@10 | nDCG@10 |")
    lines.append("|-------|--------|-----------|--------|---------|")

    for model_type, params in configs:
        label = f"{model_type}({', '.join(f'{k}={v}' for k, v in params.items())})"
        print(f"  Ablation: {label}...")

        try:
            if model_type == "bm25":
                model = BM25Baseline(max_features=params["max_features"], n_retrieve=params["n_retrieve"])
            elif model_type == "hybrid":
                from legallm.baselines import HybridBaseline

                model = HybridBaseline(alpha=params["alpha"], bm25_n_retrieve=params.get("n_retrieve", 100))
            else:
                continue

            model.fit(train_df)
            results = model.predict(test_df, k=max(args.ks))
            metrics = evaluate(results, test_df, ks=args.ks)
            r = metrics.mean_recall.get(10, 0)
            m = metrics.mean_mrr.get(10, 0)
            n = metrics.mean_ndcg.get(10, 0)
            lines.append(f"| {model_type} | {params} | {r:.4f} | {m:.4f} | {n:.4f} |")
        except Exception as e:
            lines.append(f"| {model_type} | {params} | ERROR: {e} | | |")

    lines.append("")
    report = "\n".join(lines)

    if args.report_out:
        from pathlib import Path

        Path(args.report_out).parent.mkdir(parents=True, exist_ok=True)
        with open(args.report_out, "w", encoding="utf-8") as f:
            f.write(f"# Ablation Report\n\n{report}\n")
        print(f"\nReport written to {args.report_out}")
    else:
        print(f"\n{'=' * 60}")
        print(report)


if __name__ == "__main__":
    main()

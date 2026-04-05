"""CLI entry point for running baseline evaluation.

Usage:
    legallm-eval --parquet data/processed/facts_dataset.parquet
    legallm-eval --parquet data/processed/facts_dataset.parquet --baselines popularity bm25
    legallm-eval --parquet data/processed/facts_dataset.parquet --report-out reports/m3_eval.md
"""

from __future__ import annotations

import argparse
import sys

from legallm.baselines import BM25Baseline, PopularityBaseline
from legallm.dataset import load_dataset
from legallm.eval_harness import (
    evaluate,
    format_report,
    leakage_check,
    popularity_dominance_check,
    stratified_report,
)


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description="LegalLLM baseline evaluation harness")
    ap.add_argument("--parquet", type=str, required=True, help="Path to pipeline output parquet")
    ap.add_argument(
        "--baselines",
        nargs="+",
        default=["popularity", "bm25"],
        choices=["popularity", "bm25", "dense"],
        help="Which baselines to run (default: popularity bm25)",
    )
    ap.add_argument("--ks", nargs="+", type=int, default=[1, 3, 5, 10, 20, 50], help="K values for metrics")
    ap.add_argument("--min-targets", type=int, default=1, help="Minimum resolved targets per row")
    ap.add_argument("--seed", type=int, default=42, help="Random seed for splits")
    ap.add_argument("--report-out", type=str, default=None, help="Path to write markdown report (default: stdout)")
    ap.add_argument("--skip-leakage-check", action="store_true", help="Skip the citation leakage gate")
    args = ap.parse_args(argv)

    # Load and prepare dataset
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

    # Split
    train_df = df[df["split"] == "train"]
    test_df = df[df["split"] == "test"]
    print(f"  Train: {len(train_df)}, Test: {len(test_df)}")

    if test_df.empty:
        print("No test rows. Try a larger dataset.")
        return

    # Run baselines
    all_reports: list[str] = []
    popularity_metrics = None

    for baseline_name in args.baselines:
        print(f"\nRunning {baseline_name} baseline...")

        if baseline_name == "popularity":
            model = PopularityBaseline()
        elif baseline_name == "bm25":
            model = BM25Baseline()
        elif baseline_name == "dense":
            try:
                from legallm.baselines import DenseRetrievalBaseline

                model = DenseRetrievalBaseline()
            except ImportError as e:
                print(f"  Skipping dense baseline: {e}")
                continue
        else:
            continue

        model.fit(train_df)
        results = model.predict(test_df, k=max(args.ks))
        metrics = evaluate(results, test_df, ks=args.ks)

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

    # Output
    full_report = "\n---\n\n".join(all_reports)

    if args.report_out:
        with open(args.report_out, "w", encoding="utf-8") as f:
            f.write(f"# M3 Baseline Evaluation Report\n\n{full_report}\n")
        print(f"\nReport written to {args.report_out}")
    else:
        print(f"\n{'=' * 60}")
        print(full_report)


if __name__ == "__main__":
    main()

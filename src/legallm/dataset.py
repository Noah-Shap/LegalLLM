"""Dataset preparation: load pipeline parquet, deduplicate, split.

Transforms raw pipeline output into a modeling-ready dataset with stable
row IDs, near-duplicate removal, and stratified train/val/test splits.

Reference: approved_spec_package_v0_2.md §Modeling dataset row
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Row ID generation
# ---------------------------------------------------------------------------


def generate_row_id(search_result_id: Any, build_id: str, text: str) -> str:
    """Generate a stable, deterministic row identifier.

    Uses SHA-256 of (search_result_id, build_id, first 2000 chars of text).
    Returns a 16-character hex string.
    """
    payload = f"{search_result_id}|{build_id}|{text[:2000]}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Near-duplicate detection
# ---------------------------------------------------------------------------


def fuzzy_text_hash(text: str, *, shingle_size: int = 5, num_hashes: int = 64) -> str:
    """Character-shingle based fingerprint for near-duplicate detection.

    Computes a MinHash-style signature over character n-grams.
    Two texts with high Jaccard similarity will produce the same hash
    with high probability.
    """
    if not text:
        return "0" * 16

    # Generate character shingles
    shingles = set()
    clean = text.lower().strip()
    for i in range(len(clean) - shingle_size + 1):
        shingles.add(clean[i : i + shingle_size])

    if not shingles:
        return "0" * 16

    # Compute MinHash signature
    min_hashes = []
    for seed in range(num_hashes):
        min_val = float("inf")
        for shingle in shingles:
            h = int(hashlib.md5(f"{seed}:{shingle}".encode()).hexdigest()[:8], 16)
            min_val = min(min_val, h)
        min_hashes.append(min_val)

    # Combine into a single hash
    combined = hashlib.sha256(str(min_hashes).encode()).hexdigest()[:16]
    return combined


def deduplicate(
    df: pd.DataFrame,
    *,
    id_col: str = "search_result_id",
    text_col: str = "facts_text_masked",
    targets_col: str = "targets",
) -> pd.DataFrame:
    """Remove near-duplicate rows.

    Pass 1: Exact dedup on search_result_id (same doc in multiple builds).
    Pass 2: Fuzzy dedup on text fingerprint. Keeps row with more targets.
    """
    if df.empty:
        return df

    # Pass 1: exact dedup — keep row with most targets
    df = df.copy()
    df["_target_count"] = df[targets_col].apply(len)
    df = df.sort_values("_target_count", ascending=False).drop_duplicates(subset=[id_col], keep="first")

    # Pass 2: fuzzy dedup on text
    df["_text_hash"] = df[text_col].apply(fuzzy_text_hash)
    df = df.sort_values("_target_count", ascending=False).drop_duplicates(subset=["_text_hash"], keep="first")

    df = df.drop(columns=["_target_count", "_text_hash"])
    return df.reset_index(drop=True)


# ---------------------------------------------------------------------------
# Label cardinality
# ---------------------------------------------------------------------------


def label_cardinality_bin(n: int) -> str:
    """Map target count to bin: '1', '2-3', '4-7', '8+'."""
    if n <= 1:
        return "1"
    if n <= 3:
        return "2-3"
    if n <= 7:
        return "4-7"
    return "8+"


# ---------------------------------------------------------------------------
# Train/val/test split
# ---------------------------------------------------------------------------


def split_dataset(
    df: pd.DataFrame,
    *,
    train_frac: float = 0.7,
    val_frac: float = 0.15,
    test_frac: float = 0.15,
    seed: int = 42,
) -> pd.DataFrame:
    """Add a 'split' column (train/val/test) with stratified random assignment.

    Stratifies by label_cardinality_bin to ensure proportional representation.
    """
    df = df.copy()
    rng = np.random.default_rng(seed)

    # Ensure label_cardinality_bin exists
    if "label_cardinality_bin" not in df.columns:
        df["label_cardinality_bin"] = df["targets"].apply(lambda t: label_cardinality_bin(len(t)))

    splits = [""] * len(df)

    # Stratify by label_cardinality_bin
    for _bin_val, group in df.groupby("label_cardinality_bin"):
        indices = group.index.tolist()
        rng.shuffle(indices)

        n = len(indices)
        n_train = max(1, int(n * train_frac))
        n_val = max(0, int(n * val_frac))

        for i, idx in enumerate(indices):
            if i < n_train:
                splits[idx] = "train"
            elif i < n_train + n_val:
                splits[idx] = "val"
            else:
                splits[idx] = "test"

    df["split"] = splits

    # Ensure no empty splits for small datasets — assign at least 1 to test if all went to train
    if "test" not in df["split"].values and len(df) > 2:
        last_train = df[df["split"] == "train"].index[-1]
        df.loc[last_train, "split"] = "test"

    return df


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def load_dataset(
    parquet_path: str | Path,
    *,
    dedupe: bool = True,
    split: bool = True,
    min_targets: int = 1,
    seed: int = 42,
) -> pd.DataFrame:
    """Load pipeline parquet output into a modeling-ready DataFrame.

    Parses targets_case_ids from JSON, filters empty targets, generates
    row_id, deduplicates, splits, and adds derived columns.
    """
    df = pd.read_parquet(parquet_path)

    # Parse targets from JSON string to list
    df["targets"] = df["targets_case_ids"].apply(lambda x: json.loads(x) if isinstance(x, str) else (x or []))

    # Filter rows with too few targets
    df["label_cardinality"] = df["targets"].apply(len)
    df = df[df["label_cardinality"] >= min_targets].reset_index(drop=True)

    if df.empty:
        df["row_id"] = pd.Series(dtype=str)
        df["label_cardinality_bin"] = pd.Series(dtype=str)
        if split:
            df["split"] = pd.Series(dtype=str)
        return df

    # Generate row IDs
    df["row_id"] = df.apply(
        lambda r: generate_row_id(r["search_result_id"], r.get("build_id", ""), r.get("facts_text_masked", "")),
        axis=1,
    )

    # Add cardinality bin
    df["label_cardinality_bin"] = df["label_cardinality"].apply(label_cardinality_bin)

    # Deduplicate
    if dedupe:
        df = deduplicate(df)

    # Split
    if split:
        df = split_dataset(df, seed=seed)

    return df

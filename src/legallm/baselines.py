"""Baseline retrieval models for citation prediction.

Three baselines:
  0) Popularity: rank cases by global frequency (floor)
  1) BM25/Lexical: TF-IDF retrieval over masked facts text
  2) Dense: sentence-transformer embeddings (optional, requires legallm[dense])

Reference: approved_spec_package_v0_2.md §Initial modeling metric targets
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# ---------------------------------------------------------------------------
# Common data structures
# ---------------------------------------------------------------------------


@dataclass
class RetrievalResult:
    """Ranked list of candidate case IDs with scores for a single query."""

    query_row_id: str
    ranked_ids: list[str] = field(default_factory=list)
    scores: list[float] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def aggregate_case_ids(
    sim_scores: np.ndarray,
    train_targets: list[list[str]],
    k: int,
    n_retrieve: int = 50,
) -> tuple[list[str], list[float]]:
    """Aggregate case IDs from top-N retrieved training rows.

    For each retrieved training row, its target case IDs receive the
    similarity score as a vote. Case IDs are ranked by total vote.

    Args:
        sim_scores: 1D array of similarity scores (one per training row).
        train_targets: list of target lists, parallel to sim_scores.
        k: number of case IDs to return.
        n_retrieve: number of training rows to consider.

    Returns:
        (ranked_ids, scores) — top-k case IDs with aggregated scores.
    """
    top_indices = np.argsort(sim_scores)[::-1][:n_retrieve]

    case_scores: dict[str, float] = {}
    for idx in top_indices:
        score = float(sim_scores[idx])
        if score <= 0:
            continue
        for case_id in train_targets[idx]:
            case_scores[case_id] = case_scores.get(case_id, 0.0) + score

    # Sort by aggregated score descending
    sorted_cases = sorted(case_scores.items(), key=lambda x: x[1], reverse=True)[:k]
    ranked_ids = [c[0] for c in sorted_cases]
    scores = [c[1] for c in sorted_cases]
    return ranked_ids, scores


# ---------------------------------------------------------------------------
# Baseline 0: Popularity
# ---------------------------------------------------------------------------


class PopularityBaseline:
    """Rank all cases by global citation frequency in training set.

    Every query gets the same ranking. This is the floor.
    """

    def __init__(self) -> None:
        self._ranked_ids: list[str] = []
        self._scores: list[float] = []

    def fit(self, train_df: pd.DataFrame) -> None:
        """Count case ID frequency across training targets."""
        counter: Counter[str] = Counter()
        for targets in train_df["targets"]:
            for case_id in targets:
                counter[case_id] += 1

        sorted_cases = counter.most_common()
        self._ranked_ids = [c[0] for c in sorted_cases]
        self._scores = [float(c[1]) for c in sorted_cases]

    def predict(self, df: pd.DataFrame, k: int = 100) -> list[RetrievalResult]:
        """Return top-k most popular case IDs for every row."""
        results = []
        for _, row in df.iterrows():
            results.append(
                RetrievalResult(
                    query_row_id=row["row_id"],
                    ranked_ids=self._ranked_ids[:k],
                    scores=self._scores[:k],
                )
            )
        return results


# ---------------------------------------------------------------------------
# Baseline 1: BM25/Lexical (TF-IDF)
# ---------------------------------------------------------------------------


class BM25Baseline:
    """Lexical retrieval using TF-IDF (approximates BM25).

    Retrieves similar training briefs by text similarity, then aggregates
    their target case IDs weighted by similarity.
    """

    def __init__(self, *, max_features: int = 10_000, n_retrieve: int = 50) -> None:
        self.max_features = max_features
        self.n_retrieve = n_retrieve
        self._vectorizer: TfidfVectorizer | None = None
        self._train_matrix: Any = None
        self._train_targets: list[list[str]] = []

    def fit(self, train_df: pd.DataFrame) -> None:
        """Fit TF-IDF vectorizer on training facts_text_masked."""
        self._vectorizer = TfidfVectorizer(
            max_features=self.max_features,
            sublinear_tf=True,
            stop_words="english",
        )
        texts = train_df["facts_text_masked"].fillna("").tolist()
        self._train_matrix = self._vectorizer.fit_transform(texts)
        self._train_targets = train_df["targets"].tolist()

    def predict(self, df: pd.DataFrame, k: int = 100) -> list[RetrievalResult]:
        """For each query: TF-IDF similarity → aggregate case IDs → top-k."""
        if self._vectorizer is None or self._train_matrix is None:
            raise RuntimeError("Call fit() before predict()")

        results = []
        for _, row in df.iterrows():
            query_vec = self._vectorizer.transform([row.get("facts_text_masked", "")])
            sims = cosine_similarity(query_vec, self._train_matrix).flatten()

            ranked_ids, scores = aggregate_case_ids(sims, self._train_targets, k, self.n_retrieve)
            results.append(RetrievalResult(query_row_id=row["row_id"], ranked_ids=ranked_ids, scores=scores))

        return results


# ---------------------------------------------------------------------------
# Baseline 2: Dense Retrieval (optional)
# ---------------------------------------------------------------------------


class DenseRetrievalBaseline:
    """Dense embedding retrieval using sentence-transformers.

    Requires: pip install legallm[dense]
    """

    def __init__(self, *, model_name: str = "all-MiniLM-L6-v2", n_retrieve: int = 50) -> None:
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError:
            raise ImportError(
                "sentence-transformers is required for dense retrieval. Install with: pip install legallm[dense]"
            ) from None

        self.model_name = model_name
        self.n_retrieve = n_retrieve
        self._model = SentenceTransformer(model_name)
        self._train_embeddings: np.ndarray | None = None
        self._train_targets: list[list[str]] = []

    def fit(self, train_df: pd.DataFrame) -> None:
        """Encode training texts to dense embeddings."""
        texts = train_df["facts_text_masked"].fillna("").tolist()
        self._train_embeddings = self._model.encode(texts, show_progress_bar=False, convert_to_numpy=True)
        self._train_targets = train_df["targets"].tolist()

    def predict(self, df: pd.DataFrame, k: int = 100) -> list[RetrievalResult]:
        """Encode queries → cosine similarity → aggregate → top-k."""
        if self._train_embeddings is None:
            raise RuntimeError("Call fit() before predict()")

        texts = df["facts_text_masked"].fillna("").tolist()
        query_embeddings = self._model.encode(texts, show_progress_bar=False, convert_to_numpy=True)

        results = []
        row_ids = df["row_id"].tolist()
        for i, row_id in enumerate(row_ids):
            sims = cosine_similarity(query_embeddings[i : i + 1], self._train_embeddings).flatten()
            ranked_ids, scores = aggregate_case_ids(sims, self._train_targets, k, self.n_retrieve)
            results.append(RetrievalResult(query_row_id=row_id, ranked_ids=ranked_ids, scores=scores))

        return results


# ---------------------------------------------------------------------------
# Hybrid: BM25 + Dense score fusion
# ---------------------------------------------------------------------------


def _normalize_scores(scores: np.ndarray) -> np.ndarray:
    """Min-max normalize scores to [0, 1]."""
    mn, mx = scores.min(), scores.max()
    if mx - mn < 1e-9:
        return np.zeros_like(scores)
    return np.asarray((scores - mn) / (mx - mn))


class HybridBaseline:
    """Weighted fusion of BM25 (sparse) and Dense (embedding) similarity.

    Combines normalized BM25 and Dense similarity scores:
        fused = alpha * bm25_norm + (1 - alpha) * dense_norm

    Requires: pip install legallm[dense]
    """

    def __init__(
        self,
        *,
        alpha: float = 0.5,
        bm25_max_features: int = 10_000,
        bm25_n_retrieve: int = 100,
        dense_model_name: str = "all-MiniLM-L6-v2",
        n_retrieve: int = 100,
    ) -> None:
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError:
            raise ImportError(
                "sentence-transformers is required for hybrid retrieval. Install with: pip install legallm[dense]"
            ) from None

        self.alpha = alpha
        self.n_retrieve = n_retrieve
        self._bm25 = BM25Baseline(max_features=bm25_max_features, n_retrieve=n_retrieve)
        self._dense_model = SentenceTransformer(dense_model_name)
        self._train_embeddings: np.ndarray | None = None
        self._train_targets: list[list[str]] = []

    def fit(self, train_df: pd.DataFrame) -> None:
        self._bm25.fit(train_df)
        texts = train_df["facts_text_masked"].fillna("").tolist()
        self._train_embeddings = self._dense_model.encode(texts, show_progress_bar=False, convert_to_numpy=True)
        self._train_targets = train_df["targets"].tolist()

    def predict(self, df: pd.DataFrame, k: int = 100) -> list[RetrievalResult]:
        if self._bm25._vectorizer is None or self._bm25._train_matrix is None or self._train_embeddings is None:
            raise RuntimeError("Call fit() before predict()")

        texts = df["facts_text_masked"].fillna("").tolist()
        query_embeddings = self._dense_model.encode(texts, show_progress_bar=False, convert_to_numpy=True)

        results = []
        for i, (_, row) in enumerate(df.iterrows()):
            # BM25 similarities
            query_vec = self._bm25._vectorizer.transform([row.get("facts_text_masked", "")])
            bm25_sims = cosine_similarity(query_vec, self._bm25._train_matrix).flatten()

            # Dense similarities
            dense_sims = cosine_similarity(query_embeddings[i : i + 1], self._train_embeddings).flatten()

            # Normalize and fuse
            fused = self.alpha * _normalize_scores(bm25_sims) + (1 - self.alpha) * _normalize_scores(dense_sims)

            ranked_ids, scores = aggregate_case_ids(fused, self._train_targets, k, self.n_retrieve)
            results.append(RetrievalResult(query_row_id=row["row_id"], ranked_ids=ranked_ids, scores=scores))

        return results


# ---------------------------------------------------------------------------
# Reranker: BM25 retrieve → Dense rerank
# ---------------------------------------------------------------------------


class RerankerBaseline:
    """Two-stage: BM25 retrieves candidates, Dense reranks them.

    Stage 1: BM25 retrieves top-N training rows by TF-IDF similarity.
    Stage 2: Dense model reranks those N rows by embedding cosine similarity.
    Case IDs are aggregated from the reranked order.

    Requires: pip install legallm[dense]
    """

    def __init__(
        self,
        *,
        n_retrieve: int = 100,
        bm25_max_features: int = 10_000,
        dense_model_name: str = "all-MiniLM-L6-v2",
    ) -> None:
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError:
            raise ImportError(
                "sentence-transformers is required for reranker. Install with: pip install legallm[dense]"
            ) from None

        self.n_retrieve = n_retrieve
        self._bm25 = BM25Baseline(max_features=bm25_max_features, n_retrieve=n_retrieve)
        self._dense_model = SentenceTransformer(dense_model_name)
        self._train_embeddings: np.ndarray | None = None
        self._train_targets: list[list[str]] = []

    def fit(self, train_df: pd.DataFrame) -> None:
        self._bm25.fit(train_df)
        texts = train_df["facts_text_masked"].fillna("").tolist()
        self._train_embeddings = self._dense_model.encode(texts, show_progress_bar=False, convert_to_numpy=True)
        self._train_targets = train_df["targets"].tolist()

    def predict(self, df: pd.DataFrame, k: int = 100) -> list[RetrievalResult]:
        if self._bm25._vectorizer is None or self._bm25._train_matrix is None or self._train_embeddings is None:
            raise RuntimeError("Call fit() before predict()")

        texts = df["facts_text_masked"].fillna("").tolist()
        query_embeddings = self._dense_model.encode(texts, show_progress_bar=False, convert_to_numpy=True)

        results = []
        for i, (_, row) in enumerate(df.iterrows()):
            # Stage 1: BM25 retrieve top-N
            query_vec = self._bm25._vectorizer.transform([row.get("facts_text_masked", "")])
            bm25_sims = cosine_similarity(query_vec, self._bm25._train_matrix).flatten()
            top_n_indices = np.argsort(bm25_sims)[::-1][: self.n_retrieve]

            # Stage 2: Dense rerank the top-N
            candidate_embeddings = self._train_embeddings[top_n_indices]
            dense_sims = cosine_similarity(query_embeddings[i : i + 1], candidate_embeddings).flatten()

            # Aggregate case IDs from reranked candidates
            reranked_order = np.argsort(dense_sims)[::-1]
            case_scores: dict[str, float] = {}
            for rank, local_idx in enumerate(reranked_order):
                global_idx = top_n_indices[local_idx]
                score = float(dense_sims[local_idx])
                if score <= 0:
                    continue
                for case_id in self._train_targets[global_idx]:
                    case_scores[case_id] = case_scores.get(case_id, 0.0) + score

            sorted_cases = sorted(case_scores.items(), key=lambda x: x[1], reverse=True)[:k]
            ranked_ids = [c[0] for c in sorted_cases]
            scores = [c[1] for c in sorted_cases]
            results.append(RetrievalResult(query_row_id=row["row_id"], ranked_ids=ranked_ids, scores=scores))

        return results

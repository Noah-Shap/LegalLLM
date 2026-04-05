"""Citation resolver: maps normalized case citations to CourtListener cluster IDs.

Resolves citations extracted by citation_extractor.py to canonical CourtListener
opinion cluster IDs via the CourtListener REST v4 search API. Implements caching,
budget enforcement, and confidence scoring per the approved spec.

Reference: approved_spec_package_v0_2.md §Resolver architecture + constraints
"""

from __future__ import annotations

import datetime
import json
import logging
import os
import random
import re
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import requests

from legallm.citation_extractor import ExtractedCitation

logger = logging.getLogger(__name__)

BASE = "https://www.courtlistener.com/api/rest/v4"
RESOLVER_VERSION = "1.0.0"

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ResolverConfig:
    """Configuration for the citation resolver."""

    min_confidence: float = 0.90
    batch_size: int = 50
    max_retries: int = 5
    budget_per_build: int = 10_000
    budget_per_hour: int = 5_000
    cache_path: Path = field(default_factory=lambda: Path("data/processed/citation_cache.json"))


# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------


@dataclass
class CacheEntry:
    """One cached resolution result."""

    resolved_id: str | None
    resolution_status: str  # "resolved" | "unresolved"
    confidence: float | None
    timestamp: str
    resolver_version: str


class CitationCache:
    """Persistent JSON-based citation resolution cache."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self._entries: dict[str, CacheEntry] = {}
        self._hits = 0
        self._misses = 0
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            stored_version = data.get("resolver_version", "")
            if stored_version != RESOLVER_VERSION:
                logger.info("Cache version mismatch (%s != %s), invalidating", stored_version, RESOLVER_VERSION)
                return
            for key, val in data.get("entries", {}).items():
                self._entries[key] = CacheEntry(**val)
        except (json.JSONDecodeError, TypeError, KeyError) as e:
            logger.warning("Cache file corrupt (%s), starting fresh", e)

    def get(self, normalized: str) -> CacheEntry | None:
        entry = self._entries.get(normalized)
        if entry is not None:
            self._hits += 1
        else:
            self._misses += 1
        return entry

    def put(self, normalized: str, entry: CacheEntry) -> None:
        self._entries[normalized] = entry

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "resolver_version": RESOLVER_VERSION,
            "entry_count": len(self._entries),
            "entries": {k: asdict(v) for k, v in self._entries.items()},
        }
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
        os.replace(str(tmp), str(self.path))

    def hit_rate(self) -> float:
        total = self._hits + self._misses
        return self._hits / total if total > 0 else 0.0

    def __len__(self) -> int:
        return len(self._entries)


# ---------------------------------------------------------------------------
# Budget tracker
# ---------------------------------------------------------------------------


class BudgetTracker:
    """Enforces per-build, per-hour, and daily request limits."""

    def __init__(self, budget_per_build: int, budget_per_hour: int, daily_ceiling: int = 25_000):
        self.budget_per_build = budget_per_build
        self.budget_per_hour = budget_per_hour
        self.daily_ceiling = daily_ceiling
        self._build_count = 0
        self._hour_counts: dict[str, int] = {}
        self._daily_count = 0

    def _hour_key(self) -> str:
        return datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%dT%H")

    def can_spend(self, n: int = 1) -> bool:
        if self._build_count + n > self.budget_per_build:
            return False
        hk = self._hour_key()
        if self._hour_counts.get(hk, 0) + n > self.budget_per_hour:
            return False
        if self._daily_count + n > self.daily_ceiling:
            return False
        return True

    def spend(self, n: int = 1) -> None:
        self._build_count += n
        hk = self._hour_key()
        self._hour_counts[hk] = self._hour_counts.get(hk, 0) + n
        self._daily_count += n

    @property
    def build_count(self) -> int:
        return self._build_count


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


@dataclass
class ResolverMetrics:
    """Counters for build manifest recording."""

    total_submitted: int = 0
    cache_hits: int = 0
    api_calls: int = 0
    resolved_count: int = 0
    unresolved_count: int = 0
    budget_exceeded_count: int = 0
    error_count: int = 0


# ---------------------------------------------------------------------------
# API interaction
# ---------------------------------------------------------------------------


def _normalize_cl_citation(cite_str: str) -> str:
    """Normalize a citation string from CourtListener for comparison."""
    # Collapse whitespace, strip
    s = re.sub(r"\s+", " ", cite_str.strip())
    return s


def _evaluate_results(
    normalized: str,
    results: list[dict[str, Any]],
    min_confidence: float,
) -> tuple[str | None, float | None, str | None]:
    """Evaluate CourtListener search results for a citation query.

    Returns (cluster_id, confidence, excluded_reason).
    """
    if not results:
        return None, None, "no_match"

    # Find results where the queried citation appears in the result's citation list
    exact_matches: list[dict[str, Any]] = []
    for result in results:
        cite_list = result.get("citation", [])
        if not isinstance(cite_list, list):
            continue
        for c in cite_list:
            if _normalize_cl_citation(c) == _normalize_cl_citation(normalized):
                exact_matches.append(result)
                break

    if len(exact_matches) == 1:
        cluster_id = exact_matches[0].get("cluster_id")
        if cluster_id is not None:
            return str(cluster_id), 1.0, None

    if len(exact_matches) > 1:
        return None, None, "low_confidence_or_ambiguous"

    # No exact match in citation lists — try fuzzy match on first result only
    if len(results) == 1:
        result = results[0]
        cluster_id = result.get("cluster_id")
        # Check volume/page overlap as a weak signal
        cite_list = result.get("citation", [])
        parts = normalized.split()
        if len(parts) >= 3:
            volume, page = parts[0], parts[-1]
            for c in cite_list:
                c_parts = c.split()
                if len(c_parts) >= 3 and c_parts[0] == volume and c_parts[-1] == page:
                    # Volume and page match — moderate confidence
                    if min_confidence <= 0.80 and cluster_id is not None:
                        return str(cluster_id), 0.80, None
        return None, None, "low_confidence_or_ambiguous"

    return None, None, "low_confidence_or_ambiguous"


def _query_single_citation(
    session: requests.Session,
    normalized: str,
    config: ResolverConfig,
) -> tuple[str | None, float | None, str | None]:
    """Query CourtListener for a single normalized citation.

    Returns (cluster_id, confidence, excluded_reason).
    """
    url = f"{BASE}/search/"
    params = {"type": "o", "citation": normalized}

    last_error: str | None = None
    for attempt in range(config.max_retries):
        try:
            r = session.get(url, params=params, timeout=30)
            if r.status_code == 429:
                # Rate limited — backoff and retry
                delay = (2**attempt) + random.uniform(0, 0.5 * (2**attempt))
                time.sleep(delay)
                last_error = "rate_limited_429"
                continue
            if r.status_code >= 500:
                delay = (2**attempt) + random.uniform(0, 0.5 * (2**attempt))
                time.sleep(delay)
                last_error = f"server_error_{r.status_code}"
                continue
            if r.status_code != 200:
                return None, None, f"http_error_{r.status_code}"

            data = r.json()
            results = data.get("results", [])
            return _evaluate_results(normalized, results, config.min_confidence)

        except (requests.Timeout, requests.ConnectionError) as e:
            delay = (2**attempt) + random.uniform(0, 0.5 * (2**attempt))
            time.sleep(delay)
            last_error = f"{type(e).__name__}"
        except (json.JSONDecodeError, KeyError) as e:
            return None, None, f"api_response_parse_error: {e}"

    return None, None, f"api_error_after_retries: {last_error}"


# ---------------------------------------------------------------------------
# Main resolver
# ---------------------------------------------------------------------------


def resolve_citations(
    citations: list[ExtractedCitation],
    session: requests.Session,
    config: ResolverConfig,
    cache: CitationCache,
    budget: BudgetTracker,
) -> tuple[list[ExtractedCitation], list[str], ResolverMetrics]:
    """Resolve a list of case citations to CourtListener cluster IDs.

    Args:
        citations: ExtractedCitation objects with target_type="case" and normalized filled.
        session: Authenticated CourtListener API session (from cl_session()).
        config: Resolver configuration.
        cache: Persistent citation cache (shared across documents in a build).
        budget: Budget tracker (shared across documents in a build).

    Returns:
        (enriched_citations, targets_case_ids, metrics)
    """
    metrics = ResolverMetrics()

    if not citations:
        return [], [], metrics

    # Deduplicate by normalized string to avoid redundant API calls
    seen: dict[str, ExtractedCitation] = {}
    for cite in citations:
        if cite.normalized and cite.normalized not in seen:
            seen[cite.normalized] = cite
    unique_normalized = list(seen.keys())
    metrics.total_submitted = len(unique_normalized)

    # Phase 1: Check cache
    uncached: list[str] = []
    resolved_map: dict[str, tuple[str | None, float | None, str | None]] = {}

    for norm in unique_normalized:
        entry = cache.get(norm)
        if entry is not None:
            metrics.cache_hits += 1
            excl = None if entry.resolution_status == "resolved" else "cached_unresolved"
            resolved_map[norm] = (entry.resolved_id, entry.confidence, excl)
        else:
            uncached.append(norm)

    # Phase 2: Query API in batches
    for i in range(0, len(uncached), config.batch_size):
        chunk = uncached[i : i + config.batch_size]

        if not budget.can_spend(len(chunk)):
            # Mark all remaining as budget exceeded
            for norm in uncached[i:]:
                resolved_map[norm] = (None, None, "api_budget_exceeded")
                metrics.budget_exceeded_count += 1
            break

        for norm in chunk:
            cluster_id, confidence, excluded_reason = _query_single_citation(session, norm, config)
            metrics.api_calls += 1
            budget.spend(1)

            resolved_map[norm] = (cluster_id, confidence, excluded_reason)

            # Cache the result
            status = "resolved" if cluster_id is not None else "unresolved"

            cache.put(
                norm,
                CacheEntry(
                    resolved_id=cluster_id,
                    resolution_status=status,
                    confidence=confidence,
                    timestamp=datetime.datetime.now(datetime.UTC).isoformat(),
                    resolver_version=RESOLVER_VERSION,
                ),
            )

        # Save cache after each batch chunk
        cache.save()

    # Phase 3: Apply results to all citations (including duplicates)
    for cite in citations:
        if cite.normalized and cite.normalized in resolved_map:
            cluster_id, confidence, excluded_reason = resolved_map[cite.normalized]
            if cluster_id is not None:
                cite.resolution_status = "resolved"
                cite.resolved_id = str(cluster_id)
                cite.resolved_source = "courtlistener_api"
                cite.confidence = confidence
                metrics.resolved_count += 1
            else:
                cite.resolution_status = "unresolved"
                cite.excluded_reason = excluded_reason
                if excluded_reason and "budget" in excluded_reason:
                    pass  # already counted
                else:
                    metrics.unresolved_count += 1

    # Build targets_case_ids (Phase-1 labels)
    targets_case_ids: list[str] = []
    seen_ids: set[str] = set()
    for cite in citations:
        if cite.resolution_status == "resolved" and cite.resolved_id and cite.resolved_id not in seen_ids:
            targets_case_ids.append(cite.resolved_id)
            seen_ids.add(cite.resolved_id)

    return citations, targets_case_ids, metrics


# ---------------------------------------------------------------------------
# Helper for pipeline output
# ---------------------------------------------------------------------------


def citation_to_target_dict(cite: ExtractedCitation) -> dict[str, Any]:
    """Convert an ExtractedCitation to the targets_all object schema from the spec."""
    return {
        "original_text": cite.original_text,
        "normalized": cite.normalized,
        "target_type": cite.target_type,
        "resolution_status": cite.resolution_status,
        "resolved_id": cite.resolved_id,
        "excluded_reason": cite.excluded_reason,
        "resolved_source": cite.resolved_source,
        "confidence": cite.confidence,
    }

"""Tests for legallm.citation_resolver module."""

import json
from unittest.mock import MagicMock

import pytest

from legallm.citation_extractor import ExtractedCitation
from legallm.citation_resolver import (
    BudgetTracker,
    CacheEntry,
    CitationCache,
    ResolverConfig,
    _evaluate_results,
    citation_to_target_dict,
    resolve_citations,
)

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def resolver_config(tmp_path):
    return ResolverConfig(
        min_confidence=0.90,
        batch_size=10,
        max_retries=2,
        budget_per_build=100,
        budget_per_hour=50,
        cache_path=tmp_path / "test_cache.json",
    )


@pytest.fixture
def mock_cl_response_single():
    """A CourtListener search response with one exact match."""
    return {
        "results": [
            {
                "cluster_id": 12345,
                "caseName": "Smith v. Jones",
                "citation": ["500 U.S. 100", "111 S.Ct. 1000", "113 L.Ed.2d 100"],
                "court": "Supreme Court of the United States",
                "dateFiled": "1990-06-15",
            }
        ]
    }


@pytest.fixture
def mock_cl_response_empty():
    """A CourtListener search response with no results."""
    return {"results": []}


@pytest.fixture
def mock_cl_response_ambiguous():
    """A CourtListener search response with multiple exact matches."""
    return {
        "results": [
            {
                "cluster_id": 11111,
                "caseName": "Alpha v. Beta",
                "citation": ["500 U.S. 100"],
                "court": "Supreme Court",
            },
            {
                "cluster_id": 22222,
                "caseName": "Gamma v. Delta",
                "citation": ["500 U.S. 100"],
                "court": "Supreme Court",
            },
        ]
    }


@pytest.fixture
def sample_case_citation():
    return ExtractedCitation(
        original_text="500 U.S. 100 (1990)",
        start=0,
        end=20,
        target_type="case",
        volume="500",
        reporter="U.S.",
        page="100",
        normalized="500 U.S. 100",
    )


# ============================================================================
# CitationCache
# ============================================================================


class TestCitationCache:
    def test_empty_cache_returns_none(self, tmp_path):
        cache = CitationCache(tmp_path / "cache.json")
        assert cache.get("500 U.S. 100") is None

    def test_put_and_get(self, tmp_path):
        cache = CitationCache(tmp_path / "cache.json")
        entry = CacheEntry(
            resolved_id="12345",
            resolution_status="resolved",
            confidence=1.0,
            timestamp="2026-01-01T00:00:00",
            resolver_version="1.0.0",
        )
        cache.put("500 U.S. 100", entry)
        result = cache.get("500 U.S. 100")
        assert result is not None
        assert result.resolved_id == "12345"
        assert result.confidence == 1.0

    def test_save_and_load(self, tmp_path):
        path = tmp_path / "cache.json"
        cache = CitationCache(path)
        entry = CacheEntry(
            resolved_id="12345",
            resolution_status="resolved",
            confidence=1.0,
            timestamp="2026-01-01T00:00:00",
            resolver_version="1.0.0",
        )
        cache.put("500 U.S. 100", entry)
        cache.save()

        # Load in a new instance
        cache2 = CitationCache(path)
        result = cache2.get("500 U.S. 100")
        assert result is not None
        assert result.resolved_id == "12345"

    def test_version_mismatch_invalidates(self, tmp_path):
        path = tmp_path / "cache.json"
        # Write a cache with a different version
        data = {
            "resolver_version": "0.0.1",
            "entries": {
                "500 U.S. 100": {
                    "resolved_id": "12345",
                    "resolution_status": "resolved",
                    "confidence": 1.0,
                    "timestamp": "2026-01-01T00:00:00",
                    "resolver_version": "0.0.1",
                }
            },
        }
        path.write_text(json.dumps(data), encoding="utf-8")

        cache = CitationCache(path)
        # Should be empty due to version mismatch
        assert cache.get("500 U.S. 100") is None
        assert len(cache) == 0

    def test_hit_rate(self, tmp_path):
        cache = CitationCache(tmp_path / "cache.json")
        entry = CacheEntry("id", "resolved", 1.0, "ts", "1.0.0")
        cache.put("500 U.S. 100", entry)

        cache.get("500 U.S. 100")  # hit
        cache.get("999 F.3d 1")  # miss
        assert cache.hit_rate() == pytest.approx(0.5)

    def test_corrupt_cache_handled(self, tmp_path):
        path = tmp_path / "cache.json"
        path.write_text("not valid json {{{", encoding="utf-8")
        cache = CitationCache(path)
        assert len(cache) == 0


# ============================================================================
# BudgetTracker
# ============================================================================


class TestBudgetTracker:
    def test_initial_budget_available(self):
        bt = BudgetTracker(budget_per_build=100, budget_per_hour=100)
        assert bt.can_spend(1) is True
        assert bt.can_spend(100) is True

    def test_build_budget_exhausted(self):
        bt = BudgetTracker(budget_per_build=5, budget_per_hour=1000)
        bt.spend(5)
        assert bt.can_spend(1) is False

    def test_hourly_budget_exhausted(self):
        bt = BudgetTracker(budget_per_build=1000, budget_per_hour=3)
        bt.spend(3)
        assert bt.can_spend(1) is False

    def test_daily_ceiling(self):
        bt = BudgetTracker(budget_per_build=100_000, budget_per_hour=100_000, daily_ceiling=10)
        bt.spend(10)
        assert bt.can_spend(1) is False

    def test_spend_increments(self):
        bt = BudgetTracker(budget_per_build=100, budget_per_hour=100)
        bt.spend(3)
        assert bt.build_count == 3
        bt.spend(2)
        assert bt.build_count == 5


# ============================================================================
# _evaluate_results
# ============================================================================


class TestEvaluateResults:
    def test_single_exact_match(self):
        results = [
            {
                "cluster_id": 12345,
                "citation": ["500 U.S. 100", "111 S.Ct. 1000"],
            }
        ]
        cluster_id, conf, reason = _evaluate_results("500 U.S. 100", results, 0.90)
        assert cluster_id == "12345"
        assert conf == 1.0
        assert reason is None

    def test_no_results(self):
        cluster_id, conf, reason = _evaluate_results("500 U.S. 100", [], 0.90)
        assert cluster_id is None
        assert reason == "no_match"

    def test_ambiguous_multiple_exact(self, mock_cl_response_ambiguous):
        results = mock_cl_response_ambiguous["results"]
        cluster_id, conf, reason = _evaluate_results("500 U.S. 100", results, 0.90)
        assert cluster_id is None
        assert reason == "low_confidence_or_ambiguous"

    def test_no_exact_match_in_citations(self):
        results = [
            {
                "cluster_id": 99999,
                "citation": ["5 Cl.Ct. 349", "other cite"],
            }
        ]
        cluster_id, conf, reason = _evaluate_results("500 U.S. 349", results, 0.90)
        assert cluster_id is None
        assert reason == "low_confidence_or_ambiguous"

    def test_single_result_no_citation_field(self):
        results = [{"cluster_id": 12345}]
        cluster_id, conf, reason = _evaluate_results("500 U.S. 100", results, 0.90)
        assert cluster_id is None


# ============================================================================
# resolve_citations (integration with mocked API)
# ============================================================================


class TestResolveCitations:
    def test_cache_hit_no_api_call(self, resolver_config):
        cache = CitationCache(resolver_config.cache_path)
        cache.put(
            "500 U.S. 100",
            CacheEntry("12345", "resolved", 1.0, "ts", "1.0.0"),
        )
        budget = BudgetTracker(100, 50)
        session = MagicMock()

        cite = ExtractedCitation(
            original_text="500 U.S. 100",
            start=0,
            end=12,
            target_type="case",
            normalized="500 U.S. 100",
        )

        enriched, case_ids, metrics = resolve_citations([cite], session, resolver_config, cache, budget)
        assert metrics.cache_hits == 1
        assert metrics.api_calls == 0
        assert cite.resolved_id == "12345"
        assert cite.resolution_status == "resolved"
        assert "12345" in case_ids
        # No API calls should have been made
        session.get.assert_not_called()

    def test_uncached_resolution(self, resolver_config, mock_cl_response_single):
        cache = CitationCache(resolver_config.cache_path)
        budget = BudgetTracker(100, 50)
        session = MagicMock()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_cl_response_single
        session.get.return_value = mock_response

        cite = ExtractedCitation(
            original_text="500 U.S. 100 (1990)",
            start=0,
            end=20,
            target_type="case",
            normalized="500 U.S. 100",
        )

        enriched, case_ids, metrics = resolve_citations([cite], session, resolver_config, cache, budget)
        assert metrics.api_calls == 1
        assert cite.resolved_id == "12345"
        assert cite.resolution_status == "resolved"
        assert cite.resolved_source == "courtlistener_api"
        assert "12345" in case_ids

        # Verify cached for next time
        cached = cache.get("500 U.S. 100")
        assert cached is not None
        assert cached.resolved_id == "12345"

    def test_budget_exceeded(self, resolver_config):
        cache = CitationCache(resolver_config.cache_path)
        budget = BudgetTracker(budget_per_build=0, budget_per_hour=50)  # zero budget
        session = MagicMock()

        cite = ExtractedCitation(
            original_text="500 U.S. 100",
            start=0,
            end=12,
            target_type="case",
            normalized="500 U.S. 100",
        )

        enriched, case_ids, metrics = resolve_citations([cite], session, resolver_config, cache, budget)
        assert metrics.budget_exceeded_count == 1
        assert cite.excluded_reason == "api_budget_exceeded"
        assert len(case_ids) == 0
        session.get.assert_not_called()

    def test_empty_input(self, resolver_config):
        cache = CitationCache(resolver_config.cache_path)
        budget = BudgetTracker(100, 50)
        session = MagicMock()

        enriched, case_ids, metrics = resolve_citations([], session, resolver_config, cache, budget)
        assert enriched == []
        assert case_ids == []
        assert metrics.total_submitted == 0

    def test_no_match_produces_unresolved(self, resolver_config, mock_cl_response_empty):
        cache = CitationCache(resolver_config.cache_path)
        budget = BudgetTracker(100, 50)
        session = MagicMock()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_cl_response_empty
        session.get.return_value = mock_response

        cite = ExtractedCitation(
            original_text="999 F.3d 9999",
            start=0,
            end=14,
            target_type="case",
            normalized="999 F.3d 9999",
        )

        enriched, case_ids, metrics = resolve_citations([cite], session, resolver_config, cache, budget)
        assert cite.resolution_status == "unresolved"
        assert cite.excluded_reason == "no_match"
        assert len(case_ids) == 0

    def test_deduplicates_normalized(self, resolver_config, mock_cl_response_single):
        """Same normalized citation appearing twice should only make one API call."""
        cache = CitationCache(resolver_config.cache_path)
        budget = BudgetTracker(100, 50)
        session = MagicMock()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_cl_response_single
        session.get.return_value = mock_response

        cite1 = ExtractedCitation(
            original_text="500 U.S. 100 (1990)",
            start=0,
            end=20,
            target_type="case",
            normalized="500 U.S. 100",
        )
        cite2 = ExtractedCitation(
            original_text="500 U.S. 100",
            start=50,
            end=62,
            target_type="case",
            normalized="500 U.S. 100",
        )

        enriched, case_ids, metrics = resolve_citations([cite1, cite2], session, resolver_config, cache, budget)
        assert metrics.api_calls == 1  # only one API call despite two citations
        assert cite1.resolved_id == "12345"
        assert cite2.resolved_id == "12345"


# ============================================================================
# citation_to_target_dict
# ============================================================================


class TestCitationToTargetDict:
    def test_resolved_citation(self):
        cite = ExtractedCitation(
            original_text="500 U.S. 100 (1990)",
            start=0,
            end=20,
            target_type="case",
            normalized="500 U.S. 100",
            resolution_status="resolved",
            resolved_id="12345",
            resolved_source="courtlistener_api",
            confidence=1.0,
        )
        d = citation_to_target_dict(cite)
        assert d["original_text"] == "500 U.S. 100 (1990)"
        assert d["normalized"] == "500 U.S. 100"
        assert d["target_type"] == "case"
        assert d["resolution_status"] == "resolved"
        assert d["resolved_id"] == "12345"
        assert d["confidence"] == 1.0

    def test_unresolved_citation(self):
        cite = ExtractedCitation(
            original_text="999 F.3d 9999",
            start=0,
            end=14,
            target_type="case",
            normalized="999 F.3d 9999",
            resolution_status="unresolved",
            excluded_reason="no_match",
        )
        d = citation_to_target_dict(cite)
        assert d["resolution_status"] == "unresolved"
        assert d["excluded_reason"] == "no_match"
        assert d["resolved_id"] is None

"""Tests for legallm.downstream_eval (item 10: resolver % + BM25 Recall@k on method spans). Offline."""

import json
from pathlib import Path

import pandas as pd
import pytest

from legallm.citation_resolver import CitationCache
from legallm.downstream_eval import (
    QUERY_BUILDERS,
    build_query,
    format_downstream,
    load_modeling_split,
    main,
    run_downstream,
    span_cites,
    spans_from_run,
)
from legallm.extraction_eval import run_eval
from legallm.results_page import render_results
from legallm.schema import FactsExtraction, FactsSpan

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "xeval_smoke"
GOLD = FIXTURES / "gold_smoke.jsonl"

CITES = {
    "500 U.S. 100": "1001",
    "123 F.3d 456": "1002",
    "789 F.2d 1": "1003",
    "42 U.S. 7": None,  # cached, unresolved
}


def _cache(tmp_path: Path) -> Path:
    entries = {
        norm: {
            "resolved_id": rid,
            "resolution_status": "resolved" if rid else "unresolved",
            "confidence": 0.95 if rid else None,
            "timestamp": "2026-04-05T00:00:00+00:00",
            "resolver_version": "1.0.0",
        }
        for norm, rid in CITES.items()
    }
    p = tmp_path / "citation_cache.json"
    p.write_text(
        json.dumps({"resolver_version": "1.0.0", "entry_count": len(entries), "entries": entries}), encoding="utf-8"
    )
    return p


def _parquet(tmp_path: Path) -> Path:
    """A tiny pipeline parquet: 14 distinct training briefs whose facts mention the cited cases' topics."""
    rows = []
    topics = [
        ("tenant lease eviction landlord apartment rent", ["1001"]),
        ("patent infringement claim construction software", ["1002"]),
        ("employment discrimination termination retaliation", ["1003"]),
        ("tenant lease landlord notice rent deposit", ["1001", "1003"]),
        ("patent prior art obviousness software license", ["1002"]),
        ("contract breach damages delivery goods", ["1003"]),
        ("tenant eviction notice landlord habitability", ["1001"]),
        ("securities fraud disclosure investors shares", ["1002", "1003"]),
        ("employment wage overtime hours retaliation", ["1003"]),
        ("lease rent arrears eviction landlord tenant", ["1001"]),
        ("patent claim software infringement damages", ["1002"]),
        ("insurance policy coverage denial claim", ["1003"]),
        ("tenant landlord lease renewal eviction", ["1001"]),
        ("copyright software license infringement", ["1002"]),
    ]
    for i, (text, targets) in enumerate(topics):
        body = (" ".join([text] * 6) + f" distinct filler {i} " + " ".join(f"w{i}{j}" for j in range(12))).strip()
        rows.append(
            {
                "search_result_id": 5000 + i,
                "build_id": "test",
                "facts_text_masked": body,
                "targets_case_ids": json.dumps(targets),
                "doc_type_id": "UNKNOWN",
            }
        )
    p = tmp_path / "facts.parquet"
    pd.DataFrame(rows).to_parquet(p, index=False)
    return p


def _fake_llm(doc_text: str, doc_type_id: str) -> FactsExtraction:
    """Facts span = the rules span; on brief_a it appends the sentence that carries the citations."""
    from legallm.baseline_adapter import extract_rules

    ex = extract_rules(doc_text, doc_type_id)
    span = ex.facts_span
    if span is not None and "500 U.S. 100" in doc_text:
        end = doc_text.index("500 U.S. 100") + len("500 U.S. 100 (1991)")
        end = max(end, span.end)
        span = FactsSpan(start=span.start, end=end, text=doc_text[span.start : end])
    return FactsExtraction(**{**ex.model_dump(), "facts_span": span, "extractor_version": "llm-fake"})


class TestSpanCites:
    def test_cache_lookup_only(self, tmp_path):
        cache = CitationCache(_cache(tmp_path))
        text = (
            "Tenant sued. See Smith v. Jones, 500 U.S. 100 (1991); Doe v. Roe, 123 F.3d 456 (9th Cir. 1997); "
            "Foo v. Bar, 42 U.S. 7 (1800); Never v. Seen, 999 F.3d 999 (2020); 500 U.S. 100 again."
        )
        st = span_cites(text, cache)
        assert st.n_case_cites == 5
        assert st.n_resolved == 2 and sorted(st.targets) == ["1001", "1002"]
        assert st.n_cached_unresolved == 1 and st.n_uncached == 1
        assert span_cites("", cache).n_unique == 0
        assert cache._misses >= 1  # a miss is counted, never fetched


class TestRun:
    @pytest.fixture
    def run_dir(self, tmp_path):
        return run_eval(
            gold_path=GOLD,
            methods=["rules_v2", "llm-fake"],
            subset="all",
            runs_dir=tmp_path / "runs",
            cache_dir=None,
            extractors={"llm-fake": _fake_llm},
        )

    def test_spans_from_run(self, run_dir):
        spans, ref = spans_from_run(run_dir, ["rules_v2", "llm-fake"])
        assert set(spans) == {"rules_v2", "llm-fake"} and len(spans["rules_v2"]) == 3
        assert ref["s001"]["is_gold"] and ref["s001"]["reference_span"] == [117, 1125]

    def test_split_cache(self, tmp_path):
        pq = _parquet(tmp_path)
        sc = tmp_path / "split.parquet"
        df = load_modeling_split(pq, split_cache=sc)
        assert sc.exists() and set(df["split"]) <= {"train", "val", "test"}
        assert all(isinstance(v, str) for v in df["search_result_id"])  # strings, to match gold ids
        df2 = load_modeling_split(pq, split_cache=sc)
        assert len(df2) == len(df)

    def test_run_downstream_end_to_end(self, tmp_path, run_dir):
        pq, cache = _parquet(tmp_path), _cache(tmp_path)
        texts = {}
        for line in GOLD.read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            texts[r["gold_id"]] = (Path(r["pdf_path"])).read_text(encoding="utf-8")
        # make the gold span of s001 carry two resolvable citations so a retrieval query exists
        # (fixture brief_a's citations sit inside the rules/gold span already).
        out = run_downstream(
            run_dir,
            methods=["rules_v2", "llm-fake"],
            gold_path=GOLD,
            parquet=pq,
            cache_path=cache,
            split_cache=tmp_path / "split.parquet",
            k=10,
            doc_texts=texts,
        )
        assert out["meta"]["methods"] == ["rules_v2", "llm-fake", "gold"]
        assert out["meta"]["network"].startswith("none")
        S = out["summaries"]
        for m in ("rules_v2", "llm-fake", "gold"):
            s = S[m]
            assert s["n_docs"] == 3 and 0 <= s["docs_resolved_ge1_rate"] <= 1
            assert s["n_unique_cites"] == s["n_resolved"] + s["n_cached_unresolved"] + s["n_uncached"]
        # the gold span is its own target reference: precision and recall 1.0 where it has targets
        assert S["gold"]["target_precision"] == 1.0 and S["gold"]["target_recall"] == 1.0
        assert out["meta"]["n_queries"] >= 1 and S["gold"]["recall@10"] is not None
        assert out["baseline"]["n_train_minus_gold"] == out["baseline"]["n_train"]  # fixture ids not in parquet
        assert out["comparisons"] and out["comparisons"][0]["a"] == "rules_v2"
        # files written
        assert (run_dir / "downstream.json").exists() and (run_dir / "downstream_per_doc.jsonl").exists()
        md = (run_dir / "downstream.md").read_text(encoding="utf-8")
        assert "## Citation resolution" in md and "## BM25 retrieval" in md
        assert format_downstream(out) == md
        # results page picks the section up
        page = render_results(run_dir)
        assert "## Downstream: citation resolution and BM25 retrieval" in page
        assert "| docs with ≥ 1 resolved citation |" in page

    def test_cli(self, tmp_path, run_dir, capsys, monkeypatch):
        pq, cache = _parquet(tmp_path), _cache(tmp_path)
        # gold pdf_paths are repo-relative .txt fixtures; document_text handles .txt
        monkeypatch.chdir(Path(__file__).resolve().parent.parent)
        rc = main(
            [
                "--run",
                str(run_dir),
                "--methods",
                "rules_v2",
                "llm-fake",
                "--gold",
                str(GOLD),
                "--parquet",
                str(pq),
                "--cache",
                str(cache),
                "--split-cache",
                str(tmp_path / "split.parquet"),
            ]
        )
        assert rc == 0
        out = capsys.readouterr().out
        assert "rules_v2:" in out and "gold:" in out and "downstream.md" in out


class TestQueryBuilders:
    def _ex(self):
        from legallm.schema import FactsExtraction, FactsSpan, KeyEvent

        return FactsExtraction(
            extractor_version="t",
            confidence="high",
            facts_span=FactsSpan(start=0, end=5, text="abcde"),
            parties=["Tenant", "Landlord"],
            procedural_posture="Appeal from an eviction judgment.",
            key_events=[KeyEvent(date="2020", text="lease signed"), KeyEvent(date=None, text="rent unpaid")],
        )

    def test_builders(self):
        span = "The tenant sued. See Smith v. Jones, 500 U.S. 100 (1991). Rent was unpaid."
        ex = self._ex()
        assert "500 U.S. 100" not in build_query("narrative", span, None)
        assert build_query("fields", span, None) is None  # no extraction -> not applicable
        f = build_query("fields", span, ex)
        assert f.startswith("Appeal from an eviction judgment. lease signed rent unpaid Tenant Landlord")
        assert build_query("fields3", span, ex).count("eviction") == 3
        assert build_query("fields+narrative", span, ex).endswith("Rent was unpaid.")
        assert build_query("events", span, ex) == "lease signed rent unpaid"
        with pytest.raises(KeyError):
            build_query("nope", span, ex)
        assert "narrative" in QUERY_BUILDERS and len(QUERY_BUILDERS) == 7

    def test_run_with_builders(self, tmp_path):
        from legallm.extraction_eval import run_eval

        run_dir = run_eval(
            gold_path=GOLD,
            methods=["rules_v2", "llm-fake"],
            subset="all",
            runs_dir=tmp_path / "runs",
            cache_dir=None,
            extractors={"llm-fake": _fake_llm},
        )
        texts = {}
        for line in GOLD.read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            texts[r["gold_id"]] = Path(r["pdf_path"]).read_text(encoding="utf-8")
        exs = {"llm-fake": {g: self._ex() for g in texts}}
        out = run_downstream(
            run_dir,
            methods=["rules_v2", "llm-fake"],
            gold_path=GOLD,
            parquet=_parquet(tmp_path),
            cache_path=_cache(tmp_path),
            split_cache=tmp_path / "split.parquet",
            doc_texts=texts,
            query_builders=QUERY_BUILDERS,
            extractions=exs,
        )
        qb = out["query_builders"]
        assert set(qb) == {"llm-fake"} and set(qb["llm-fake"]) == set(QUERY_BUILDERS)
        r = qb["llm-fake"]["fields3"]
        assert r["n"] == out["meta"]["n_queries"] and r["wins"] + r["ties"] + r["losses"] == r["n"]
        assert qb["llm-fake"]["narrative"]["wins"] == 0 and qb["llm-fake"]["narrative"]["losses"] == 0
        md = (run_dir / "downstream.md").read_text(encoding="utf-8")
        assert "## Query builders (plan 1A)" in md and "| llm-fake |" in md

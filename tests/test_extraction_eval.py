"""Tests for legallm.extraction_eval (C6 metrics + C7 harness). Offline; LLM methods use fake extractors."""

import json
from pathlib import Path

import pytest

from legallm.extraction_eval import (
    DocEval,
    ExtractionCache,
    agreement,
    auto_rating,
    compare,
    evaluate_doc,
    gold_reference,
    main,
    run_eval,
    run_method,
    select_records,
    span_iou,
    stratify,
    summarize,
)
from legallm.gold import GoldRecord, load_gold, set_label
from legallm.schema import FactsExtraction, FactsSpan

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "xeval_smoke"
GOLD = FIXTURES / "gold_smoke.jsonl"


class TestPrimitives:
    def test_span_iou(self):
        assert span_iou([0, 10], [0, 10]) == 1.0
        assert span_iou([0, 10], [5, 15]) == pytest.approx(5 / 15)
        assert span_iou([0, 10], [20, 30]) == 0.0
        assert span_iou(None, None) == 1.0
        assert span_iou([0, 10], None) == 0.0 and span_iou(None, [0, 10]) == 0.0

    def test_auto_rating(self):
        assert auto_rating(0.95) == "correct"
        assert auto_rating(0.9) == "correct"
        assert auto_rating(0.6) == "partially_correct"
        assert auto_rating(0.2) == "incorrect"
        assert auto_rating(None) is None

    def test_gold_reference(self):
        rec = GoldRecord(gold_id="g1", search_result_id=1, source="audit_set", pdf_path="x", rules_span=[1, 9])
        assert gold_reference(rec) == ([1, 9], False)
        set_label(rec, rating="correct", has_facts=True, gold_span=[2, 8])
        assert gold_reference(rec) == ([2, 8], True)
        set_label(rec, rating="incorrect", has_facts=False, gold_span=None)
        assert gold_reference(rec) == (None, True)


def _ex(span, **kw) -> FactsExtraction:
    base = dict(extractor_version="fake-v0", confidence="high")
    base.update(kw)
    return FactsExtraction(
        facts_span=FactsSpan(start=span[0], end=span[1], text="x" * (span[1] - span[0])) if span else None, **base
    )


class TestEvaluateDoc:
    def test_labeled_doc_metrics(self):
        doc = "x" * 100
        rec = GoldRecord(
            gold_id="g1",
            search_result_id=1,
            source="audit_set",
            pdf_path="x",
            rules_span=[0, 50],
            stratum={"confidence": "low"},
        )
        set_label(rec, rating="partially_correct", has_facts=True, gold_span=[10, 50])
        ex = _ex(
            [10, 50],
            case_citations=["not in doc"],
            provenance={
                "backend": "claude-cli",
                "model_id": "m",
                "prompt_sha": "p",
                "cost_usd": 0.01,
                "latency_s": 2.0,
            },
        )
        d = evaluate_doc(rec, "fake", ex, doc)
        assert d.is_gold and d.iou == 1.0 and d.auto_rating == "correct" and d.human_rating == "partially_correct"
        assert d.validation_ok is False and d.citation_fidelity == 0.0 and "unsupported_citation:not in doc" in d.flags
        assert d.backend == "claude-cli" and d.cost_usd == 0.01 and d.latency_s == 2.0

    def test_unlabeled_doc_uses_rules_span_as_agreement_reference(self):
        rec = GoldRecord(gold_id="g1", search_result_id=1, source="audit_set", pdf_path="x", rules_span=[0, 50])
        d = evaluate_doc(rec, "fake", _ex([0, 50]), "x" * 60)
        assert not d.is_gold and d.iou == 1.0

    def test_extractor_error(self):
        rec = GoldRecord(gold_id="g1", search_result_id=1, source="audit_set", pdf_path="x", rules_span=[0, 50])
        set_label(rec, rating="correct", has_facts=True, gold_span=[0, 50])
        d = evaluate_doc(rec, "fake", None, "x" * 60, error="boom")
        assert d.error == "boom" and d.iou == 0.0 and not d.span_found


class TestSummaries:
    def _evals(self):
        mk = lambda gid, src, iou, gold, hr, ar, flags=(), cost=None, has_facts=True, span=True: DocEval(  # noqa: E731
            gold_id=gid,
            search_result_id=1,
            source=src,
            stratum={"confidence": "low" if gid.endswith("1") else "high"},
            method="m",
            is_gold=gold,
            human_rating=hr,
            auto_rating=ar,
            iou=iou,
            gold_has_facts=has_facts,
            reference_span=[0, 1] if has_facts else None,
            span_found=span,
            validation_ok=not flags,
            flags=list(flags),
            cost_usd=cost,
            latency_s=1.0,
            citation_fidelity=0.5 if flags else None,
        )
        return [
            mk("g001", "audit_set", 0.95, True, "correct", "correct", cost=0.1),
            mk(
                "g002",
                "audit_set",
                0.6,
                True,
                "correct",
                "partially_correct",
                flags=("unsupported_citation:x",),
                cost=0.3,
            ),
            mk("g003", "audit_set", 0.2, False, None, "incorrect"),  # unlabeled: excluded from gold metrics
            mk("f001", "no_facts_span", 0.7, True, None, "partially_correct"),
            mk("f002", "no_facts_span", 1.0, True, None, "correct", has_facts=False, span=False),
        ]

    def test_summarize(self):
        s = summarize(self._evals())
        assert s["n_docs"] == 5 and s["n_gold"] == 4
        assert s["iou_mean"] == pytest.approx((0.95 + 0.6 + 0.7 + 1.0) / 4, abs=1e-4)
        assert s["iou_ge_0.9"] == 0.5 and s["iou_ge_0.5"] == 1.0
        assert s["validation_pass_rate"] == 0.8
        assert s["docs_with_unsupported_cites"] == 1 and s["n_docs_with_cites"] == 1
        assert s["recovered_span_rate"] == 1.0 and s["failure_stratum_n"] == 2
        assert s["failure_correct_no_facts_rate"] == 1.0
        assert s["auto_vs_human_n"] == 2 and s["auto_vs_human_agreement"] == 0.5
        assert s["auto_vs_human_confusion"] == {"correct->correct": 1, "correct->partially_correct": 1}
        assert s["cost_usd_per_doc"] == pytest.approx(0.2) and s["cost_usd_total"] == pytest.approx(0.4)
        assert s["flags"] == {"unsupported_citation": 1}

    def test_stratify_and_agreement_and_compare(self):
        ev = self._evals()
        by_src = stratify(ev, "source")
        assert set(by_src) == {"audit_set", "no_facts_span"} and by_src["no_facts_span"]["n_docs"] == 2
        by_conf = stratify(ev, "confidence")
        assert set(by_conf) == {"low", "high"}
        other = [DocEval(**{**d.to_dict(), "method": "o", "iou": (d.iou or 0) - 0.5, "pred_span": [0, 5]}) for d in ev]
        for d in ev:
            d.pred_span = [0, 10]
        ag = agreement(ev, other)
        assert ag["n"] == 5 and ag["iou_mean"] == 0.5
        c = compare(ev, other)
        assert c["n_pairs"] == 4 and c["losses"] == 4 and c["iou_delta_mean"] == pytest.approx(-0.5)
        assert c["worst_b"][0]["gold_id"] in {"f001", "g002"}


class TestRunMethodAndCache:
    def test_rules_over_fixture_gold(self):
        records = load_gold(GOLD)
        texts = {r.gold_id: Path(r.pdf_path).read_text(encoding="utf-8") for r in records}
        from legallm.baseline_adapter import preprocess_text
        from legallm.pipeline import normalize_text

        texts = {k: preprocess_text(normalize_text(v)) for k, v in texts.items()}
        evals = run_method(records, "rules_v2", texts, cache=None)
        by = {d.gold_id: d for d in evals}
        assert by["s001"].iou == 1.0 and by["s001"].auto_rating == "correct"  # gold == rules span
        assert by["s002"].iou < 1.0 and by["s002"].is_gold  # gold trims the heading rules kept
        assert by["s003"].pred_span is None and by["s003"].iou == 1.0  # no facts: both None

    def test_cache_hit_and_offline(self, tmp_path):
        records = load_gold(GOLD)
        texts = {r.gold_id: "x" * (100 + i) for i, r in enumerate(records)}  # distinct doc_sha1 per record
        calls = []

        def fake(doc_text, doc_type_id):
            calls.append(doc_type_id)
            return _ex([0, 10], provenance={"cost_usd": 0.5})

        cache = ExtractionCache(tmp_path / "cache")
        a = run_method(records, "fake", texts, cache=cache, extractor=fake, config_sha="cfg")
        b = run_method(records, "fake", texts, cache=cache, extractor=fake, config_sha="cfg")
        assert len(calls) == len(records) and all(d.cached for d in b) and not any(d.cached for d in a)
        c = run_method(records, "fake", texts, cache=cache, extractor=fake, config_sha="other", offline=True)
        assert all(d.error and "offline" in d.error for d in c)
        assert (tmp_path / "cache" / "fake.jsonl").exists()

    def test_extractor_exception_is_recorded(self):
        records = load_gold(GOLD)[:1]

        def boom(doc_text, doc_type_id):
            raise RuntimeError("no credits")

        d = run_method(records, "fake", {records[0].gold_id: "x"}, extractor=boom, config_sha="c")[0]
        assert d.error == "RuntimeError: no credits" and d.iou == 0.0


class TestSelectAndRunEval:
    def test_select_records(self):
        recs = load_gold(GOLD)
        assert len(select_records(recs, "labeled", None)) == 3
        assert len(select_records(recs, "smoke", 2)) == 2
        assert len(select_records(recs, "all", None)) == 3
        with pytest.raises(ValueError):
            select_records(recs, "bogus", None)

    def test_run_eval_writes_artifacts(self, tmp_path):
        def fake_llm(doc_text, doc_type_id):
            # mimic an LLM that finds the same span as rules but hallucinates a cite
            from legallm.baseline_adapter import extract_rules

            ex = extract_rules(doc_text, doc_type_id)
            return FactsExtraction(
                **{
                    **ex.model_dump(),
                    "extractor_version": "llm-fake",
                    "case_citations": ["999 U.S. 1"],
                    "provenance": {
                        "backend": "fake",
                        "model_id": "m",
                        "prompt_sha": "p",
                        "cost_usd": 0.02,
                        "latency_s": 1.5,
                    },
                }
            )

        out = run_eval(
            gold_path=GOLD,
            methods=["rules_v2", "llm-fake"],
            subset="smoke",
            runs_dir=tmp_path / "runs",
            cache_dir=tmp_path / "cache",
            extractors={"llm-fake": fake_llm},
        )
        assert (out / "per_doc.jsonl").exists() and (out / "summary.json").exists() and (out / "manifest.json").exists()
        report = (out / "report.md").read_text(encoding="utf-8")
        assert "| rules_v2 |" in report and "| llm-fake |" in report and "llm-fake vs rules_v2" in report
        rows = [json.loads(line) for line in (out / "per_doc.jsonl").read_text(encoding="utf-8").splitlines()]
        assert len(rows) == 6 and "text" not in json.dumps(rows)  # no brief text in tracked output
        summ = json.loads((out / "summary.json").read_text(encoding="utf-8"))
        assert summ["summaries"]["llm-fake"]["docs_with_unsupported_cites"] == 3  # the fake cites on every doc
        assert summ["summaries"]["llm-fake"]["cost_usd_total"] == pytest.approx(0.06)
        assert summ["agreements"][0]["n"] == 3

    def test_cli_smoke(self, tmp_path, capsys):
        rc = main(
            [
                "--gold",
                str(GOLD),
                "--methods",
                "rules_v2",
                "--subset",
                "smoke",
                "--runs-dir",
                str(tmp_path),
                "--no-cache",
                "--quiet",
            ]
        )
        out = capsys.readouterr().out
        assert rc == 0 and "# Extraction eval" in out and "run dir:" in out

    def test_cli_no_records(self, tmp_path, capsys):
        empty = tmp_path / "empty.jsonl"
        empty.write_text("", encoding="utf-8")
        assert main(["--gold", str(empty), "--subset", "labeled", "--runs-dir", str(tmp_path), "--quiet"]) == 2

"""Tests for legallm.judge (item 9 pulled forward). No network: the CLI runner / client is faked."""

import json
import subprocess
from pathlib import Path

import pytest

from legallm.claude_cli import ClaudeCliClient
from legallm.gold import GoldRecord, load_gold
from legallm.judge import (
    Judge,
    JudgeCache,
    JudgeConfig,
    Verdict,
    format_judge_report,
    judge_output_json_schema,
    main,
    mark_candidates,
    run_judge,
    spans_from_run,
    summarize_verdicts,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "xeval_smoke"
GOLD = FIXTURES / "gold_smoke.jsonl"


class TestMarking:
    def test_markers_inserted_in_order(self):
        doc = "0123456789"
        m = mark_candidates(doc, {"A": [2, 5], "B": [4, 8]})
        assert m.replace("\n⟦A⟧ ", "").replace(" ⟦/A⟧\n", "").replace("\n⟦B⟧ ", "").replace(" ⟦/B⟧\n", "") == doc
        assert m.index("⟦A⟧") < m.index("⟦B⟧") < m.index("⟦/A⟧") < m.index("⟦/B⟧")

    def test_none_candidate_not_marked(self):
        assert "⟦B⟧" not in mark_candidates("abc", {"A": [0, 1], "B": None})

    def test_identical_spans(self):
        m = mark_candidates("abcdef", {"A": [1, 4], "B": [1, 4]})
        assert m.count("⟦") == 4 and "bcd" in m

    def test_schema_strict(self):
        s = judge_output_json_schema()
        assert s["additionalProperties"] is False and "$ref" not in json.dumps(s)
        assert set(s["required"]) == set(s["properties"])


def _verdict_json(**over):
    body = {
        "document_kind": "merits_brief",
        "is_brief_with_facts": True,
        "candidate_a": {
            "rating": "partially_correct",
            "issues": ["includes_cover_or_toc"],
            "comment": "starts at cover",
        },
        "candidate_b": {"rating": "correct", "issues": ["fine"], "comment": "clean"},
        "preferred": "B",
        "corrected_start_anchor": None,
        "corrected_end_anchor": None,
        "confidence": "high",
        "summary": "B is right; A includes the cover page.",
    }
    body.update(over)
    return body


class FakeRun:
    def __init__(self, payload):
        self.payload = payload
        self.calls = 0

    def __call__(self, argv, **kw):
        self.calls += 1
        res = {
            "is_error": False,
            "structured_output": self.payload,
            "modelUsage": {"claude-opus-5": {"inputTokens": 100, "outputTokens": 50}},
            "total_cost_usd": 0.05,
            "session_id": "s",
        }
        return subprocess.CompletedProcess(argv, 0, stdout=json.dumps(res), stderr="")


def _judge(payload):
    run = FakeRun(payload)
    return Judge(JudgeConfig(), client=ClaudeCliClient(exe="claude", run=run)), run


class TestJudge:
    def test_request_marks_both_candidates_and_uses_opus(self):
        j, _ = _judge(_verdict_json())
        req, _ = j.build_request("abcdefghij", "UNKNOWN", {"A": [1, 4], "B": [2, 6]}, {"A": "rules_v2", "B": "llm-v2"})
        assert req["model"] == "claude-opus-5" and req["output_config"]["effort"] == "high"
        body = req["messages"][0]["content"]
        assert "⟦A⟧" in body and "⟦/B⟧" in body and "A = rules_v2" in body

    def test_verdict_fields_and_cost(self):
        j, run = _judge(_verdict_json())
        rec = GoldRecord(gold_id="g1", search_result_id=1, source="audit_set", pdf_path="x", rules_span=[0, 5])
        v = j.judge(
            rec,
            "STATEMENT OF FACTS\nOn Jan 1 the plaintiff sued.\nARGUMENT\nNo.",
            {"A": [0, 5], "B": [19, 46]},
            {"A": "rules_v2", "B": "llm-v2"},
        )
        assert v.error is None and v.rating_a == "partially_correct" and v.rating_b == "correct"
        assert v.issues_a == ["includes_cover_or_toc"] and v.preferred == "B" and v.confidence == "high"
        assert v.cost_usd == 0.05 and v.judge_model == "claude-opus-5" and v.corrected_span is None

    def test_corrected_anchors_are_located(self):
        doc = "STATEMENT OF FACTS\nOn Jan 1 the plaintiff sued Acme. It lost.\nARGUMENT\nNo."
        j, _ = _judge(
            _verdict_json(
                candidate_a={"rating": "incorrect", "issues": ["wrong_section"], "comment": "argument"},
                candidate_b={"rating": "incorrect", "issues": ["span_empty"], "comment": "none"},
                preferred="neither",
                corrected_start_anchor="On Jan 1 the plaintiff",
                corrected_end_anchor="Acme. It lost.",
            )
        )
        rec = GoldRecord(gold_id="g1", search_result_id=1, source="audit_set", pdf_path="x")
        v = j.judge(rec, doc, {"A": [60, 70], "B": None}, {"A": "rules_v2", "B": "llm-v2"})
        assert v.corrected_span is not None
        assert doc[v.corrected_span[0] : v.corrected_span[1]] == "On Jan 1 the plaintiff sued Acme. It lost."

    def test_schema_violation_is_an_error_not_a_crash(self):
        j, _ = _judge({"document_kind": "merits_brief"})  # missing required fields
        rec = GoldRecord(gold_id="g1", search_result_id=1, source="audit_set", pdf_path="x")
        v = j.judge(rec, "text", {"A": None, "B": None}, {"A": "a", "B": "b"})
        assert v.error and v.error.startswith("schema")


class TestRunAndReport:
    def test_run_judge_with_cache(self, tmp_path):
        records = load_gold(GOLD)
        spans = {
            "rules_v2": {r.gold_id: r.rules_span for r in records},
            "llm-v2": {r.gold_id: r.rules_span for r in records},
        }
        j, run = _judge(_verdict_json())
        cache = JudgeCache(tmp_path / "jc", "claude-opus-5")
        a = run_judge(records, spans, ["rules_v2", "llm-v2"], judge=j, cache=cache)
        b = run_judge(records, spans, ["rules_v2", "llm-v2"], judge=j, cache=cache)
        assert run.calls == len(records) and all(v.cached for v in b) and not any(v.cached for v in a)
        s = summarize_verdicts(a)
        assert s["n"] == 3 and s["n_errors"] == 0
        assert s["rating_b"]["audit_set"]["correct"] == 2
        report = format_judge_report(
            {
                "run_id": "t",
                "model": "m",
                "version": "judge-v1",
                "prompt_sha": "p",
                "effort": "high",
                "backend": "claude-cli",
            },
            s,
            ["rules_v2", "llm-v2"],
        )
        assert "## Ratings by source" in report and "| includes_cover_or_toc |" in report

    def test_two_methods_required(self):
        with pytest.raises(ValueError):
            run_judge([], {}, ["a"])

    def test_spans_from_run(self, tmp_path):
        run = tmp_path / "run"
        run.mkdir()
        (run / "per_doc.jsonl").write_text(
            json.dumps({"gold_id": "s001", "method": "rules_v2", "pred_span": [1, 2]})
            + "\n"
            + json.dumps({"gold_id": "s001", "method": "llm-v2", "pred_span": None})
            + "\n",
            encoding="utf-8",
        )
        sp = spans_from_run(run, ["rules_v2", "llm-v2"])
        assert sp["rules_v2"]["s001"] == [1, 2] and sp["llm-v2"]["s001"] is None

    def test_glaring_list(self):
        v = Verdict(
            gold_id="g1",
            search_result_id=1,
            source="audit_set",
            method_a="a",
            method_b="b",
            span_a=[0, 1],
            span_b=None,
            is_brief_with_facts=False,
            rating_a="incorrect",
            rating_b="correct",
            document_kind="reply_brief",
            summary="no facts",
        )
        s = summarize_verdicts([v])
        assert s["glaring"][0]["gold_id"] == "g1"

    def test_cli(self, tmp_path, monkeypatch, capsys):
        run = tmp_path / "run"
        run.mkdir()
        recs = load_gold(GOLD)
        lines = [
            json.dumps({"gold_id": r.gold_id, "method": m, "pred_span": r.rules_span})
            for r in recs
            for m in ("rules_v2", "llm-v2")
        ]
        (run / "per_doc.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
        import legallm.judge as mod

        fake = FakeRun(_verdict_json())
        monkeypatch.setattr(
            mod, "Judge", lambda cfg=None, client=None: Judge(cfg, client=ClaudeCliClient(exe="claude", run=fake))
        )
        rc = main(
            [
                "--run",
                str(run),
                "--gold",
                str(GOLD),
                "--out-dir",
                str(tmp_path / "out"),
                "--cache-dir",
                str(tmp_path / "jc"),
                "--quiet",
                "--label",
                "t",
            ]
        )
        assert rc == 0
        outs = list((tmp_path / "out").glob("t_*.jsonl"))
        assert len(outs) == 1 and len(outs[0].read_text(encoding="utf-8").splitlines()) == 3
        assert "Judge report" in capsys.readouterr().out

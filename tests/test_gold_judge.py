"""Tests for judge pre-labels in the gold set: prefill, accept policies, labeler filters."""

import json

import pytest

from legallm.extraction_eval import select_records
from legallm.gold import (
    GoldRecord,
    accept_judge,
    accept_policy,
    load_gold,
    load_verdicts,
    main,
    prefill,
    save_gold,
    set_label,
    stats,
    suggestion_from_verdict,
)


def _verdict(
    gid,
    *,
    src="audit_set",
    has=True,
    ra="correct",
    rb="correct",
    span_a=(10, 50),
    span_b=(12, 50),
    corrected=None,
    conf="high",
    kind="merits_brief",
):
    return {
        "gold_id": gid,
        "search_result_id": 1,
        "source": src,
        "method_a": "rules_v2",
        "method_b": "llm-v2",
        "span_a": list(span_a) if span_a else None,
        "span_b": list(span_b) if span_b else None,
        "document_kind": kind,
        "is_brief_with_facts": has,
        "rating_a": ra,
        "issues_a": ["fine"] if ra == "correct" else ["includes_cover_or_toc"],
        "comment_a": "a",
        "rating_b": rb,
        "issues_b": ["fine"],
        "comment_b": "b",
        "preferred": "B",
        "corrected_span": corrected,
        "corrected_notes": [],
        "confidence": conf,
        "summary": "sum",
        "judge_model": "claude-opus-5",
        "judge_version": "judge-v1",
        "prompt_sha": "p",
        "cost_usd": 0.1,
        "latency_s": 1.0,
        "cached": False,
        "error": None,
    }


def _rec(gid, src="audit_set", rules=(10, 50)):
    return GoldRecord(
        gold_id=gid, search_result_id=1, source=src, pdf_path="x", rules_span=list(rules) if rules else None
    )


class TestSuggestion:
    def test_rules_correct(self):
        s = suggestion_from_verdict(_verdict("g1"), "run")
        assert s["rules_rating"] == "correct" and s["suggested_span"] == [10, 50] and s["span_basis"] == "rules_span"
        assert s["llm_method"] == "llm-v2" and s["has_facts"] is True

    def test_llm_correct_when_rules_wrong(self):
        s = suggestion_from_verdict(_verdict("g1", ra="partially_correct"), "run")
        assert s["suggested_span"] == [12, 50] and s["span_basis"] == "llm-v2_span"

    def test_corrected_wins(self):
        s = suggestion_from_verdict(_verdict("g1", ra="incorrect", rb="incorrect", corrected=[20, 40]), "run")
        assert s["suggested_span"] == [20, 40] and s["span_basis"] == "judge_corrected"

    def test_no_facts(self):
        s = suggestion_from_verdict(
            _verdict("g1", has=False, ra="incorrect", rb="correct", span_b=None, kind="reply_brief"), "run"
        )
        assert s["has_facts"] is False and s["suggested_span"] is None

    def test_error_verdict_is_none(self):
        v = _verdict("g1")
        v["error"] = "boom"
        assert suggestion_from_verdict(v, "run") is None


class TestPrefillAndAccept:
    def test_prefill_only_pending_unless_overwrite(self):
        recs = [_rec("g1"), _rec("g2")]
        recs[1].suggestion = {"old": True}
        counts = prefill(recs, {"g1": _verdict("g1"), "g2": _verdict("g2")}, "run")
        assert counts == {"set": 1, "skipped_existing": 1, "missing_or_errored": 0}
        assert recs[0].suggestion["judge_run"] == "run" and recs[1].suggestion == {"old": True}
        prefill(recs, {"g2": _verdict("g2")}, "run2", overwrite=True)
        assert recs[1].suggestion["judge_run"] == "run2"

    def test_policies(self):
        recs = {
            "nb": _rec("nb"),
            "rc": _rec("rc"),
            "lc": _rec("lc"),
            "co": _rec("co"),
            "low": _rec("low"),
            "f": _rec("f", src="no_facts_span", rules=None),
        }
        vs = {
            "nb": _verdict("nb", has=False, ra="incorrect", rb="correct", span_b=None, kind="amicus_brief"),
            "rc": _verdict("rc"),
            "lc": _verdict("lc", ra="partially_correct"),
            "co": _verdict("co", ra="incorrect", rb="incorrect", corrected=[20, 40]),
            "low": _verdict("low", conf="medium"),
            "f": _verdict(
                "f",
                src="no_facts_span",
                has=False,
                ra="correct",
                rb="correct",
                span_a=None,
                span_b=None,
                kind="clerk_letter_or_notice",
            ),
        }
        prefill(list(recs.values()), vs, "run")
        allp = {"nonbrief", "rules_correct", "llm_correct", "corrected"}
        assert accept_policy(recs["nb"], allp) == "nonbrief"
        assert accept_policy(recs["rc"], allp) == "rules_correct"
        assert accept_policy(recs["lc"], allp) == "llm_correct"
        assert accept_policy(recs["co"], allp) == "corrected"
        assert accept_policy(recs["low"], allp) is None  # below min confidence
        assert accept_policy(recs["low"], allp, min_confidence="medium") == "rules_correct"
        assert accept_policy(recs["rc"], {"nonbrief"}) is None
        assert accept_policy(recs["f"], allp) == "nonbrief"

    def test_accept_applies_labels_and_respects_humans(self):
        recs = [_rec("nb"), _rec("rc"), _rec("h")]
        vs = {
            "nb": _verdict("nb", has=False, ra="incorrect", rb="correct", span_b=None, kind="reply_brief"),
            "rc": _verdict("rc"),
            "h": _verdict("h"),
        }
        prefill(recs, vs, "run")
        set_label(recs[2], rating="incorrect", has_facts=True, gold_span=[1, 5], labeler="noah")  # human first
        dry = accept_judge(recs, policies={"nonbrief", "rules_correct"}, dry_run=True)
        assert dry == {"nonbrief": 1, "rules_correct": 1} and recs[0].status == "pending"
        counts = accept_judge(recs, policies={"nonbrief", "rules_correct"})
        assert counts == {"nonbrief": 1, "rules_correct": 1}
        nb, rc, h = recs
        assert nb.status == "labeled" and nb.label.has_facts is False and nb.label.rating == "incorrect"
        assert nb.label.labeler == "judge:claude-opus-5" and nb.label.notes.startswith("[judge:nonbrief]")
        assert rc.label.rating == "correct" and rc.label.gold_span == [10, 50] and rc.label.has_facts is True
        assert not nb.is_human_labeled and h.is_human_labeled and h.label.labeler == "noah"
        st = stats(recs)
        assert st["by_labeler"] == {"human": 1, "judge": 2} and st["with_suggestion"] == 3

    def test_select_records_labeler_filter(self):
        recs = [_rec("j"), _rec("h"), _rec("p")]
        set_label(recs[0], rating="correct", has_facts=True, gold_span=[10, 50], labeler="judge:claude-opus-5")
        set_label(recs[1], rating="correct", has_facts=True, gold_span=[10, 50], labeler="noah")
        assert {r.gold_id for r in select_records(recs, "labeled", None)} == {"j", "h"}
        assert {r.gold_id for r in select_records(recs, "labeled", None, labeler="human")} == {"h"}
        assert {r.gold_id for r in select_records(recs, "labeled", None, labeler="judge")} == {"j"}
        with pytest.raises(ValueError):
            select_records(recs, "labeled", None, labeler="martian")


class TestCli:
    def test_prefill_and_accept_cli(self, tmp_path, capsys):
        gold = tmp_path / "gold.jsonl"
        recs = [_rec("g1"), _rec("g2", src="no_facts_span", rules=None)]
        save_gold(recs, gold)
        jpath = tmp_path / "judge.jsonl"
        with open(jpath, "w", encoding="utf-8") as f:
            f.write(json.dumps(_verdict("g1")) + "\n")
            f.write(
                json.dumps(
                    _verdict(
                        "g2",
                        src="no_facts_span",
                        has=False,
                        ra="correct",
                        rb="correct",
                        span_a=None,
                        span_b=None,
                        kind="docket_sheet_or_form",
                    )
                )
                + "\n"
            )
        assert main(["--gold", str(gold), "prefill", "--judge", str(jpath)]) == 0
        assert all(r.suggestion for r in load_gold(gold))
        assert main(["--gold", str(gold), "accept-judge", "--policies", "nonbrief", "--dry-run"]) == 0
        assert {r.gold_id: r.status for r in load_gold(gold)} == {"g1": "pending", "g2": "pending"}
        assert main(["--gold", str(gold), "accept-judge", "--policies", "nonbrief", "rules_correct"]) == 0
        after = {r.gold_id: r for r in load_gold(gold)}
        assert after["g2"].status == "labeled" and after["g2"].label.has_facts is False
        assert after["g1"].status == "labeled" and after["g1"].label.gold_span == [10, 50]
        out = capsys.readouterr().out
        assert "labeled by: {'judge': 2}" in out
        assert load_verdicts(jpath)["g1"]["rating_a"] == "correct"

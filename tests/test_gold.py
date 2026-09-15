"""Tests for legallm.gold (C5 manifest + labels). Uses synthetic parquet/JSONL/PDFs in tmp_path."""

import json

import pandas as pd
import pytest

from legallm.gold import (
    GoldRecord,
    build_manifest,
    format_stats,
    load_gold,
    main,
    save_gold,
    set_label,
    stats,
    verify_all,
    verify_record,
    write_meta,
)


def _make_pdf(path, text):
    fitz = pytest.importorskip("fitz")
    doc = fitz.open()
    page = doc.new_page()
    y = 40
    for line in text.splitlines():
        page.insert_text((40, y), line, fontsize=8)
        y += 11
        if y > 780:
            page = doc.new_page()
            y = 40
    doc.save(str(path))
    doc.close()


@pytest.fixture
def corpus(tmp_path, sample_brief_text):
    pdf_dir = tmp_path / "pdfs"
    pdf_dir.mkdir()
    audit_ids = [101, 102, 103]
    fail_ids = [201, 202, 203, 204]
    for sid in audit_ids + fail_ids:
        _make_pdf(pdf_dir / f"{sid}.pdf", sample_brief_text)
    # audit parquet: rules spans copied from a real run on the same text
    from legallm.single_doc import extract_from_file

    r = extract_from_file(pdf_dir / "101.pdf", method="rules_v2")
    s, e = r.extraction.facts_span.start, r.extraction.facts_span.end
    df = pd.DataFrame(
        {
            "search_result_id": audit_ids,
            "pdf_url": [f"https://x/{i}.pdf" for i in audit_ids],
            "doc_type_id": ["UNKNOWN"] * 3,
            "extractor_confidence": ["high", "low", "medium"],
            "len_bin": ["short (<5K chars)"] * 3,
            "facts_start": [s] * 3,
            "facts_end": [e] * 3,
            "extractor_notes": ["", "fallback_pre_argument", ""],
            "extractor_method": ["rules_v2"] * 3,
        }
    )
    parquet = tmp_path / "audit.parquet"
    df.to_parquet(parquet, index=False)
    failures = tmp_path / "failures.jsonl"
    with open(failures, "w", encoding="utf-8") as f:
        for sid in fail_ids:
            f.write(
                json.dumps(
                    {
                        "reason": "no_facts_span",
                        "search_id": sid,
                        "pdf_url": f"https://x/{sid}.pdf",
                        "notes": ["no_span_found"],
                    }
                )
                + "\n"
            )
        f.write(json.dumps({"reason": "needs_ocr", "search_id": 999}) + "\n")
        f.write(json.dumps({"reason": "no_facts_span", "search_id": 101}) + "\n")  # already in audit set
        f.write(json.dumps({"reason": "no_facts_span", "search_id": 555}) + "\n")  # no local pdf
    return {"parquet": parquet, "failures": failures, "pdf_dir": pdf_dir, "span": [s, e]}


class TestBuild:
    def test_manifest_composition(self, corpus):
        recs = build_manifest(corpus["parquet"], corpus["failures"], corpus["pdf_dir"], n_failures=2, seed=42)
        assert [r.gold_id for r in recs][:3] == ["g001", "g002", "g003"]
        assert [r.source for r in recs].count("no_facts_span") == 2
        assert all(r.gold_id.startswith("f") for r in recs if r.source == "no_facts_span")
        ids = {r.search_result_id for r in recs}
        assert 101 in ids and 999 not in ids and 555 not in ids
        assert recs[0].rules_span == corpus["span"] and recs[0].stratum == {
            "confidence": "high",
            "len_bin": "short (<5K chars)",
        }
        assert recs[-1].rules_span is None and recs[-1].rules_notes == "no_span_found"
        assert all(r.status == "pending" for r in recs)

    def test_sampling_is_deterministic(self, corpus):
        a = build_manifest(corpus["parquet"], corpus["failures"], corpus["pdf_dir"], n_failures=2, seed=42)
        b = build_manifest(corpus["parquet"], corpus["failures"], corpus["pdf_dir"], n_failures=2, seed=42)
        c = build_manifest(corpus["parquet"], corpus["failures"], corpus["pdf_dir"], n_failures=2, seed=7)
        assert [r.search_result_id for r in a] == [r.search_result_id for r in b]
        assert len(c) == len(a)

    def test_verify_fills_sha_and_checks_bounds(self, corpus):
        recs = build_manifest(corpus["parquet"], corpus["failures"], corpus["pdf_dir"], n_failures=1)
        problems = verify_all(recs)
        assert problems == {}
        assert all(r.doc_sha1 and r.doc_chars for r in recs)
        recs[0].rules_span = [0, recs[0].doc_chars + 50]
        from legallm.gold import document_text

        assert verify_record(recs[0], document_text(recs[0].pdf_path)) == [
            f"rules_span [0, {recs[0].doc_chars + 50}] out of bounds for {recs[0].doc_chars} chars"
        ]
        recs[1].doc_sha1 = "deadbeef"
        assert "drift" in verify_record(recs[1], document_text(recs[1].pdf_path))[0]


class TestPersistence:
    def test_roundtrip_and_meta(self, corpus, tmp_path):
        recs = build_manifest(corpus["parquet"], corpus["failures"], corpus["pdf_dir"], n_failures=1)
        path = tmp_path / "gold" / "gold_v1.jsonl"
        save_gold(recs, path)
        meta = write_meta(path, recs, seed=42, n_failures=1)
        back = load_gold(path)
        assert back == recs
        m = json.loads(meta.read_text(encoding="utf-8"))
        assert m["n_audit_set"] == 3 and m["n_no_facts_span"] == 1 and m["seed"] == 42
        assert not (path.with_suffix(".jsonl.tmp")).exists()

    def test_no_text_in_file(self, corpus, tmp_path, sample_brief_text):
        recs = build_manifest(corpus["parquet"], corpus["failures"], corpus["pdf_dir"], n_failures=1)
        path = tmp_path / "gold_v1.jsonl"
        save_gold(recs, path)
        assert "Appellant filed a complaint" not in path.read_text(encoding="utf-8")


class TestLabels:
    def test_set_label_and_effective_span(self):
        rec = GoldRecord(gold_id="g001", search_result_id=1, source="audit_set", pdf_path="x.pdf", rules_span=[10, 50])
        assert rec.effective_span == [10, 50]
        set_label(rec, rating="partially_correct", has_facts=True, gold_span=[12, 48], notes="trim heading")
        assert rec.status == "labeled" and rec.label.rating == "partially_correct"
        assert rec.effective_span == [12, 48] and rec.label.labeled_at and rec.label.labeler == "noah"
        set_label(rec, rating="incorrect", has_facts=False, gold_span=None)
        assert rec.effective_span is None

    def test_bad_span_rejected(self):
        rec = GoldRecord(gold_id="f001", search_result_id=1, source="no_facts_span", pdf_path="x.pdf")
        with pytest.raises(ValueError):
            set_label(rec, rating=None, has_facts=True, gold_span=[50, 10])

    def test_bad_rating_rejected(self):
        rec = GoldRecord(gold_id="g001", search_result_id=1, source="audit_set", pdf_path="x.pdf")
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            set_label(rec, rating="meh", has_facts=True, gold_span=None)  # type: ignore[arg-type]

    def test_stats(self):
        recs = [
            GoldRecord(
                gold_id="g001", search_result_id=1, source="audit_set", pdf_path="a", stratum={"confidence": "low"}
            ),
            GoldRecord(
                gold_id="g002", search_result_id=2, source="audit_set", pdf_path="b", stratum={"confidence": "high"}
            ),
            GoldRecord(gold_id="f001", search_result_id=3, source="no_facts_span", pdf_path="c"),
        ]
        set_label(recs[0], rating="correct", has_facts=True, gold_span=[1, 5])
        set_label(recs[1], rating="incorrect", has_facts=True, gold_span=[1, 5])
        s = stats(recs)
        assert s["by_status"] == {"labeled": 2, "pending": 1}
        assert s["ratings"] == {"correct": 1, "incorrect": 1}
        assert s["with_gold_span"] == 2
        assert s["boundary_corrected"] == 2 and s["boundary_corrected_low_medium"] == 1
        assert "boundary corrected (differs from rules): 2 (low/medium: 1)" in format_stats(s)

    def test_unchanged_gold_span_is_not_a_correction(self):
        rec = GoldRecord(gold_id="g001", search_result_id=1, source="audit_set", pdf_path="a", rules_span=[1, 5])
        set_label(rec, rating="correct", has_facts=True, gold_span=[1, 5])
        s = stats([rec])
        assert s["with_gold_span"] == 1 and s["boundary_corrected"] == 0


class TestCli:
    def test_init_stats_verify(self, corpus, tmp_path, capsys):
        gold = tmp_path / "evals" / "gold_v1.jsonl"
        rc = main(
            [
                "--gold",
                str(gold),
                "init",
                "--audit-parquet",
                str(corpus["parquet"]),
                "--failures",
                str(corpus["failures"]),
                "--pdf-dir",
                str(corpus["pdf_dir"]),
                "--n-failures",
                "2",
            ]
        )
        assert rc == 0 and gold.exists() and gold.with_name("gold_v1.meta.json").exists()
        assert main(["--gold", str(gold), "init", "--no-verify"]) == 2  # refuses to overwrite
        assert main(["--gold", str(gold), "stats"]) == 0
        assert "total: 5" in capsys.readouterr().out
        assert main(["--gold", str(gold), "verify"]) == 0

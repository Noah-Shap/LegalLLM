"""Tests for legallm.single_doc (single-document path + legallm-extract CLI)."""

import json

import pytest

from legallm.schema import FactsExtraction
from legallm.single_doc import (
    EXTRACTORS,
    NoTextError,
    SingleDocResult,
    extract_from_file,
    extract_from_text,
    format_summary,
    main,
    register_extractor,
)


class TestExtractFromText:
    def test_rules_on_fixture(self, sample_brief_text):
        r = extract_from_text(sample_brief_text, source="fixture")
        assert isinstance(r, SingleDocResult)
        assert r.method == "rules_v2"
        assert r.text_extractor == "text"
        assert r.extraction.facts_span is not None
        assert r.doc_text[r.extraction.facts_span.start : r.extraction.facts_span.end] == r.extraction.facts_text
        assert r.validation.ok, r.validation.flags
        assert isinstance(r.needs_ocr, bool)  # short fixture trips the low-text heuristic; type only
        assert isinstance(r.ocr_reasons, list)
        assert r.doc_chars == len(r.doc_text)
        assert r.elapsed_s >= 0

    def test_no_span_yields_validation_failure(self):
        r = extract_from_text("Nothing here.")
        assert r.extraction.facts_span is None
        assert not r.validation.ok
        assert "empty_facts" in r.validation.flags

    def test_no_span_ok_when_not_required(self):
        r = extract_from_text("Nothing here.", require_facts=False)
        assert r.validation.ok

    def test_unknown_method(self, sample_brief_text):
        with pytest.raises(KeyError):
            extract_from_text(sample_brief_text, method="does-not-exist")

    def test_custom_extractor_registration(self, sample_brief_text):
        def fake(doc_text: str, doc_type_id: str) -> FactsExtraction:
            return FactsExtraction(extractor_version="fake-v0", confidence="low", doc_type_id=doc_type_id)

        register_extractor("fake-v0", fake)
        try:
            r = extract_from_text(sample_brief_text, method="fake-v0", doc_type_id="MERITS_SCOTUS")
            assert r.extraction.extractor_version == "fake-v0"
            assert r.extraction.doc_type_id == "MERITS_SCOTUS"
        finally:
            EXTRACTORS.pop("fake-v0", None)

    def test_to_dict_json_serialisable(self, sample_brief_text):
        r = extract_from_text(sample_brief_text)
        d = r.to_dict()
        assert "doc_text" not in d
        json.dumps(d)
        d2 = r.to_dict(include_text=True)
        assert d2["doc_text"] == r.doc_text
        assert d["extraction"]["extractor_version"] == "rules_v2"
        assert d["validation"]["ok"] is True


class TestExtractFromFile:
    def test_txt_file(self, tmp_path, sample_brief_text):
        p = tmp_path / "brief.txt"
        p.write_text(sample_brief_text, encoding="utf-8")
        r = extract_from_file(p)
        assert r.source == str(p)
        assert r.text_extractor == "text"
        assert r.extraction.facts_span is not None

    def test_missing_file(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            extract_from_file(tmp_path / "nope.txt")

    def test_pdf_file(self, tmp_path, sample_brief_text):
        fitz = pytest.importorskip("fitz")
        pdf = tmp_path / "brief.pdf"
        doc = fitz.open()
        page = doc.new_page()
        # Keep lines short so the page layout matches the fixture's line structure.
        y = 40
        for line in sample_brief_text.splitlines():
            page.insert_text((40, y), line, fontsize=8)
            y += 11
            if y > 780:
                page = doc.new_page()
                y = 40
        doc.save(str(pdf))
        doc.close()

        r = extract_from_file(pdf, warnings_log=tmp_path / "warn.log")
        assert r.text_extractor in ("pypdf", "pymupdf")
        assert r.page_count == 1
        assert r.extraction.facts_span is not None
        assert "Appellant filed a complaint" in r.extraction.facts_text

    def test_blank_pdf_raises_no_text(self, tmp_path):
        fitz = pytest.importorskip("fitz")
        pdf = tmp_path / "blank.pdf"
        doc = fitz.open()
        doc.new_page()
        doc.save(str(pdf))
        doc.close()
        with pytest.raises(NoTextError):
            extract_from_file(pdf, warnings_log=tmp_path / "warn.log")


class TestCli:
    def test_summary_output(self, tmp_path, sample_brief_text, capsys):
        p = tmp_path / "brief.txt"
        p.write_text(sample_brief_text, encoding="utf-8")
        rc = main([str(p)])
        out = capsys.readouterr().out
        assert rc == 0
        assert "validation:     OK" in out
        assert "facts_span:" in out

    def test_json_output_and_out_file(self, tmp_path, sample_brief_text, capsys):
        p = tmp_path / "brief.txt"
        p.write_text(sample_brief_text, encoding="utf-8")
        out_path = tmp_path / "out" / "result.json"
        rc = main([str(p), "--json", "--out", str(out_path)])
        assert rc == 0
        printed = json.loads(capsys.readouterr().out)
        assert printed["extraction"]["extractor_version"] == "rules_v2"
        assert json.loads(out_path.read_text(encoding="utf-8")) == printed

    def test_nonzero_exit_on_validation_failure(self, tmp_path, capsys):
        p = tmp_path / "empty.txt"
        p.write_text("Nothing here.", encoding="utf-8")
        assert main([str(p)]) == 1

    def test_missing_file_exit_2(self, tmp_path, capsys):
        assert main([str(tmp_path / "nope.txt")]) == 2
        assert "error:" in capsys.readouterr().err

    def test_format_summary_no_span(self):
        r = extract_from_text("Nothing here.")
        assert "facts_span:     none" in format_summary(r)

    def test_llm_error_exit_2(self, tmp_path, sample_brief_text, capsys, monkeypatch):
        import legallm.llm_extractor as mod

        class Boom:
            def __call__(self, doc_text, doc_type_id="UNKNOWN"):
                raise mod.LlmExtractionError("API error 400: no credits")

        monkeypatch.setitem(mod._extractors, "v2", Boom())
        p = tmp_path / "brief.txt"
        p.write_text(sample_brief_text, encoding="utf-8")
        assert main([str(p), "--method", "llm-v2"]) == 2
        assert "no credits" in capsys.readouterr().err

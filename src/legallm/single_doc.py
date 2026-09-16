"""Single-document extraction path (GAP.md §D item 3).

    legallm-extract brief.pdf                 # rules_v2 baseline, human-readable summary
    legallm-extract brief.txt --json          # full FactsExtraction + validation as JSON
    legallm-extract brief.pdf --method llm-v1 # Claude Sonnet 5 extractor (needs ANTHROPIC_API_KEY)

Runs: load text (pypdf → PyMuPDF for PDFs; read for .txt) → normalise →
preprocess → extractor → deterministic validators. OCR is not run here; the
result carries ``needs_ocr`` so callers can route the document elsewhere.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from legallm.baseline_adapter import RULES_VERSION, extract_rules, preprocess_text
from legallm.guard import apply_guard
from legallm.llm_extractor import PROMPT_VERSIONS, LlmExtractionError, llm_method
from legallm.pipeline import doc_needs_ocr, extract_text_best, get_pdf_page_count_fast, normalize_text
from legallm.routing import ROUTED_METHOD, routed_method
from legallm.schema import FactsExtraction
from legallm.validators import ValidationReport, validate_extraction

Extractor = Callable[[str, str], FactsExtraction]

EXTRACTORS: dict[str, Extractor] = {
    RULES_VERSION: extract_rules,
    **{f"llm-{v}": llm_method(v) for v in PROMPT_VERSIONS},  # llm-v1, llm-v2, ...
    ROUTED_METHOD: routed_method(),  # llm-v3: Sonnet 5 first, Opus 5 on validator/anchor failure
}
DEFAULT_METHOD = RULES_VERSION
DEFAULT_WARNINGS_LOG = Path("logs/pdf_parse_warnings.log")


class NoTextError(RuntimeError):
    """Raised when no text could be extracted from a document (likely needs OCR)."""


def register_extractor(name: str, fn: Extractor) -> None:
    """Register an extractor callable ``fn(doc_text, doc_type_id) -> FactsExtraction`` under ``name``."""
    EXTRACTORS[name] = fn


@dataclass
class SingleDocResult:
    """Everything produced for one document."""

    source: str
    method: str
    doc_type_id: str
    text_extractor: str  # "pypdf" | "pymupdf" | "text"
    text_notes: list[str]
    page_count: int | None
    needs_ocr: bool
    ocr_reasons: list[str]
    doc_chars: int
    extraction: FactsExtraction
    validation: ValidationReport
    elapsed_s: float
    doc_text: str = field(repr=False, default="")

    def to_dict(self, *, include_text: bool = False) -> dict[str, Any]:
        d: dict[str, Any] = {
            "source": self.source,
            "method": self.method,
            "doc_type_id": self.doc_type_id,
            "text_extractor": self.text_extractor,
            "text_notes": list(self.text_notes),
            "page_count": self.page_count,
            "needs_ocr": self.needs_ocr,
            "ocr_reasons": list(self.ocr_reasons),
            "doc_chars": self.doc_chars,
            "elapsed_s": round(self.elapsed_s, 3),
            "extraction": self.extraction.model_dump(),
            "validation": self.validation.to_dict(),
        }
        if include_text:
            d["doc_text"] = self.doc_text
        return d


def load_document_text(path: Path, warnings_log: Path | None = None) -> tuple[str, str, list[str], int | None]:
    """Return ``(raw_text, text_extractor, notes, page_count)`` for a PDF or text file."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(path)
    if path.suffix.lower() == ".pdf":
        txt, extractor, notes = extract_text_best(path, warnings_log or DEFAULT_WARNINGS_LOG)
        if not txt or not txt.strip():
            raise NoTextError(f"no text extracted from {path.name} (extractor={extractor}); document may need OCR")
        return txt, extractor, list(notes), get_pdf_page_count_fast(path)
    return path.read_text(encoding="utf-8", errors="replace"), "text", [], None


def extract_from_text(
    text: str,
    *,
    method: str = DEFAULT_METHOD,
    doc_type_id: str = "UNKNOWN",
    source: str = "<text>",
    text_extractor: str = "text",
    text_notes: list[str] | None = None,
    page_count: int | None = None,
    require_facts: bool = True,
) -> SingleDocResult:
    """Run one extractor + validators on raw document text."""
    if method not in EXTRACTORS:
        raise KeyError(f"unknown extractor {method!r}; registered: {sorted(EXTRACTORS)}")
    t0 = time.perf_counter()
    clean = normalize_text(text)
    needs_ocr, details = doc_needs_ocr(clean, page_count=page_count)
    doc_text = preprocess_text(clean)
    extraction = EXTRACTORS[method](doc_text, doc_type_id)
    report = apply_guard(validate_extraction(extraction, doc_text, require_facts=require_facts), doc_text, extraction)
    return SingleDocResult(
        source=source,
        method=method,
        doc_type_id=doc_type_id,
        text_extractor=text_extractor,
        text_notes=list(text_notes or []),
        page_count=page_count,
        needs_ocr=bool(needs_ocr),
        ocr_reasons=list((details or {}).get("reasons") or []),
        doc_chars=len(doc_text),
        extraction=extraction,
        validation=report,
        elapsed_s=time.perf_counter() - t0,
        doc_text=doc_text,
    )


def extract_from_file(
    path: str | Path,
    *,
    method: str = DEFAULT_METHOD,
    doc_type_id: str = "UNKNOWN",
    warnings_log: Path | None = None,
    require_facts: bool = True,
) -> SingleDocResult:
    """Run one extractor + validators on a PDF or text file."""
    p = Path(path)
    raw, extractor, notes, page_count = load_document_text(p, warnings_log)
    return extract_from_text(
        raw,
        method=method,
        doc_type_id=doc_type_id,
        source=str(p),
        text_extractor=extractor,
        text_notes=notes,
        page_count=page_count,
        require_facts=require_facts,
    )


def format_summary(r: SingleDocResult, *, preview_chars: int = 400) -> str:
    ex = r.extraction
    lines = [
        f"source:         {r.source}",
        f"method:         {r.method}  (doc_type={r.doc_type_id})",
        f"text:           {r.text_extractor} | {r.doc_chars:,} chars | pages={r.page_count} | needs_ocr={r.needs_ocr}",
        f"confidence:     {ex.confidence}",
        f"notes:          {', '.join(ex.notes) or '-'}",
        f"case_citations: {len(ex.case_citations)}",
        f"validation:     {'OK' if r.validation.ok else 'FAIL'}  flags={r.validation.flags or '-'}",
        f"elapsed:        {r.elapsed_s:.2f}s",
    ]
    if ex.facts_span is not None:
        lines.append(f"facts_span:     [{ex.facts_span.start}, {ex.facts_span.end}) | {ex.facts_span.length:,} chars")
        preview = ex.facts_span.text[:preview_chars].replace("\n", " ")
        lines.append(f"preview:        {preview}{'...' if ex.facts_span.length > preview_chars else ''}")
    else:
        lines.append("facts_span:     none")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="legallm-extract", description="Extract the facts section from one brief.")
    ap.add_argument("file", help="PDF or .txt file")
    ap.add_argument("--method", default=DEFAULT_METHOD, help=f"extractor name (registered: {sorted(EXTRACTORS)})")
    ap.add_argument("--doc-type", default="UNKNOWN", dest="doc_type_id", help="doc_type_id for heading policy")
    ap.add_argument("--json", action="store_true", help="print full JSON (extraction + validation)")
    ap.add_argument("--include-text", action="store_true", help="with --json, include the preprocessed doc text")
    ap.add_argument("--out", type=str, default=None, help="write JSON to this path")
    ap.add_argument(
        "--backend",
        choices=["api", "claude-cli"],
        default=None,
        help="LLM transport for llm-* methods: Messages API (default) or headless claude -p (subscription)",
    )
    args = ap.parse_args(argv)
    if args.backend:
        from legallm.llm_extractor import configure_default

        configure_default(backend=args.backend)

    try:
        result = extract_from_file(args.file, method=args.method, doc_type_id=args.doc_type_id)
    except (FileNotFoundError, NoTextError, KeyError, LlmExtractionError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    payload = result.to_dict(include_text=args.include_text)
    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print(format_summary(result))
        if args.out:
            print(f"wrote:          {args.out}")
    return 0 if result.validation.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

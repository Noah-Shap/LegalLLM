"""
PyMuPDF + Tesseract "OCR on demand" backend.

Purpose
-------
Use this module to reduce text-native PDF bias by performing OCR only when native text
extraction is insufficient.

Key points
----------
- Uses PyMuPDF (fitz) for native text extraction.
- Uses PyMuPDF's built-in OCR integration (Page.get_textpage_ocr) backed by Tesseract.
- Uses the *shared* decision logic in ocr_decision.py for both:
    - document-level "needs OCR?" decisions (in your pipeline), and
    - page-level "should OCR this page?" decisions (in this backend),
  so the two do not drift.

Optional: save extracted text to a .txt file (CLI flag --save-txt).

Notes
-----
PyMuPDF's OCR integration calls Tesseract under the hood via Page.get_textpage_ocr().
On Windows you typically need:
  - Tesseract installed
  - tesseract.exe on PATH
  - TESSDATA_PREFIX pointing at the tessdata directory (or pass --tessdata)

"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# PyMuPDF
try:
    import fitz  # type: ignore
except Exception:  # pragma: no cover
    fitz = None  # type: ignore

from ocr_decision import OcrDecisionConfig, page_text_metrics, should_ocr_page


# -----------------------------
# Env / dependency checks
# -----------------------------

def _which(exe: str) -> Optional[str]:
    try:
        return shutil.which(exe)
    except Exception:
        return None


def _run_tesseract_list_langs(tesseract_exe: str, env: Dict[str, str]) -> Tuple[bool, str]:
    """
    Best-effort: ask Tesseract which languages are installed.
    Returns (ok, stdout_or_err).
    """
    try:
        p = subprocess.run(
            [tesseract_exe, "--list-langs"],
            capture_output=True,
            text=True,
            env=env,
            timeout=10,
        )
        out = (p.stdout or "") + (p.stderr or "")
        return (p.returncode == 0), out.strip()
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"


def check_ocr_ready(language: str = "eng", tessdata: Optional[str] = None) -> Tuple[bool, str, Dict[str, Any]]:
    """
    Verify that OCR dependencies are available (Windows-friendly):
      - PyMuPDF is importable and supports Page.get_textpage_ocr
      - Tesseract executable is on PATH
      - tessdata directory discoverable (via tessdata arg or TESSDATA_PREFIX)
      - language traineddata present
    """
    details: Dict[str, Any] = {}

    if fitz is None:
        return False, "PyMuPDF (fitz) not importable. Install: pip install pymupdf", details

    has_ocr = bool(getattr(getattr(fitz, "Page", object), "get_textpage_ocr", None))
    details["has_Page_get_textpage_ocr"] = has_ocr
    if not has_ocr:
        return False, "This PyMuPDF build does not expose Page.get_textpage_ocr(). Upgrade PyMuPDF.", details

    tesseract_exe = _which("tesseract")
    details["tesseract_on_path"] = tesseract_exe
    if not tesseract_exe:
        return False, "tesseract not found on PATH. Install Tesseract and add it to PATH.", details

    # tessdata directory
    env_tessdata = os.environ.get("TESSDATA_PREFIX")
    td = Path(tessdata or env_tessdata or "").expanduser() if (tessdata or env_tessdata) else None
    details["TESSDATA_PREFIX"] = env_tessdata
    details["tessdata_arg"] = tessdata
    if not td or not td.exists() or not td.is_dir():
        return False, "tessdata directory not found. Set TESSDATA_PREFIX or pass --tessdata.", details

    details["tessdata_dir"] = str(td)
    trained = td / f"{language}.traineddata"
    details["traineddata_path"] = str(trained)
    if not trained.exists():
        return False, f"Missing traineddata for language='{language}': {trained}", details

    # Optional: language listing
    env = dict(os.environ)
    env["TESSDATA_PREFIX"] = str(td)
    ok_langs, out = _run_tesseract_list_langs(tesseract_exe, env)
    details["tesseract_list_langs_ok"] = ok_langs
    details["tesseract_list_langs_output"] = out

    return True, f"OCR ready (tessdata={td})", details


# -----------------------------
# Metadata
# -----------------------------

@dataclass
class OcrMeta:
    backend: str = "pymupdf_textpage_ocr"
    ocr_used: bool = False
    ocr_full: bool = True
    ocr_language: str = "eng"
    ocr_dpi: int = 300
    ocr_pages_attempted: int = 0
    ocr_pages_succeeded: int = 0
    total_pages: int = 0
    elapsed_ms: int = 0
    tessdata: Optional[str] = None
    error: Optional[str] = None
    # For analysis/debug
    per_page_native_metrics: Optional[List[Dict[str, Any]]] = None
    per_page_ocr_metrics: Optional[List[Dict[str, Any]]] = None


# -----------------------------
# Extraction
# -----------------------------

def _sha1_file(path: Path, chunk_size: int = 1 << 20) -> str:
    h = hashlib.sha1()
    with path.open("rb") as f:
        while True:
            b = f.read(chunk_size)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def _get_textpage_ocr(page: Any, *, language: str, dpi: int, full: bool, tessdata: Optional[str]):
    """
    Handle keyword variations across PyMuPDF versions.
    """
    try:
        return page.get_textpage_ocr(language=language, dpi=dpi, full=full, tessdata=tessdata)
    except TypeError:
        # Some builds may not accept tessdata kwarg.
        return page.get_textpage_ocr(language=language, dpi=dpi, full=full)


def extract_text_pymupdf_selective_ocr(
    pdf_path: str | Path,
    *,
    language: str = "eng",
    dpi: int = 300,
    full: bool = True,
    tessdata: Optional[str] = None,
    decision_cfg: OcrDecisionConfig = OcrDecisionConfig(),
    force_ocr: bool = False,
    collect_reasons: bool = False,
    max_pages: Optional[int] = None,
    timeout_seconds: Optional[int] = None,
    collect_debug_metrics: bool = False,
) -> Tuple[str, OcrMeta]:
    """
    Extract text from a PDF using PyMuPDF, performing OCR only on pages where native
    extraction is 'bad' (per ocr_decision.should_ocr_page), unless force_ocr=True.

    - Native extraction: page.get_text("text")
    - OCR: page.get_textpage_ocr(...) then page.get_text("text", textpage=tp)

    Args:
      full: True OCRs whole page; False OCRs image regions (often better for mixed PDFs).
      tessdata: path to tessdata dir; defaults to TESSDATA_PREFIX.
      decision_cfg: shared thresholds used for page-level decisions.
      force_ocr: if True, OCR every page regardless of native text quality.
      collect_reasons: if True, store per-page decision reasons in native_metrics under key "ocr_reasons".
      max_pages: safety limit (abort if doc exceeds this).
      timeout_seconds: safety limit on total OCR runtime.
      collect_debug_metrics: store per-page metrics in meta (increases memory).

    Returns:
      (combined_text, meta)
    """
    if fitz is None:
        raise RuntimeError("PyMuPDF (fitz) is not available; install with: pip install pymupdf")

    start = time.perf_counter()
    pdf_path = Path(pdf_path)

    meta = OcrMeta(
        ocr_full=full,
        ocr_language=language,
        ocr_dpi=dpi,
        tessdata=tessdata or os.environ.get("TESSDATA_PREFIX"),
    )

    pages_text: List[str] = []
    native_metrics: Optional[List[Dict[str, Any]]] = [] if collect_debug_metrics else None
    ocr_metrics: Optional[List[Dict[str, Any]]] = [] if collect_debug_metrics else None

    try:
        doc = fitz.open(str(pdf_path))
        meta.total_pages = doc.page_count

        if max_pages is not None and meta.total_pages > max_pages:
            raise ValueError(f"PDF has {meta.total_pages} pages > max_pages={max_pages}")

        for i in range(meta.total_pages):
            # safety timeout
            if timeout_seconds is not None:
                if (time.perf_counter() - start) > timeout_seconds:
                    raise TimeoutError(f"OCR extraction exceeded timeout_seconds={timeout_seconds}")

            page = doc.load_page(i)
            native = page.get_text("text") or ""

            do_ocr = force_ocr
            details: Dict[str, Any] = {}
            if not force_ocr:
                do_ocr, details = should_ocr_page(native, cfg=decision_cfg)

            if collect_debug_metrics:
                m = details.get("metrics") if details else page_text_metrics(native)
                m = dict(m)
                if collect_reasons and details:
                    m["ocr_reasons"] = details.get("reasons", [])
                native_metrics.append(m)

            if do_ocr:
                meta.ocr_pages_attempted += 1
                tp = _get_textpage_ocr(page, language=language, dpi=dpi, full=full, tessdata=meta.tessdata)
                ocr_text = page.get_text("text", textpage=tp) or ""

                if collect_debug_metrics:
                    ocr_metrics.append(page_text_metrics(ocr_text))

                if ocr_text.strip():
                    meta.ocr_pages_succeeded += 1
                    meta.ocr_used = True
                    pages_text.append(ocr_text)
                else:
                    # fall back to native if OCR produced nothing
                    pages_text.append(native)
            else:
                pages_text.append(native)

    except Exception as e:
        meta.error = f"{type(e).__name__}: {e}"
    finally:
        try:
            doc.close()  # type: ignore[name-defined]
        except Exception:
            pass

    meta.elapsed_ms = int((time.perf_counter() - start) * 1000)

    if collect_debug_metrics:
        meta.per_page_native_metrics = native_metrics
        meta.per_page_ocr_metrics = ocr_metrics

    return "\n".join(pages_text), meta


def extract_text_with_ocr_fallback(
    pdf_path: str | Path,
    *,
    language: str = "eng",
    dpi: int = 300,
    full: bool = True,
    tessdata: Optional[str] = None,
    decision_cfg: OcrDecisionConfig = OcrDecisionConfig(),
    force_ocr: bool = False,
    max_pages: Optional[int] = None,
    timeout_seconds: Optional[int] = None,
    save_txt: bool = False,
    out_txt_path: Optional[str | Path] = None,
) -> Tuple[str, Dict[str, Any]]:
    """
    Convenience wrapper used by pipelines:
      - uses PyMuPDF native
      - selectively OCRs pages based on shared ocr_decision.should_ocr_page

    Returns:
      (combined_text, meta_dict)

    If save_txt=True, writes combined_text to out_txt_path (or next to PDF as .txt).
    """
    text, meta = extract_text_pymupdf_selective_ocr(
        pdf_path,
        language=language,
        dpi=dpi,
        full=full,
        tessdata=tessdata,
        decision_cfg=decision_cfg,
        force_ocr=force_ocr,
        max_pages=max_pages,
        timeout_seconds=timeout_seconds,
        collect_debug_metrics=False,
    )
    meta_dict = asdict(meta)

    if save_txt:
        pdf_path = Path(pdf_path)
        out_path = Path(out_txt_path) if out_txt_path else pdf_path.with_suffix(".txt")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(text, encoding="utf-8", errors="replace")
        meta_dict["saved_txt_path"] = str(out_path)

    return text, meta_dict


# -----------------------------
# Simple caching (optional)
# -----------------------------

def extract_text_pymupdf_selective_ocr_cached(
    pdf_path: str | Path,
    cache_dir: str | Path,
    *,
    language: str = "eng",
    dpi: int = 300,
    full: bool = True,
    tessdata: Optional[str] = None,
    decision_cfg: OcrDecisionConfig = OcrDecisionConfig(),
    force_ocr: bool = False,
    max_pages: Optional[int] = None,
    timeout_seconds: Optional[int] = None,
) -> Tuple[Path, Path]:
    """
    Cache outputs (text + meta json) by SHA1 of the PDF bytes.
    Returns (text_path, meta_path).
    """
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)

    pdf_path = Path(pdf_path)
    key = _sha1_file(pdf_path)
    base = cache_dir / key
    text_path = base.with_suffix(".txt")
    meta_path = base.with_suffix(".meta.json")

    if text_path.exists() and meta_path.exists():
        return text_path, meta_path

    text, meta = extract_text_with_ocr_fallback(
        pdf_path,
        language=language,
        dpi=dpi,
        full=full,
        tessdata=tessdata,
        decision_cfg=decision_cfg,
        force_ocr=force_ocr,
        max_pages=max_pages,
        timeout_seconds=timeout_seconds,
    )

    text_path.write_text(text, encoding="utf-8", errors="replace")
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")

    return text_path, meta_path


# -----------------------------
# CLI
# -----------------------------

def _cli() -> int:
    ap = argparse.ArgumentParser(description="PyMuPDF selective OCR text extractor")
    ap.add_argument("--pdf", type=str, required=True, help="Path to a PDF file")
    ap.add_argument("--language", type=str, default="eng")
    ap.add_argument("--dpi", type=int, default=300)
    ap.add_argument("--full", action="store_true", help="OCR the full page (default)")
    ap.add_argument("--partial", action="store_true", help="OCR image regions only")
    ap.add_argument("--tessdata", type=str, default=None, help="Path to tessdata directory (optional)")
    ap.add_argument("--max-pages", type=int, default=None, help="Abort if PDF exceeds this many pages")
    ap.add_argument("--timeout-seconds", type=int, default=None, help="Abort if OCR runtime exceeds this many seconds")
    ap.add_argument("--force-ocr", action="store_true", help="OCR every page regardless of native text quality")
    ap.add_argument("--save-txt", action="store_true", help="Save extracted output to a .txt file")
    ap.add_argument("--out-txt", type=str, default=None, help="Optional explicit output .txt path")
    ap.add_argument("--cache-dir", type=str, default=None, help="Optional cache dir; if set, writes cache files and exits")
    ap.add_argument("--print-preview", action="store_true", help="Print the first 1000 chars of output text")
    args = ap.parse_args()

    ok, msg, details = check_ocr_ready(args.language, tessdata=args.tessdata)
    if not ok:
        print(msg)
        print(json.dumps(details, indent=2))
        return 2

    full = True
    if args.partial:
        full = False
    if args.full:
        full = True

    if args.cache_dir:
        text_path, meta_path = extract_text_pymupdf_selective_ocr_cached(
            args.pdf,
            args.cache_dir,
            language=args.language,
            dpi=args.dpi,
            full=full,
            tessdata=args.tessdata,
            force_ocr=args.force_ocr,
            timeout_seconds=args.timeout_seconds,
            max_pages=args.max_pages,
        )
        print(f"cache: text={text_path} meta={meta_path}")
        return 0

    text, meta = extract_text_with_ocr_fallback(
        args.pdf,
        language=args.language,
        dpi=args.dpi,
        full=full,
        tessdata=args.tessdata,
        force_ocr=args.force_ocr,
        timeout_seconds=args.timeout_seconds,
        max_pages=args.max_pages,
        save_txt=args.save_txt,
        out_txt_path=args.out_txt,
    )

    print(json.dumps(meta, indent=2))
    print(f"chars: {len(text)}")
    if args.print_preview:
        print("\n--- preview ---\n")
        print(text[:1000])

    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(_cli())

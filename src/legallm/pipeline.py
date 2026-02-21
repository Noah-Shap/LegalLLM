import argparse
import contextlib
import io
import json
import logging
import os
import re
import sys
import time
from pathlib import Path
from typing import Any

import pandas as pd
import requests
from pypdf import PdfReader
from requests.adapters import HTTPAdapter
from tqdm import tqdm
from urllib3.util.retry import Retry

from legallm.ocr_decision import OcrDecisionConfig, should_ocr_document

# Optional: OCR backend (PyMuPDF + Tesseract). If unavailable, pipeline can still run without OCR.
check_ocr_ready: Any = None
extract_text_with_ocr_fallback: Any = None
try:
    from legallm.ocr_backend import check_ocr_ready, extract_text_with_ocr_fallback
except Exception:  # pragma: no cover
    pass

# Optional: PyMuPDF provides more reliable text extraction for some PDFs.
try:
    import fitz  # type: ignore[import-untyped]  # PyMuPDF
except Exception:  # pragma: no cover
    fitz = None

BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


BASE = "https://www.courtlistener.com/api/rest/v4"

RE_PACER_HEADER = re.compile(r"(?i)\bcase\b.*\bdocument\b.*\bfiled\b.*\bpage\b")
RE_CA3_HEADER = re.compile(r"(?i)^case:\s*\d", re.M)


logging.getLogger("pypdf").setLevel(logging.ERROR)

# Shared OCR decision config (standardized across modules)
OCR_DECISION_CFG = OcrDecisionConfig()


def doc_needs_ocr(text: str, page_count: int | None = None):
    """Standard OCR decision wrapper used by this pipeline."""
    return should_ocr_document(text, page_count=page_count, cfg=OCR_DECISION_CFG)


def cl_session() -> requests.Session:
    token = os.environ.get("CL_TOKEN")
    if not token:
        raise RuntimeError("Missing CL_TOKEN env var.")

    s = requests.Session()
    s.headers.update({"Authorization": f"Token {token}"})
    s.headers.update({"User-Agent": "facts-only-extractor/0.3"})

    # Retries for flaky network / overloaded server
    retry = Retry(
        total=6,
        connect=6,
        read=6,
        status=6,
        backoff_factor=1.0,  # 1s, 2s, 4s, 8s...
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET", "OPTIONS"],
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry, pool_connections=10, pool_maxsize=10)
    s.mount("https://", adapter)
    s.mount("http://", adapter)
    return s


def paged_get(s: requests.Session, url: str, params: dict[str, Any], max_items: int) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    next_url: str | None = url
    next_params: dict[str, Any] | None = params
    while next_url and len(out) < max_items:
        r = s.get(next_url, params=next_params, timeout=180)
        r.raise_for_status()
        data = r.json()
        out.extend(data.get("results", []))
        next_url = data.get("next")
        next_params = None
    return out[:max_items]


# -----------------------------
# Normalization
# -----------------------------
RE_MULTI_NL = re.compile(r"\n{3,}")
RE_SPACES = re.compile(r"[ \t]{2,}")
RE_HYPHEN_BREAK = re.compile(r"(\w)-\n(\w)")


def normalize_text(raw: str) -> str:
    txt = raw.replace("\r\n", "\n").replace("\r", "\n")
    txt = RE_HYPHEN_BREAK.sub(r"\1\2", txt)
    txt = RE_SPACES.sub(" ", txt)
    txt = RE_MULTI_NL.sub("\n\n", txt)
    txt = "\n".join(line.rstrip() for line in txt.splitlines())
    return txt.strip()


# -----------------------------
# Facts extraction (rules)
# -----------------------------
START_HEADINGS = [
    r"STATEMENT OF FACTS",
    r"STATEMENT OF THE CASE",
    r"STATEMENT OF THE FACTS",
    r"FACTUAL BACKGROUND",
    r"BACKGROUND",
    r"RELEVANT FACTS",
    r"FACTS AND PROCEDURAL HISTORY",
    r"FACTUAL AND PROCEDURAL BACKGROUND",
    r"STATEMENT OF FACTS AND PROCEDURAL HISTORY",
    r"STATEMENT OF THE CASE AND FACTS",
    r"PROCEDURAL HISTORY",
]
STOP_HEADINGS = [
    r"SUMMARY OF ARGUMENT",
    r"ARGUMENT",
    r"STANDARD OF REVIEW",
    r"LEGAL STANDARD",
    r"CONCLUSION",
    r"RELIEF REQUESTED",
    r"DISCUSSION",
    r"ANALYSIS",
]


def _heading_regex(phrases: list[str]) -> re.Pattern:
    # Match common heading formats, including punctuation and TOC page numbers.
    esc = [re.escape(p.upper()) for p in phrases]
    joined = "|".join(esc)

    return re.compile(
        rf"""(?mx)
        ^\s*
        (?:[IVXLC]+\.?)?\s*          # optional roman numeral (with optional dot)
        (?:\d+\.?)?\s*               # optional arabic numeral (with optional dot)
        (?:{joined})                 # heading phrase
        \s*(?:[:\.\-–—])?\s*         # optional trailing punctuation
        (?:\.{{2,}}\s*\d{{1,4}})?\s* # optional dot leaders + page number (TOC)
        (?:\s+\d{{1,4}})?\s*         # optional bare page number (TOC)
        $"""
    )


TOC_MARKERS = ("TABLE OF CONTENTS", "TABLE OF AUTHORITIES", "TABLE OF CITATIONS")


def _line_at(text: str, idx: int) -> str:
    ls = text.rfind("\n", 0, idx) + 1
    le = text.find("\n", idx)
    if le == -1:
        le = len(text)
    return text[ls:le]


def _is_probably_toc_entry(upper_text: str, match_start: int) -> bool:
    # If there is a TOC marker shortly before the match, and the line looks like a TOC entry,
    # treat it as TOC rather than a real section heading.
    window = 15000
    prev = upper_text[max(0, match_start - window) : match_start]
    if not any(m in prev for m in TOC_MARKERS):
        return False

    line = _line_at(upper_text, match_start).strip()

    # Dot leaders or trailing page number are strong TOC signals.
    if re.search(r"\.{2,}\s*\d{1,4}\s*$", line):
        return True
    if re.search(r"\s+\d{1,4}\s*$", line) and len(line) >= 20:
        return True
    return False


RE_START = _heading_regex(START_HEADINGS)
RE_STOP = _heading_regex(STOP_HEADINGS)


HEADING_LINE = re.compile(r"(?m)^\s*(?:[IVXLC]+\.)?\s*(?:\d+\.)?\s*([A-Z][A-Z0-9 \-–—/&,:]{2,90})\s*$")

BAD_HEADING_FRAGMENTS = [
    "TABLE OF CONTENTS",
    "TABLE OF AUTHORITIES",
    "JURISDICTION",
    "CERTIFICATE",
    "SERVICE",
    "COMPLIANCE",
    "CORPORATE DISCLOSURE",
    "CASE ",
    "DOCUMENT ",
    "FILED ",
    "PAGE ",
]

SOFT_START_KEYWORDS = ["FACT", "BACKGROUND", "STATEMENT OF THE CASE", "STATEMENT"]
SOFT_STOP_KEYWORDS = ["ARGUMENT", "DISCUSSION", "STANDARD OF REVIEW", "LEGAL STANDARD", "CONCLUSION"]


def strip_pacer_headers(clean: str) -> str:
    out = []
    for line in clean.splitlines():
        u = line.strip().upper()
        if "DOCUMENT" in u and "FILED" in u and "PAGE" in u and u.startswith("CASE "):
            continue
        if u.startswith("CASE:") and "DOCUMENT:" in u and "PAGE:" in u:
            continue
        out.append(line)
    return "\n".join(out)


def merge_roman_heading_lines(text: str) -> str:
    lines = text.splitlines()
    merged = []
    i = 0
    while i < len(lines):
        cur = lines[i].strip()
        if re.fullmatch(r"[IVXLC]+", cur) and i + 1 < len(lines):
            nxt = lines[i + 1].strip()
            # merge into "III. <next>"
            merged.append(f"{cur}. {nxt}")
            i += 2
            continue
        merged.append(lines[i])
        i += 1
    return "\n".join(merged)


def extract_facts_span(clean: str) -> tuple[tuple[int, int] | None, dict[str, Any]]:
    meta: dict[str, Any] = {"method": "rules_v1", "notes": []}

    clean2 = merge_roman_heading_lines(strip_pacer_headers(clean))
    upper = clean2.upper()

    # 1) Exact heading start/stop (your original approach)
    m_start = RE_START.search(upper)
    while m_start and _is_probably_toc_entry(upper, m_start.start()):
        meta["notes"].append("ignored_toc_start")
        m_start = RE_START.search(upper, m_start.end())

    if m_start:
        start = m_start.end()
        m_stop = RE_STOP.search(upper, pos=start)
        while m_stop and _is_probably_toc_entry(upper, m_stop.start()):
            meta["notes"].append("ignored_toc_stop")
            m_stop = RE_STOP.search(upper, pos=m_stop.end())
        end = m_stop.start() if m_stop else len(clean2)

        while start < len(clean2) and clean2[start] in " \n\t":
            start += 1
        while end > 0 and clean2[end - 1] in " \n\t":
            end -= 1

        if end > start:
            if (end - start) < 500:
                meta["notes"].append("span_too_short")
            return (start, end), meta

    meta["notes"].append("no_exact_heading")

    # 2) Soft heading detection: any heading-like line containing FACT/BACKGROUND/STATEMENT
    heading_matches = list(HEADING_LINE.finditer(upper))
    headings = []
    for m in heading_matches:
        title = m.group(1).strip()
        if any(b in title for b in BAD_HEADING_FRAGMENTS):
            continue
        headings.append((m.start(), m.end(), title))

    # pick first heading that looks like facts
    soft_start: int | None = None
    for hs, he, title in headings:
        if any(k in title for k in SOFT_START_KEYWORDS):
            soft_start = he
            meta["notes"].append(f"soft_start:{title}")
            break

    if soft_start is not None:
        # stop at first argument-like heading after start
        end = len(clean2)
        for hs, he, title in headings:
            if hs <= soft_start:
                continue
            if any(k in title for k in SOFT_STOP_KEYWORDS):
                end = hs
                meta["notes"].append(f"soft_stop:{title}")
                break

        while soft_start < len(clean2) and clean2[soft_start] in " \n\t":
            soft_start += 1
        while end > 0 and clean2[end - 1] in " \n\t":
            end -= 1

        if end > soft_start and (end - soft_start) >= 300:
            return (soft_start, end), meta
        meta["notes"].append("soft_span_bad")

    # 3) Fallback: pre-ARGUMENT slice (many briefs put facts before ARGUMENT even w/out a facts heading)
    m_arg = re.search(r"(?m)^\s*(?:[IVXLC]+\.?)?\s*(?:\d+\.?)?\s*ARGUMENT\s*(?:[:\.\-–—])?\s*$", upper)
    if m_arg:
        end = m_arg.start()
        # also try to skip front matter like tables if present
        m_toa = re.search(r"(?m)^\s*TABLE OF AUTHORITIES\s*$", upper)
        if m_toa and m_toa.start() < end:
            # start after TOA block (next heading after TOA)
            start = m_toa.end()
            # move to next heading after TOA
            for hs, he, title in headings:
                if hs > start:
                    start = he
                    break
        else:
            start = 0

        # trim
        while start < len(clean2) and clean2[start] in " \n\t":
            start += 1
        while end > 0 and clean2[end - 1] in " \n\t":
            end -= 1

        if end > start and (end - start) >= 800:
            meta["notes"].append("fallback_pre_argument")
            return (start, end), meta

    meta["notes"].append("no_span_found")
    return None, meta


# -----------------------------
# Quality flags
# -----------------------------
RE_CASE_CITE = re.compile(r"\b\d{1,4}\s+[A-Z][A-Za-z\.\s]{0,20}\s+\d{1,5}\b")
RE_ARG_MARKERS = re.compile(
    r"\b(we\s+argue|this\s+court\s+should|standard\s+of\s+review|for\s+these\s+reasons)\b", re.I
)


def quality_flags(text: str) -> dict[str, Any]:
    n_chars = max(len(text), 1)
    cite_hits = len(RE_CASE_CITE.findall(text))
    arg_hits = len(RE_ARG_MARKERS.findall(text))
    return {
        "cite_hits": cite_hits,
        "arg_marker_hits": arg_hits,
        "cite_hits_per_10k_chars": cite_hits / (n_chars / 10_000.0),
        "arg_hits_per_10k_chars": arg_hits / (n_chars / 10_000.0),
    }


# -----------------------------
# Search + URL resolution
# -----------------------------
def search_recap_documents(
    s: requests.Session, query: str, max_docs: int, search_fields: str | None
) -> list[dict[str, Any]]:
    url = f"{BASE}/search/"
    params = {
        "q": query,
        "type": "rd",  # "flat PACER documents" mode (per migration guide)
        "available_only": "on",
        "order_by": "score desc",
    }
    # If supported, ask for extra fields so we can find the PDF without recap-doc endpoints
    if search_fields:
        params["fields"] = search_fields
    return paged_get(s, url, params, max_docs)


PDF_URL_KEYS = ["download_url", "file_url", "pdf_url", "download", "url"]
WEB_URL_KEYS = ["absolute_url", "permalink", "web_url"]

RE_RECAP_DOC_PAGE = re.compile(r"/recap-document/(\d+)/")


def _normalize_web_url(u: str) -> str:
    if u.startswith("/"):
        return "https://www.courtlistener.com" + u
    return u


def extract_pdf_url_from_webpage(s: requests.Session, web_url: str) -> str | None:
    """
    Best-effort: fetch the public webpage and regex out a PDF href.
    """
    try:
        r = s.get(web_url, headers={"Accept": "text/html"}, timeout=60)
        if r.status_code != 200:
            return None
        html = r.text
        # Look for any href to .pdf
        m = re.search(r'href="([^"]+\.pdf[^"]*)"', html, re.IGNORECASE)
        if not m:
            return None
        return _normalize_web_url(m.group(1))
    except Exception:
        return None


def derive_pdf_url(s: requests.Session, item: dict[str, Any]) -> tuple[str | None, dict[str, Any]]:
    meta: dict[str, Any] = {"strategy": None, "web_url": None}

    # ✅ 0) Best: filepath_local from search results
    fp = item.get("filepath_local")
    if isinstance(fp, str) and fp.strip():
        fp = fp.strip().lstrip("/")  # ensure no leading slash issues
        meta["strategy"] = "search.filepath_local"
        return f"https://storage.courtlistener.com/{fp}", meta

    # 1) Direct PDF-ish fields
    for k in PDF_URL_KEYS:
        v = item.get(k)
        if isinstance(v, str) and v.strip():
            meta["strategy"] = f"search.{k}"
            return _normalize_web_url(v.strip()), meta

    # 2) scrape docket-entry page if present
    web_url = None
    for k in WEB_URL_KEYS:
        v = item.get(k)
        if isinstance(v, str) and v.strip():
            web_url = _normalize_web_url(v.strip())
            break

    if web_url:
        meta["web_url"] = web_url
        meta["strategy"] = "scrape_webpage_for_pdf"
        pdf = extract_pdf_url_from_webpage(s, web_url)
        if pdf:
            return pdf, meta

    return None, {**meta, "strategy": meta["strategy"] or "no_pdf_fields"}


def candidate_pdf_urls(url: str) -> list[str]:
    urls = []
    if url.startswith("https://www.courtlistener.com/recap/"):
        urls.append(url.replace("https://www.courtlistener.com", "https://storage.courtlistener.com", 1))
        urls.append(url)
    elif url.startswith("https://storage.courtlistener.com/recap/"):
        urls.append(url)
        urls.append(url.replace("https://storage.courtlistener.com", "https://www.courtlistener.com", 1))
    else:
        urls.append(url)

    # de-dupe while preserving order
    seen = set()
    out = []
    for u in urls:
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out


def download_pdf(pdf_url: str, out_path: Path, retries: int = 3) -> tuple[bool, dict[str, Any]]:
    headers = {"User-Agent": BROWSER_UA, "Accept": "application/pdf,*/*;q=0.8"}

    last_info = {}
    for attempt in range(retries):
        for url in candidate_pdf_urls(pdf_url):
            r = requests.get(url, headers=headers, stream=True, timeout=120, allow_redirects=True)
            info = {
                "status": r.status_code,
                "final_url": str(r.url),
                "content_type": r.headers.get("Content-Type", ""),
                "attempt": attempt + 1,
            }
            last_info = info

            # Treat 202 as "not the PDF" (pending HTML) and try the next candidate host.
            if r.status_code == 202:
                try:
                    info["body_snippet"] = r.text[:200]
                except Exception:
                    info["body_snippet"] = ""
                info["error"] = "pending_202"
                continue

            if r.status_code != 200:
                continue

            it = r.iter_content(chunk_size=1024 * 256)
            first = next(it, b"")
            if not first or not first.lstrip().startswith(b"%PDF"):
                info["error"] = "non_pdf_payload"
                try:
                    info["first_bytes"] = first[:20].decode("latin1", errors="replace")
                except Exception:
                    pass
                continue

            out_path.parent.mkdir(parents=True, exist_ok=True)
            with open(out_path, "wb") as f:
                f.write(first)
                for chunk in it:
                    if chunk:
                        f.write(chunk)
            return True, info

        time.sleep(2**attempt)

    return False, last_info


def extract_text_pypdf(pdf_path: Path, warnings_log_path: Path | None = None) -> str | None:
    try:
        # Redirect stderr (where pypdf prints a lot of parsing chatter)
        if warnings_log_path:
            warnings_log_path.parent.mkdir(parents=True, exist_ok=True)
            with open(warnings_log_path, "a", encoding="utf-8") as logf, contextlib.redirect_stderr(logf):
                reader = PdfReader(str(pdf_path), strict=False)
                parts = []
                for page in reader.pages:
                    t = page.extract_text() or ""
                    if t.strip():
                        parts.append(t)
                return "\n\n".join(parts) if parts else None
        else:
            with contextlib.redirect_stderr(io.StringIO()):
                reader = PdfReader(str(pdf_path), strict=False)
                parts = []
                for page in reader.pages:
                    t = page.extract_text() or ""
                    if t.strip():
                        parts.append(t)
                return "\n\n".join(parts) if parts else None
    except Exception:
        return None


def _alpha_count(s: str) -> int:
    return sum(ch.isalpha() for ch in s)


def looks_like_garbage_text(text: str) -> bool:
    """Detect obviously broken extraction (PDF internals instead of real text).

    Delegates to the shared implementation in ocr_decision.py.
    """
    from legallm.ocr_decision import looks_like_garbage_text as _looks_like_garbage

    return _looks_like_garbage(text)


def _append_warning(warnings_log_path: Path, msg: str) -> None:
    if not warnings_log_path:
        return
    try:
        warnings_log_path.parent.mkdir(parents=True, exist_ok=True)
        with warnings_log_path.open("a", encoding="utf-8") as f:
            f.write(msg.rstrip() + "\n")
    except Exception:
        # Don't fail the pipeline due to logging.
        pass


def extract_text_fitz(pdf_path: Path, warnings_log_path: Path) -> str | None:
    """Fallback text extraction via PyMuPDF (fitz).

    Returns None if PyMuPDF isn't available or extraction fails.
    """
    if fitz is None:
        return None
    try:
        doc = fitz.open(str(pdf_path))
        parts = []
        for page in doc:
            parts.append(page.get_text("text") or "")
        doc.close()
        return "\n".join(parts)
    except Exception as e:
        _append_warning(warnings_log_path, f"[fitz] {pdf_path.name}: {type(e).__name__}: {e}")
        return None


def get_pdf_page_count_fast(pdf_path: Path) -> int | None:
    """Best-effort page count for OCR decision density checks."""
    try:
        with contextlib.redirect_stderr(io.StringIO()):
            reader = PdfReader(str(pdf_path), strict=False)
            return len(reader.pages)
    except Exception:
        pass
    if fitz is not None:
        try:
            d = fitz.open(str(pdf_path))
            n: int = int(d.page_count)
            d.close()
            return n
        except Exception:
            return None
    return None


def is_text_better(new_text: str, old_text: str) -> bool:
    a_new = _alpha_count(new_text[:40000])
    a_old = _alpha_count(old_text[:40000])
    # Substantial improvement threshold to avoid flip-flopping.
    if a_new >= 1500 and a_new >= max(int(a_old * 1.5), a_old + 800):
        return True
    if looks_like_garbage_text(old_text) and a_new >= 800:
        return True
    return False


def extract_text_best(pdf_path: Path, warnings_log_path: Path) -> tuple[str | None, str, list[str]]:
    """Try PyPDF first, then PyMuPDF as a fallback if extraction looks unusable.

    Returns (text_or_none, extractor_name, notes).
    """
    txt = extract_text_pypdf(pdf_path, warnings_log_path)
    if not txt:
        alt = extract_text_fitz(pdf_path, warnings_log_path)
        return alt, ("pymupdf" if alt else "none"), ["no_text_from_pypdf"]

    # If it looks like headers-only or garbage, try an alternate extractor before declaring OCR.
    needs_ocr, _ocr_details = doc_needs_ocr(normalize_text(txt), page_count=None)
    if needs_ocr:
        alt = extract_text_fitz(pdf_path, warnings_log_path)
        if alt and is_text_better(alt, txt):
            return alt, "pymupdf", ["fallback_pymupdf"]

    return txt, "pypdf", []


def heading_candidates(clean: str, limit: int = 40) -> list[str]:
    upper = clean.upper()
    out = []
    for m in HEADING_LINE.finditer(upper):
        title = m.group(1).strip()
        if any(b in title for b in BAD_HEADING_FRAGMENTS):
            continue
        out.append(title)
        if len(out) >= limit:
            break
    return out


def looks_like_header_only(text: str, page_count: int | None = None) -> bool:
    """Standardized OCR decision (delegates to ocr_decision.should_ocr_document)."""
    needs, _details = doc_needs_ocr(text, page_count=page_count)
    return bool(needs)


# -----------------------------
# Scope filtering (A)
# -----------------------------
# Goal: keep a benchmark-grade slice focused on merits briefs, and avoid treating motions/orders/etc.
# as extraction failures. This changes dataset *coverage*, not the extraction logic for included docs.
BAD_SD = [
    # Only apply to short_description-like text.
    "order",
    "memorandum to counsel",
    "appendix",
    "errata",
    "mandate",
    "transcript",
]
BAD_IF_NOT_BRIEF = ["motion", "memorandum", "points and authorities"]

ROLE_KEYWORDS = ["opening", "response", "appellant", "appellee", "initial", "opposition"]


def in_scope_brief(item: dict[str, Any], exclude_motion_briefs: bool = False) -> bool:
    sd = (item.get("short_description") or "").lower()
    desc = (item.get("description") or "").lower()

    # Prefer short_description as the primary signal
    if sd:
        if "brief" not in sd:
            return False
        text = sd
    else:
        # If sd missing, fall back to description but be stricter.
        if "brief" not in desc:
            return False
        text = desc

    # Exclude amicus/reply (include amici)
    if re.search(r"\bamic(us|i)\b", text) or "reply" in text:
        return False

    # Exclude non-brief / administrative items
    if any(b in text for b in BAD_SD):
        return False

    # Exclude claim construction by default (dataset-definition choice)
    if "claim construction" in text or "construction brief" in text:
        return False

    # Exclude motion-like things that masquerade as briefs
    if any(b in text for b in BAD_IF_NOT_BRIEF):
        return False

    # Require merits-ish roles
    if not any(k in text for k in ["opening", "response", "appellant", "appellee", "initial", "opposition"]):
        return False

    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--query", type=str, required=True)
    ap.add_argument("--max_docs", type=int, default=200)
    ap.add_argument("--out_parquet", type=str, default="data/processed/facts_dataset.parquet")
    ap.add_argument("--failures_jsonl", type=str, default="data/processed/facts_failures.jsonl")
    ap.add_argument("--raw_pdf_dir", type=str, default="data/raw/pdfs")
    ap.add_argument("--dump_first", action="store_true", help="Print the first search hit JSON keys for debugging.")
    ap.add_argument(
        "--search_fields",
        type=str,
        default="id,absolute_url,download_url,short_description,document_type,description",
        help="Attempt to request these fields from Search API (if supported).",
    )
    ap.add_argument(
        "--no_scope_filter",
        action="store_true",
        help="Disable brief-scope filtering (include all PACER documents returned by search).",
    )
    ap.add_argument(
        "--exclude_motion_briefs",
        action="store_true",
        help="Exclude briefs that are actually motion/memo filings (based on description).",
    )

    # OCR integration (optional)
    ap.add_argument(
        "--enable_ocr", action="store_true", help="If set, attempt PyMuPDF+Tesseract OCR for PDFs flagged needs_ocr."
    )
    ap.add_argument("--ocr_language", type=str, default="eng")
    ap.add_argument("--ocr_dpi", type=int, default=300)
    ap.add_argument("--ocr_full", action="store_true", help="OCR the full page (default).")
    ap.add_argument("--ocr_partial", action="store_true", help="OCR image regions only (often better for mixed PDFs).")
    ap.add_argument(
        "--tessdata", type=str, default=None, help="Optional tessdata directory (overrides TESSDATA_PREFIX)."
    )
    ap.add_argument(
        "--ocr_timeout_seconds", type=int, default=900, help="Safety limit on OCR runtime per document (seconds)."
    )
    ap.add_argument(
        "--ocr_max_pages", type=int, default=300, help="Safety limit: abort OCR if PDF exceeds this many pages."
    )
    ap.add_argument(
        "--ocr_save_txt", action="store_true", help="If set, write OCR output to a .txt file next to the PDF."
    )
    ap.add_argument("--force_ocr", action="store_true", help="Force OCR on every page when OCR is invoked (slow).")
    args = ap.parse_args()

    # OCR enablement check (optional)
    ocr_enabled = False
    ocr_full = True
    if args.ocr_partial:
        ocr_full = False
    if args.ocr_full:
        ocr_full = True

    if args.enable_ocr:
        if (extract_text_with_ocr_fallback is None) or (check_ocr_ready is None):
            print("OCR requested but OCR backend is not importable; continuing without OCR.")
        else:
            ok_ocr, msg_ocr, details_ocr = check_ocr_ready(args.ocr_language, tessdata=args.tessdata)
            if ok_ocr:
                ocr_enabled = True
                print(msg_ocr)
            else:
                print("OCR requested but not ready; continuing without OCR.")
                print(msg_ocr)
                try:
                    print(json.dumps(details_ocr, indent=2))
                except Exception:
                    pass

    def _maybe_run_ocr(pdf_path: Path) -> tuple[str | None, dict[str, Any] | None]:
        """Run OCR backend for this PDF (if enabled)."""
        if not ocr_enabled:
            return None, None
        try:
            text_ocr, meta_ocr = extract_text_with_ocr_fallback(
                pdf_path,
                language=args.ocr_language,
                dpi=args.ocr_dpi,
                full=ocr_full,
                tessdata=args.tessdata,
                decision_cfg=OCR_DECISION_CFG,
                force_ocr=args.force_ocr,
                max_pages=args.ocr_max_pages,
                timeout_seconds=args.ocr_timeout_seconds,
                save_txt=args.ocr_save_txt,
            )
            return text_ocr, meta_ocr
        except TypeError:
            # Back-compat with older backend versions that don't accept decision_cfg/save_txt.
            text_ocr, meta_ocr = extract_text_with_ocr_fallback(
                pdf_path,
                language=args.ocr_language,
                dpi=args.ocr_dpi,
                full=ocr_full,
                tessdata=args.tessdata,
                max_pages=args.ocr_max_pages,
                timeout_seconds=args.ocr_timeout_seconds,
            )
            return text_ocr, meta_ocr
        except Exception as e:
            return None, {"error": f"{type(e).__name__}: {e}"}

    s = cl_session()

    hits = search_recap_documents(s, args.query, args.max_docs, args.search_fields)
    print(f"Search hits: {len(hits)}")
    if not hits:
        return

    if args.dump_first:
        first = hits[0]
        print("First hit keys:", sorted(list(first.keys()))[:200])
        print("First hit (truncated):")
        print(json.dumps(first, indent=2)[:4000])

    raw_dir = Path(args.raw_pdf_dir)
    rows = []
    failures = 0

    Path(args.failures_jsonl).parent.mkdir(parents=True, exist_ok=True)

    with open(args.failures_jsonl, "w", encoding="utf-8") as f_fail:
        for item in tqdm(hits, desc="Processing", file=sys.stdout):
            search_id = item.get("id")
            pdf_url, meta_pdf = derive_pdf_url(s, item)

            if not pdf_url:
                failures += 1
                f_fail.write(
                    json.dumps(
                        {
                            "reason": "no_pdf_url",
                            "search_id": search_id,
                            "meta": meta_pdf,
                        }
                    )
                    + "\n"
                )
                continue
            # Scope filter (A): avoid treating non-brief filings as extraction failures.
            if (not args.no_scope_filter) and (
                not in_scope_brief(item, exclude_motion_briefs=args.exclude_motion_briefs)
            ):
                failures += 1
                f_fail.write(
                    json.dumps(
                        {
                            "reason": "out_of_scope",
                            "search_id": search_id,
                            "pdf_url": pdf_url,
                            "short_description": item.get("short_description"),
                            "description": item.get("description"),
                        }
                    )
                    + "\n"
                )
                continue

            pdf_path = raw_dir / f"{search_id}.pdf"
            ok, dl_info = download_pdf(pdf_url, pdf_path)
            if not ok:
                failures += 1
                reason = "pdf_pending" if (dl_info or {}).get("status") == 202 else "pdf_download_failed"
                f_fail.write(
                    json.dumps(
                        {
                            "reason": reason,
                            "search_id": search_id,
                            "pdf_url": pdf_url,
                            "meta": meta_pdf,
                            "download_info": dl_info,
                        }
                    )
                    + "\n"
                )
                continue

            warnings_log = Path("data/processed/pdf_parse_warnings.log")
            txt_raw, text_extractor, text_extractor_notes = extract_text_best(pdf_path, warnings_log)
            ocr_meta = None

            if not txt_raw:
                # Try OCR fallback if enabled
                ocr_text, ocr_meta = _maybe_run_ocr(pdf_path)
                if ocr_text and ocr_text.strip():
                    txt_raw = ocr_text
                    text_extractor = "pymupdf_ocr_backend"
                    text_extractor_notes = (text_extractor_notes or []) + ["ocr_fallback_used"]
                else:
                    failures += 1
                    f_fail.write(
                        json.dumps(
                            {
                                "reason": "needs_ocr",
                                "search_id": search_id,
                                "pdf_url": pdf_url,
                                "notes": ["no_text_from_pdf"],
                                "text_extractor": text_extractor,
                                "text_extractor_notes": text_extractor_notes,
                                "meta": meta_pdf,
                                "ocr_meta": ocr_meta,
                            }
                        )
                        + "\n"
                    )
                    continue

            clean = normalize_text(txt_raw)
            page_count = get_pdf_page_count_fast(pdf_path)
            needs_ocr, ocr_details = doc_needs_ocr(clean, page_count=page_count)
            if needs_ocr:
                # Try OCR fallback if enabled
                ocr_text2, ocr_meta2 = _maybe_run_ocr(pdf_path)
                if ocr_text2 and ocr_text2.strip():
                    clean_ocr = normalize_text(ocr_text2)
                    needs_ocr2, ocr_details2 = doc_needs_ocr(clean_ocr, page_count=page_count)
                    if not needs_ocr2:
                        clean = clean_ocr
                        txt_raw = ocr_text2
                        ocr_meta = ocr_meta2
                        text_extractor = "pymupdf_ocr_backend"
                        text_extractor_notes = (text_extractor_notes or []) + ["ocr_fallback_used"]
                    else:
                        failures += 1
                        f_fail.write(
                            json.dumps(
                                {
                                    "reason": "needs_ocr",
                                    "search_id": search_id,
                                    "pdf_url": pdf_url,
                                    "notes": ["header_only_or_low_text_density", "still_needs_ocr_after_ocr"],
                                    "ocr_reasons": ocr_details.get("reasons"),
                                    "ocr_metrics": ocr_details.get("metrics"),
                                    "ocr_reasons_after_ocr": ocr_details2.get("reasons"),
                                    "ocr_metrics_after_ocr": ocr_details2.get("metrics"),
                                    "text_extractor": text_extractor,
                                    "text_extractor_notes": text_extractor_notes,
                                    "snippet_start": clean_ocr[:1200],
                                    "ocr_meta": ocr_meta2,
                                }
                            )
                            + "\n"
                        )
                        continue
                else:
                    failures += 1
                    f_fail.write(
                        json.dumps(
                            {
                                "reason": "needs_ocr",
                                "search_id": search_id,
                                "pdf_url": pdf_url,
                                "notes": ["header_only_or_low_text_density", "ocr_attempt_failed_or_empty"],
                                "ocr_reasons": ocr_details.get("reasons"),
                                "ocr_metrics": ocr_details.get("metrics"),
                                "text_extractor": text_extractor,
                                "text_extractor_notes": text_extractor_notes,
                                "snippet_start": clean[:1200],
                                "ocr_meta": ocr_meta2,
                            }
                        )
                        + "\n"
                    )
                    continue
            span, meta_span = extract_facts_span(clean)
            if not span:
                failures += 1
                f_fail.write(
                    json.dumps(
                        {
                            "reason": "no_facts_span",
                            "search_id": search_id,
                            "pdf_url": pdf_url,
                            "notes": meta_span.get("notes"),
                            "heading_candidates": heading_candidates(clean),
                            "snippet_start": clean[:1200],
                        }
                    )
                    + "\n"
                )
                continue

            a, b = span
            facts = clean[a:b]
            flags = quality_flags(facts)

            rows.append(
                {
                    "search_result_id": search_id,
                    "short_description": item.get("short_description"),
                    "document_type": item.get("document_type"),
                    "pdf_url": pdf_url,
                    "pdf_url_strategy": meta_pdf.get("strategy"),
                    "facts_start": a,
                    "facts_end": b,
                    "facts_text": facts,
                    "extractor_method": meta_span.get("method"),
                    "extractor_notes": ";".join(meta_span.get("notes", [])),
                    **flags,
                }
            )

    df = pd.DataFrame(rows)
    df.to_parquet(args.out_parquet, index=False)
    print(f"Wrote: {args.out_parquet}")
    print(f"Extracted facts spans: {len(df)}")
    print(f"Failures: {failures} (see {args.failures_jsonl})")


if __name__ == "__main__":
    main()

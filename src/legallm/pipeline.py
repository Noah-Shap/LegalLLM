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

from legallm.build_manifest import create_manifest, finalize_manifest, write_manifest
from legallm.citation_extractor import citation_summary, extract_citations, mask_citations
from legallm.facts_extractor import extract_facts_span, heading_candidates, quality_flags
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


def looks_like_header_only(text: str, page_count: int | None = None) -> bool:
    """Standardized OCR decision (delegates to ocr_decision.should_ocr_document)."""
    needs, _details = doc_needs_ocr(text, page_count=page_count)
    return bool(needs)


# -----------------------------
# Scope filtering (A)
# -----------------------------
# Goal: keep a benchmark-grade slice focused on merits briefs, and avoid treating motions/orders/etc.
# as extraction failures. This changes dataset *coverage*, not the extraction logic for included docs.

# Documents whose short_description starts with these are never briefs.
_NON_BRIEF_PREFIXES = [
    "order",
    "notice",
    "report and recommendation",
    "proposed order",
    "stipulation",
    "summons",
    "complaint",
    "indictment",
    "judgment",
    "verdict",
    "warrant",
    "subpoena",
    "transcript",
    "minute",
    "docket",
]

# Exclusion keywords anywhere in the text.
_EXCLUDE_KEYWORDS = [
    "appendix",
    "errata",
    "mandate",
    "transcript",
    "memorandum to counsel",
    "table of authorities",
    "certificate of service",
    "certificate of compliance",
    "corporate disclosure",
    "notice of appeal",
]

# Exclude motion-like filings even if "brief" appears in their name.
_EXCLUDE_IF_NOT_BRIEF = ["motion", "memorandum", "points and authorities"]


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

    # Exclude documents whose sd clearly indicates a non-brief filing type.
    sd_stripped = sd.strip()
    for prefix in _NON_BRIEF_PREFIXES:
        if sd_stripped.startswith(prefix):
            return False

    # Exclude amicus (include amici)
    if re.search(r"\bamic(us|i)\b", text):
        return False

    # Exclude reply briefs (dataset-definition choice: merits briefs only)
    if "reply" in text:
        return False

    # Exclude non-brief / administrative items
    if any(kw in text for kw in _EXCLUDE_KEYWORDS):
        return False

    # Exclude claim construction by default (dataset-definition choice)
    if "claim construction" in text or "construction brief" in text:
        return False

    # Exclude motion-like things that masquerade as briefs
    if any(kw in text for kw in _EXCLUDE_IF_NOT_BRIEF):
        return False

    return True


# -----------------------------
# Document-type classification
# -----------------------------
# Maps CourtListener metadata to the doc_type_id used by facts_extractor
# for heading policy decisions (e.g., whether INTRODUCTION is factual).

# CourtListener court IDs that indicate federal appellate courts.
_FEDERAL_APPELLATE_COURTS = re.compile(r"(?i)\b(ca\d{1,2}|cafc|cadc|circuit)\b")
_SCOTUS_COURTS = re.compile(r"(?i)\b(scotus|supreme\s+court\s+of\s+the\s+united\s+states)\b")
_DISTRICT_COURTS = re.compile(r"(?i)\b(district|[a-z]{2,4}d)\b")


def derive_doc_type_id(item: dict[str, Any]) -> str:
    """Derive a doc_type_id from CourtListener search result metadata.

    Uses court field, short_description, and description to classify the
    document into one of the types defined in facts_extractor.DOC_TYPE_HEADING_POLICY.
    """
    court = (item.get("court") or item.get("court_id") or "").lower()
    sd = (item.get("short_description") or "").lower()
    desc = (item.get("description") or "").lower()
    text = sd or desc

    # SCOTUS
    if _SCOTUS_COURTS.search(court) or "supreme court" in text:
        if "certiorari" in text or "petition" in text:
            return "CERT_PETITION"
        return "MERITS_SCOTUS"

    # Federal appellate
    if _FEDERAL_APPELLATE_COURTS.search(court) or "circuit" in court or "court of appeals" in text:
        if any(k in text for k in ["response", "appellee", "respondent", "answering"]):
            return "FEDERAL_APPELLATE_RESPONSE"
        return "FEDERAL_APPELLATE_OPENING"

    # District court
    if _DISTRICT_COURTS.search(court) or "district" in text:
        return "DISTRICT_COURT"

    # State appellate (heuristic: if court name doesn't match federal patterns
    # but text mentions appellate-level terms)
    if any(k in court for k in ["app", "appellate", "supreme"]):
        return "STATE_APPELLATE"

    return "UNKNOWN"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--query", type=str, required=True)
    ap.add_argument("--max_docs", type=int, default=200)
    ap.add_argument("--out_parquet", type=str, default="data/processed/facts_dataset.parquet")
    ap.add_argument("--failures_jsonl", type=str, default="data/processed/facts_failures.jsonl")
    ap.add_argument("--raw_pdf_dir", type=str, default="data/raw/pdfs")
    ap.add_argument("--manifest_json", type=str, default="data/processed/build_manifest.json")
    ap.add_argument("--dump_first", action="store_true", help="Print the first search hit JSON keys for debugging.")
    ap.add_argument(
        "--search_fields",
        type=str,
        default="id,absolute_url,download_url,short_description,document_type,description,court,court_id",
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

    # Build manifest
    build_params = {
        "query": args.query,
        "max_docs": args.max_docs,
        "enable_ocr": ocr_enabled,
        "no_scope_filter": args.no_scope_filter,
        "exclude_motion_briefs": args.exclude_motion_briefs,
    }
    manifest = create_manifest(build_params)
    print(f"Build ID: {manifest.build_id}")

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
            doc_type_id = derive_doc_type_id(item)
            span, meta_span = extract_facts_span(clean, doc_type_id=doc_type_id)
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

            # Citation extraction + masking
            cite_result = extract_citations(facts)
            cite_stats = citation_summary(cite_result)
            facts_masked = mask_citations(facts)

            rows.append(
                {
                    "search_result_id": search_id,
                    "build_id": manifest.build_id,
                    "short_description": item.get("short_description"),
                    "document_type": item.get("document_type"),
                    "doc_type_id": doc_type_id,
                    "pdf_url": pdf_url,
                    "pdf_url_strategy": meta_pdf.get("strategy"),
                    "facts_start": a,
                    "facts_end": b,
                    "facts_text": facts,
                    "facts_text_masked": facts_masked,
                    "extractor_method": meta_span.get("method"),
                    "extractor_notes": ";".join(meta_span.get("notes", [])),
                    "extractor_confidence": meta_span.get("confidence"),
                    **flags,
                    **cite_stats,
                }
            )

    df = pd.DataFrame(rows)
    df.to_parquet(args.out_parquet, index=False)
    print(f"Wrote: {args.out_parquet}")
    print(f"Extracted facts spans: {len(df)}")
    print(f"Failures: {failures} (see {args.failures_jsonl})")

    # Write build manifest
    results = {
        "total_hits": len(hits),
        "extracted_spans": len(df),
        "failures": failures,
    }
    finalize_manifest(manifest, results)
    manifest_path = write_manifest(manifest, args.manifest_json)
    print(f"Manifest: {manifest_path}")


if __name__ == "__main__":
    main()

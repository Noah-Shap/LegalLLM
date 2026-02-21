"""
Shared OCR decision heuristics.

Goal
----
Provide ONE standard way to decide:
  1) whether a document likely needs OCR, and
  2) whether an individual page likely needs OCR,

so multiple modules (pipeline, PyMuPDF OCR backend, etc.) don't drift.

Design
------
- Pure standard library (no PyMuPDF / pypdf imports).
- Returns (decision, details) where details includes reasons + metrics.
- Tunable via OcrDecisionConfig.

This module is intentionally conservative: it tries to catch common court-filing
failure modes such as:
  - "stamp-only" extraction (PACER/ECF header overlay extracted, body is image-only)
  - garbage extraction (PDF internals like /i255 tokens, extremely low alpha ratio)
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional, Tuple
import re


# -----------------------------
# Config
# -----------------------------

@dataclass(frozen=True)
class OcrDecisionConfig:
    # Page-level heuristics (used by selective OCR)
    page_min_chars: int = 120                    # non-whitespace chars
    page_min_word_count: int = 35                # alphabetic tokens of length >=2
    page_min_alpha_ratio: float = 0.35           # alphabetic / non-whitespace chars
    page_max_weird_token_ratio: float = 0.20     # tokens like /i255
    page_stamp_only_min_body_chars: int = 60     # after stripping stamps, body chars required

    # Document-level heuristics (used by pipeline to decide "needs_ocr")
    doc_min_total_chars: int = 1200              # very small total text => likely OCR
    doc_min_chars_per_page: int = 600            # if page_count known, skip OCR if above
    doc_header_sample_lines: int = 400           # number of non-empty lines sampled from head
    doc_header_line_frac: float = 0.80           # fraction of header-like lines in sample
    doc_min_deheaded_len: int = 1200             # remaining chars after header removal
    doc_min_deheaded_alpha: int = 600            # remaining alpha chars after header removal
    doc_stamp_only_min_body_chars: int = 600     # after stripping stamps across doc head, body chars required

    # Garbage detection (doc+page)
    garbage_token_pattern: str = r"/i\d{2,}"      # PDF internal tokens seen in broken extraction
    garbage_min_alpha_chars: int = 300
    garbage_max_alpha_ratio: float = 0.02         # alpha/len threshold (very low => likely garbage)


# -----------------------------
# Regex / parsing helpers
# -----------------------------

_WEIRD_TOKEN_RE = re.compile(r"^/?[A-Za-z]\d{2,}$")     # e.g. /i255, x1234
_WORD_RE = re.compile(r"[A-Za-z]{2,}")

# PACER/ECF-ish stamp line patterns
_STAMP_LINE_RE = re.compile(
    r"\bCase\s+\d{1,2}:\d{2,4}-[a-z]{2,3}-\d+\b.*\bDocument\s+\d+\b.*\bFiled\s+\d{1,2}/\d{1,2}/\d{2,4}\b",
    re.IGNORECASE,
)
_PAGEID_RE = re.compile(r"\bPage\s+\d+\s+of\s+\d+\b.*\bPageID\b", re.IGNORECASE)

# Broader header signals used historically in the pipeline
_RE_PACER_HEADER = re.compile(r"(?i)\bcase\b.*\bdocument\b.*\bfiled\b.*\bpage\b")
_RE_CA3_HEADER = re.compile(r"(?i)^case:\s*\d", re.M)


def page_text_metrics(text: str) -> Dict[str, float]:
    """Compute quality metrics for a text chunk."""
    s = text or ""
    non_ws = "".join(ch for ch in s if not ch.isspace())
    n = len(non_ws)
    if n == 0:
        return {
            "chars": 0.0,
            "alpha_ratio": 0.0,
            "weird_token_ratio": 0.0,
            "word_count": 0.0,
            "unique_word_count": 0.0,
            "nonempty_lines": 0.0,
        }

    alpha = sum(ch.isalpha() for ch in non_ws)
    alpha_ratio = alpha / n

    tokens = re.findall(r"\S+", s)
    if not tokens:
        weird_ratio = 0.0
    else:
        weird = sum(1 for t in tokens if _WEIRD_TOKEN_RE.match(t) is not None)
        weird_ratio = weird / len(tokens)

    words = _WORD_RE.findall(s)
    word_count = len(words)
    unique_word_count = len({w.lower() for w in words})

    nonempty_lines = sum(1 for ln in s.splitlines() if ln.strip())

    return {
        "chars": float(n),
        "alpha_ratio": float(alpha_ratio),
        "weird_token_ratio": float(weird_ratio),
        "word_count": float(word_count),
        "unique_word_count": float(unique_word_count),
        "nonempty_lines": float(nonempty_lines),
    }


def strip_pacer_ecf_stamps(text: str) -> str:
    """Remove obvious PACER/ECF header stamp lines."""
    kept: List[str] = []
    for ln in (text or "").splitlines():
        s = ln.strip()
        if not s:
            continue
        if _STAMP_LINE_RE.search(s) or _PAGEID_RE.search(s):
            continue
        # broader patterns
        if _RE_PACER_HEADER.search(s) or _RE_CA3_HEADER.search(s):
            continue
        kept.append(ln)
    return "\n".join(kept)


def looks_like_garbage_text(text: str, cfg: OcrDecisionConfig = OcrDecisionConfig()) -> bool:
    """Detect broken extraction that yields PDF internals instead of real text."""
    if not text:
        return True
    head = text[:30000]
    if re.search(cfg.garbage_token_pattern, head):
        return True
    non_ws = "".join(ch for ch in head if not ch.isspace())
    if not non_ws:
        return True
    alpha = sum(ch.isalpha() for ch in non_ws)
    if alpha < cfg.garbage_min_alpha_chars:
        if (alpha / max(len(non_ws), 1)) < cfg.garbage_max_alpha_ratio:
            return True
    return False


def looks_like_stamp_only(text: str, min_body_chars: int) -> bool:
    """True if, after removing stamp lines, there is essentially no remaining body text."""
    body = strip_pacer_ecf_stamps(text)
    body_non_ws = "".join(ch for ch in body if not ch.isspace())
    return len(body_non_ws) < min_body_chars


# -----------------------------
# Decisions
# -----------------------------

def should_ocr_page(
    page_text: str,
    cfg: OcrDecisionConfig = OcrDecisionConfig(),
) -> Tuple[bool, Dict[str, Any]]:
    """
    Decide whether a single page should be OCR'd.

    Returns:
      (should_ocr, details) where details includes:
        - reasons: list[str]
        - metrics: page_text_metrics
        - cfg: config as dict (for logging)
    """
    reasons: List[str] = []
    metrics = page_text_metrics(page_text)

    if looks_like_garbage_text(page_text, cfg):
        reasons.append("garbage_text")

    if looks_like_stamp_only(page_text, cfg.page_stamp_only_min_body_chars):
        reasons.append("stamp_only")

    if metrics["chars"] < cfg.page_min_chars:
        reasons.append("too_few_chars")
    if metrics["word_count"] < cfg.page_min_word_count:
        reasons.append("too_few_words")
    if metrics["alpha_ratio"] < cfg.page_min_alpha_ratio:
        reasons.append("low_alpha_ratio")
    if metrics["weird_token_ratio"] > cfg.page_max_weird_token_ratio:
        reasons.append("weird_token_ratio")

    return (len(reasons) > 0), {"reasons": reasons, "metrics": metrics, "cfg": asdict(cfg)}


def should_ocr_document(
    doc_text: str,
    *,
    page_count: Optional[int] = None,
    cfg: OcrDecisionConfig = OcrDecisionConfig(),
) -> Tuple[bool, Dict[str, Any]]:
    """
    Decide whether a *document* likely needs OCR (i.e., extracted text is insufficient).

    Intended use:
      - after best-effort extraction (pypdf/fitz), before logging "needs_ocr"
      - to decide whether to attempt OCR or treat as usable text

    Returns:
      (should_ocr, details) where details includes reasons + metrics.
    """
    reasons: List[str] = []
    txt = doc_text or ""

    if not txt.strip():
        reasons.append("no_text")

    # Total length signals
    non_ws = "".join(ch for ch in txt if not ch.isspace())
    total_chars = len(non_ws)
    if total_chars < cfg.doc_min_total_chars:
        reasons.append("too_little_text")

    # Garbage extraction signals
    if looks_like_garbage_text(txt, cfg):
        reasons.append("garbage_text")

    # Stamp-only / header-only signals (on the head portion)
    head = txt[:20000]
    if looks_like_stamp_only(head, cfg.doc_stamp_only_min_body_chars):
        reasons.append("stamp_only_head")

    # Header-line fraction signals (pipeline-style)
    lines = [ln.strip() for ln in head.splitlines() if ln.strip()]
    sample = lines[: cfg.doc_header_sample_lines]
    header_lines = [ln for ln in sample if (_RE_PACER_HEADER.search(ln) or _RE_CA3_HEADER.search(ln) or _STAMP_LINE_RE.search(ln) or _PAGEID_RE.search(ln))]
    header_frac = len(header_lines) / max(1, len(sample))
    deheaded = "\n".join([ln for ln in sample if ln not in header_lines])
    deheaded_non_ws = "".join(ch for ch in deheaded if not ch.isspace())
    deheaded_len = len(deheaded_non_ws)
    deheaded_alpha = sum(ch.isalpha() for ch in deheaded_non_ws)

    if header_frac >= cfg.doc_header_line_frac and deheaded_len < cfg.doc_min_deheaded_len and deheaded_alpha < cfg.doc_min_deheaded_alpha:
        reasons.append("header_only")

    # If page count is known and text density is good, override some weak reasons.
    chars_per_page = None
    if page_count and page_count > 0:
        chars_per_page = total_chars / page_count
        if chars_per_page >= cfg.doc_min_chars_per_page:
            # Keep only strong reasons (garbage), drop weak "too_little_text"/header heuristics.
            reasons = [r for r in reasons if r in ("garbage_text", "no_text")]

    details = {
        "reasons": reasons,
        "metrics": {
            "total_chars": total_chars,
            "page_count": page_count,
            "chars_per_page": chars_per_page,
            "header_frac": header_frac,
            "deheaded_len": deheaded_len,
            "deheaded_alpha": deheaded_alpha,
        },
        "cfg": asdict(cfg),
    }
    return (len(reasons) > 0), details

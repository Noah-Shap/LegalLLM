"""Streamlit gold-set labeler (C5). Launch with ``legallm-gold label`` (needs ``pip install -e ".[label]"``).

Per document: read the rubric, inspect the rules_v2 span in context, rate it,
optionally correct the boundaries (paste verbatim start/end anchors or edit
offsets), and save. Labels go to evals/gold/gold_v1.jsonl (ids + offsets only).
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import cast

import streamlit as st

from legallm.gold import GoldRecord, Rating, load_gold, save_gold, set_label, stats, verify_record
from legallm.llm_extractor import find_anchor
from legallm.single_doc import extract_from_file

RATINGS = ["correct", "partially_correct", "incorrect"]
PREVIEW = 500


def _args() -> argparse.Namespace:
    ap = argparse.ArgumentParser()
    ap.add_argument("--gold", type=Path, default=Path(os.environ.get("LEGALLM_GOLD_PATH", "evals/gold/gold_v1.jsonl")))
    ap.add_argument("--labeler", default=os.environ.get("LEGALLM_LABELER", "noah"))
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    return ap.parse_known_args(argv)[0]


@st.cache_data(show_spinner="extracting document text…")
def doc_text_for(pdf_path: str) -> str:
    return extract_from_file(pdf_path, method="rules_v2", require_facts=False).doc_text


def _load(path: Path) -> list[GoldRecord]:
    if "records" not in st.session_state:
        st.session_state.records = load_gold(path)
    return cast(list[GoldRecord], st.session_state.records)


def _save_one(path: Path, rec: GoldRecord) -> list[GoldRecord]:
    """Write-through save: reload the file, replace this record, save, refresh the session copy.

    Another process (legallm-gold prefill / accept-judge, a second labeler tab) may have changed
    other records since this session loaded the file; rewriting from the session copy would
    silently discard those changes.
    """
    fresh = load_gold(path)
    for i, r in enumerate(fresh):
        if r.gold_id == rec.gold_id:
            fresh[i] = rec
            break
    else:
        fresh.append(rec)
    save_gold(fresh, path)
    st.session_state.records = fresh
    return fresh


def _marked(doc: str, span: list[int] | None) -> str:
    if not span:
        return doc
    s, e = span
    return doc[:s] + "⟦⟦⟦ " + doc[s:e] + " ⟧⟧⟧" + doc[e:]


def main() -> None:
    args = _args()
    st.set_page_config(page_title="Gold labeler", layout="wide")
    records = _load(args.gold)
    ids = [r.gold_id for r in records]

    # ---------------- sidebar: progress + navigation
    with st.sidebar:
        st.title("Gold labeler")
        s = stats(records)
        done = s["by_status"].get("labeled", 0)
        st.progress(done / max(len(records), 1), text=f"{done}/{len(records)} labeled")
        st.caption(
            f"boundary corrected: {s['boundary_corrected']} (low/med {s['boundary_corrected_low_medium']}) · "
            f"ratings: {s['ratings']}"
        )
        review_path = args.gold.with_name("review_set_v1.txt")
        review_ids: list[str] = []
        if review_path.exists():
            review_ids = [ln.strip() for ln in review_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
        choices = ["pending", "all", "labeled", "judge-labeled", "skipped"] + (["review set"] if review_ids else [])
        flt = st.radio("Show", choices, horizontal=True)
        src = st.radio("Source", ["all", "audit_set", "no_facts_span"], horizontal=True)

        def _show(r: GoldRecord) -> bool:
            if flt == "all":
                ok = True
            elif flt == "judge-labeled":
                ok = r.status == "labeled" and not r.is_human_labeled
            elif flt == "review set":
                ok = r.gold_id in review_ids and not r.is_human_labeled
            else:
                ok = r.status == flt
            return ok and (src == "all" or r.source == src)

        visible = [r for r in records if _show(r)]
        if flt == "review set":
            visible.sort(key=lambda r: review_ids.index(r.gold_id))
            n_done = sum(1 for r in records if r.gold_id in review_ids and r.is_human_labeled)
            st.caption(f"review set: {n_done}/{len(review_ids)} reviewed by you")
        if not visible:
            st.success("Nothing left in this filter.")
            st.stop()
        vis_ids = [r.gold_id for r in visible]
        if "cur" not in st.session_state or st.session_state.cur not in vis_ids:
            st.session_state.cur = vis_ids[0]
        pos = vis_ids.index(st.session_state.cur)
        st.session_state.cur = st.selectbox(
            "Document", vis_ids, index=pos, format_func=lambda g: f"{g} · {records[ids.index(g)].search_result_id}"
        )
        c1, c2 = st.columns(2)
        if c1.button("◀ prev", key="prev", use_container_width=True) and pos > 0:
            st.session_state.cur = vis_ids[pos - 1]
            st.rerun()
        if c2.button("next ▶", key="next", use_container_width=True) and pos < len(vis_ids) - 1:
            st.session_state.cur = vis_ids[pos + 1]
            st.rerun()
        with st.expander("Rubric"):
            st.markdown(
                "- **correct**: span substantially captures the narrative facts/background; not dominated by "
                "argument, TOA/TOC, or boilerplate.\n"
                "- **partially_correct**: captures some facts but includes significant non-facts content or "
                "misses key facts sections.\n"
                "- **incorrect**: mostly argument, TOC, boilerplate, or unrelated content.\n\n"
                "See `evals/gold/LABELING_GUIDE.md` for boundary rules."
            )

    rec = records[ids.index(st.session_state.cur)]
    doc = doc_text_for(rec.pdf_path)
    problems = verify_record(rec, doc)

    # ---------------- header
    st.subheader(f"{rec.gold_id} · search_result_id {rec.search_result_id} · {rec.source}")
    meta_cols = st.columns(5)
    meta_cols[0].metric("status", rec.status)
    meta_cols[1].metric("rules confidence", rec.rules_confidence or "—")
    meta_cols[2].metric("len bin", rec.stratum.get("len_bin", "—"))
    meta_cols[3].metric("doc chars", f"{len(doc):,}")
    meta_cols[4].metric("rules span", f"{rec.rules_span[0]}–{rec.rules_span[1]}" if rec.rules_span else "none")
    if rec.rules_notes:
        st.caption(f"rules notes: {rec.rules_notes}")
    if rec.pdf_url:
        st.caption(f"[source PDF]({rec.pdf_url})")
    for p in problems:
        st.error(p)

    # ---------------- span editing state
    key = f"span_{rec.gold_id}"
    if key not in st.session_state:
        st.session_state[key] = list(rec.label.gold_span or rec.rules_span or [0, min(len(doc), 2000)])
    span = st.session_state[key]

    # ---------------- judge suggestion (pre-label), if any
    sug = rec.suggestion
    if sug:
        with st.container(border=True):
            st.markdown(
                f"**Judge suggestion** (`{sug.get('judge_model')}`, confidence **{sug.get('confidence')}**) · "
                f"kind: `{sug.get('document_kind')}` · has facts: **{'yes' if sug.get('has_facts') else 'no'}** · "
                f"rules span rated **{sug.get('rules_rating') or '—'}** · preferred: {sug.get('preferred')}"
            )
            st.caption(sug.get("summary", ""))
            for m, iss in (sug.get("issues") or {}).items():
                st.caption(f"{m}: {', '.join(iss)} — {(sug.get('comments') or {}).get(m, '')}")
            j1, j2 = st.columns(2)
            if sug.get("suggested_span") and j1.button(
                f"Load suggested span ({sug.get('span_basis')})", key=f"sugload_{rec.gold_id}"
            ):
                st.session_state[key] = list(sug["suggested_span"])
                st.rerun()
            if j2.button("Accept suggestion as my label", key=f"sugacc_{rec.gold_id}"):
                rating = sug.get("rules_rating") if rec.rules_span else None
                set_label(
                    rec,
                    rating=cast(Rating | None, rating),
                    has_facts=bool(sug.get("has_facts")),
                    gold_span=sug.get("suggested_span") if sug.get("has_facts") else None,
                    notes=f"[accepted judge] {sug.get('summary', '')}",
                    labeler=args.labeler,
                )
                _save_one(args.gold, rec)
                st.toast(f"accepted judge suggestion for {rec.gold_id}")
                if pos < len(vis_ids) - 1:
                    st.session_state.cur = vis_ids[pos + 1]
                st.rerun()

    left, right = st.columns([1, 1])
    with left:
        st.markdown("**Rules_v2 span (as extracted)**")
        if rec.rules_span:
            rs, re_ = rec.rules_span
            st.code(
                doc[rs : rs + PREVIEW]
                + ("\n…\n" if re_ - rs > 2 * PREVIEW else "")
                + doc[max(rs, re_ - PREVIEW) : re_],
                language=None,
            )
        else:
            st.info("rules_v2 found no span. Locate the facts section (or mark has_facts = no).")

    with right:
        st.markdown("**Gold span (edit)**")
        a1, a2 = st.columns(2)
        start_anchor = a1.text_input("start anchor (verbatim first words)", key=f"sa_{rec.gold_id}")
        end_anchor = a2.text_input("end anchor (verbatim last words)", key=f"ea_{rec.gold_id}")
        if st.button("Locate anchors", key=f"loc_{rec.gold_id}"):
            new = list(span)
            if start_anchor.strip():
                hit = find_anchor(doc, start_anchor)
                if hit:
                    new[0] = hit[0]
                else:
                    st.warning("start anchor not found")
            if end_anchor.strip():
                hit = find_anchor(doc, end_anchor, start_at=new[0])
                if hit:
                    new[1] = hit[1]
                else:
                    st.warning("end anchor not found")
            st.session_state[key] = new
            st.rerun()
        n1, n2 = st.columns(2)
        span[0] = int(
            n1.number_input("start", min_value=0, max_value=len(doc), value=int(span[0]), key=f"s_{rec.gold_id}")
        )
        span[1] = int(
            n2.number_input("end", min_value=0, max_value=len(doc), value=int(span[1]), key=f"e_{rec.gold_id}")
        )
        if span[1] > span[0]:
            st.caption(f"{span[1] - span[0]:,} chars")
            st.code(
                doc[span[0] : span[0] + PREVIEW] + "\n…\n" + doc[max(span[0], span[1] - PREVIEW) : span[1]],
                language=None,
            )
        else:
            st.warning("end must be greater than start")

    with st.expander("Full document text (gold span marked with ⟦⟦⟦ … ⟧⟧⟧)", expanded=False):
        st.text_area("doc", _marked(doc, span if span[1] > span[0] else None), height=600, label_visibility="collapsed")

    # ---------------- label form
    st.markdown("---")
    f1, f2, f3 = st.columns([1, 1, 2])
    rating = f1.radio(
        "Rating of rules_v2 span",
        RATINGS,
        index=RATINGS.index(rec.label.rating) if rec.label.rating in RATINGS else None,
        key=f"r_{rec.gold_id}",
        disabled=rec.rules_span is None,
    )
    has_facts = f2.radio(
        "Brief has a facts section?",
        ["yes", "no"],
        index=(0 if rec.label.has_facts in (None, True) else 1),
        key=f"hf_{rec.gold_id}",
    )
    corrected = f2.checkbox(
        "Save gold span (boundary correction)",
        value=True,
        key=f"c_{rec.gold_id}",
        help="On by default: the current span is saved as gold even if identical to rules. Untick to rate only.",
    )
    notes = f3.text_area("Notes", value=rec.label.notes, key=f"n_{rec.gold_id}", height=120)

    b1, b2, b3 = st.columns(3)
    if b1.button("💾 Save & next", key="save", type="primary", use_container_width=True):
        gs = span if (corrected and has_facts == "yes" and span[1] > span[0]) else None
        try:
            set_label(
                rec,
                rating=cast(Rating | None, rating),
                has_facts=(has_facts == "yes"),
                gold_span=gs,
                notes=notes,
                labeler=args.labeler,
            )
            _save_one(args.gold, rec)
            st.toast(f"saved {rec.gold_id}")
            if pos < len(vis_ids) - 1:
                st.session_state.cur = vis_ids[pos + 1]
            st.rerun()
        except ValueError as e:
            st.error(str(e))
    if b2.button("⏭ Skip", key="skip", use_container_width=True):
        rec.status = "skipped"
        rec.label.notes = notes
        _save_one(args.gold, rec)
        if pos < len(vis_ids) - 1:
            st.session_state.cur = vis_ids[pos + 1]
        st.rerun()
    if b3.button("↺ Reset span to rules", key="reset", use_container_width=True):
        st.session_state[key] = list(rec.rules_span or [0, min(len(doc), 2000)])
        st.rerun()


main()

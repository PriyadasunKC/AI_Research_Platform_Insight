"""pages/history.py - Pipeline run history stored in MongoDB."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st

_CARD_OPEN  = '<div class="kg-card">'
_CARD_CLOSE = '</div>'

# ── Colour helpers ────────────────────────────────────────────────────────────

_LABEL_COLORS: dict[str, str] = {
    "PERSON_KING":  "#ef5350",
    "PERSON_MONK":  "#42a5f5",
    "PERSON_OTHER": "#ab47bc",
    "LOCATION":     "#66bb6a",
    "MONUMENT":     "#ffa726",
    "DYNASTY":      "#7e57c2",
    "BATTLE_EVENT": "#ec407a",
    "DATE_ERA":     "#26a69a",
    "CHRONICLE":    "#78909c",
    "RELIC":        "#ffca28",
}

_LABEL_BG: dict[str, str] = {
    "PERSON_KING":  "rgba(239,83,80,0.12)",
    "PERSON_MONK":  "rgba(66,165,245,0.12)",
    "PERSON_OTHER": "rgba(171,71,188,0.12)",
    "LOCATION":     "rgba(102,187,106,0.12)",
    "MONUMENT":     "rgba(255,167,38,0.12)",
    "DYNASTY":      "rgba(126,87,194,0.12)",
    "BATTLE_EVENT": "rgba(236,64,122,0.12)",
    "DATE_ERA":     "rgba(38,166,154,0.12)",
    "CHRONICLE":    "rgba(120,144,156,0.12)",
    "RELIC":        "rgba(255,202,40,0.12)",
}


def _tag_pill(entity: str, label: str) -> str:
    fg = _LABEL_COLORS.get(label, "#78909c")
    bg = _LABEL_BG.get(label, "rgba(120,144,156,0.12)")
    return (
        f'<span style="background:{bg};border:1px solid {fg}55;color:{fg};'
        f'border-radius:6px;padding:3px 10px;margin:2px 3px;display:inline-block;'
        f'font-family:\'Noto Sans Sinhala\',sans-serif;font-size:.85em;font-weight:600">'
        f'{entity}'
        f'<span style="font-family:\'Inter\',sans-serif;font-size:.65em;'
        f'opacity:.7;margin-left:5px">{label}</span></span>'
    )


def _triple_row(triple: dict) -> str:
    subj = triple.get("subject", "")
    rel  = triple.get("relation", "")
    obj  = triple.get("object",  "")
    return (
        f'<div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap;'
        f'margin:6px 0;padding:8px 14px;background:rgba(92,107,192,0.08);'
        f'border:1px solid rgba(92,107,192,0.2);border-radius:10px">'
        f'<span style="color:#90caf9;font-family:\'Noto Sans Sinhala\',sans-serif;'
        f'font-weight:600;font-size:.9em">{subj}</span>'
        f'<span style="color:#7986cb;font-family:\'Inter\',sans-serif;'
        f'font-weight:700;font-size:.8em;white-space:nowrap">── {rel} ──▶</span>'
        f'<span style="color:#a5d6a7;font-family:\'Noto Sans Sinhala\',sans-serif;'
        f'font-weight:600;font-size:.9em">{obj}</span>'
        f'</div>'
    )


# ── Summary metrics ───────────────────────────────────────────────────────────

def _render_stats(stats: dict) -> None:
    st.markdown('<div class="kg-section-title">Overview</div>', unsafe_allow_html=True)
    m1, m2, m3, m4 = st.columns(4)
    metrics = [
        (m1, stats.get("total_runs",     0), "Total Runs",       "#7986cb"),
        (m2, stats.get("kg_saved_runs",  0), "Saved to KG",      "#81c784"),
        (m3, stats.get("total_entities", 0), "Entities Tagged",  "#ffb74d"),
        (m4, stats.get("total_triples",  0), "Triples Extracted","#f48fb1"),
    ]
    for col, val, label, color in metrics:
        col.markdown(
            f'<div class="kg-metric-card">'
            f'<div class="kg-metric-value" style="color:{color}">{val}</div>'
            f'<div class="kg-metric-label">{label}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )


# ── Run list table ────────────────────────────────────────────────────────────

def _render_run_list(runs: list[dict]) -> str | None:
    """Render the run list and return the _id of the selected run (or None)."""
    import pandas as pd

    st.markdown('<div class="kg-section-title">Recent Runs</div>', unsafe_allow_html=True)
    st.markdown(_CARD_OPEN, unsafe_allow_html=True)

    # Search / filter
    search = st.text_input(
        "Filter by sentence content",
        placeholder="e.g. දුටුගැමුණු",
        key="hist_search",
    )

    df_rows = []
    for r in runs:
        text = r.get("input_text", "")
        if search and search.lower() not in text.lower():
            continue
        ts  = r.get("timestamp", "")[:19].replace("T", "  ")
        kg  = "✅" if r.get("kg_saved") else "-"
        df_rows.append({
            "_id":       r["_id"],
            "Timestamp": ts,
            "Sentence":  text[:70] + ("…" if len(text) > 70 else ""),
            "Entities":  r.get("ner_entity_count", 0),
            "Triples":   r.get("triple_count",     0),
            "KG Saved":  kg,
            "Provider":  r.get("llm_provider", ""),
        })

    if not df_rows:
        st.info("No runs match the filter." if search else "No runs recorded yet.")
        st.markdown(_CARD_CLOSE, unsafe_allow_html=True)
        return None

    df = pd.DataFrame(df_rows)
    ids = df["_id"].tolist()
    display_df = df.drop(columns=["_id"])
    st.dataframe(display_df, width="stretch", hide_index=True)

    selected_label = st.selectbox(
        "Select a run to inspect",
        options=ids,
        format_func=lambda rid: next(
            (r["Timestamp"] + "  -  " + r["Sentence"]
             for r in df_rows if r["_id"] == rid), rid
        ),
        key="hist_selected",
    )
    st.markdown(_CARD_CLOSE, unsafe_allow_html=True)
    return selected_label


# ── Run detail panel ──────────────────────────────────────────────────────────

def _render_run_detail(run: dict) -> None:
    st.markdown('<div class="kg-section-title">Run Detail</div>', unsafe_allow_html=True)
    st.markdown(_CARD_OPEN, unsafe_allow_html=True)

    ts  = run.get("timestamp", "")[:19].replace("T", "  ")
    kg  = run.get("kg_saved", False)

    # Header row
    h1, h2, h3 = st.columns([3, 2, 1])
    with h1:
        st.markdown(
            f'<div style="font-family:\'Inter\',sans-serif;font-size:.75em;'
            f'color:rgba(255,255,255,.4)">Timestamp</div>'
            f'<div style="font-family:\'Inter\',sans-serif;color:#f0f2f6;'
            f'font-size:.95em">{ts}</div>',
            unsafe_allow_html=True,
        )
    with h2:
        st.markdown(
            f'<div style="font-family:\'Inter\',sans-serif;font-size:.75em;'
            f'color:rgba(255,255,255,.4)">LLM</div>'
            f'<div style="font-family:\'Inter\',sans-serif;color:#7986cb;'
            f'font-size:.9em;font-weight:600">'
            f'{run.get("llm_provider","?")} / '
            f'<code style="color:#80cbc4">{run.get("llm_model","?")}</code></div>',
            unsafe_allow_html=True,
        )
    with h3:
        badge_color = "#81c784" if kg else "rgba(255,255,255,.3)"
        badge_text  = "KG Saved" if kg else "Not in KG"
        st.markdown(
            f'<div style="font-family:\'Inter\',sans-serif;font-size:.75em;'
            f'color:rgba(255,255,255,.4)">Status</div>'
            f'<div style="color:{badge_color};font-family:\'Inter\',sans-serif;'
            f'font-size:.85em;font-weight:600">{badge_text}</div>',
            unsafe_allow_html=True,
        )

    st.markdown("<br>", unsafe_allow_html=True)

    # Input sentence
    st.markdown(
        '<div style="font-family:\'Inter\',sans-serif;font-size:.75em;font-weight:700;'
        'letter-spacing:.06em;text-transform:uppercase;color:rgba(255,255,255,.4);'
        'margin-bottom:6px">Input Sentence</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        f'<div style="font-family:\'Noto Sans Sinhala\',sans-serif;font-size:1.05em;'
        f'line-height:1.9;padding:14px 18px;background:rgba(255,255,255,0.03);'
        f'border:1px solid rgba(255,255,255,0.07);border-radius:10px;color:#f0f2f6">'
        f'{run.get("input_text","")}</div>',
        unsafe_allow_html=True,
    )

    st.markdown("<br>", unsafe_allow_html=True)

    col_left, col_right = st.columns(2, gap="large")

    # NER tags
    with col_left:
        st.markdown(
            '<div style="font-family:\'Inter\',sans-serif;font-size:.75em;font-weight:700;'
            'letter-spacing:.06em;text-transform:uppercase;color:rgba(255,255,255,.4);'
            'margin-bottom:8px">Named Entities</div>',
            unsafe_allow_html=True,
        )
        tags = run.get("ner_tags", [])
        if tags:
            pills = "".join(_tag_pill(t["entity"], t["label"]) for t in tags)
            st.markdown(
                f'<div style="line-height:2.4">{pills}</div>',
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                '<span style="color:rgba(255,255,255,.3);font-size:.85em">None</span>',
                unsafe_allow_html=True,
            )

    # Validated triples
    with col_right:
        st.markdown(
            '<div style="font-family:\'Inter\',sans-serif;font-size:.75em;font-weight:700;'
            'letter-spacing:.06em;text-transform:uppercase;color:rgba(255,255,255,.4);'
            'margin-bottom:8px">Validated Triples</div>',
            unsafe_allow_html=True,
        )
        triples = run.get("validated_triples", [])
        if triples:
            for t in triples:
                st.markdown(_triple_row(t), unsafe_allow_html=True)
        else:
            st.markdown(
                '<span style="color:rgba(255,255,255,.3);font-size:.85em">None</span>',
                unsafe_allow_html=True,
            )

    # Raw LLM response (collapsible)
    raw = run.get("llm_raw_response", "")
    parsed = run.get("llm_parsed_triples", [])
    if raw or parsed:
        with st.expander("Raw LLM Response", expanded=False):
            if raw:
                st.markdown(
                    f'<div style="font-family:\'Fira Code\',monospace;font-size:.8em;'
                    f'line-height:1.7;background:rgba(0,0,0,0.3);padding:14px 18px;'
                    f'border-radius:8px;color:#b0bec5;border:1px solid rgba(255,255,255,0.06);'
                    f'white-space:pre-wrap;word-break:break-word">{raw}</div>',
                    unsafe_allow_html=True,
                )
            if parsed:
                st.markdown("**Pre-validation parsed triples:**")
                st.json(parsed)

    st.markdown(_CARD_CLOSE, unsafe_allow_html=True)


# ── Page entry point ──────────────────────────────────────────────────────────

def render() -> None:
    st.markdown("""
    <div class="kg-page-title">🗂️ Run History</div>
    <div class="kg-page-subtitle">
      All pipeline executions saved to MongoDB - input sentences, NER tags,
      LLM responses, and extracted triples.
    </div>
    """, unsafe_allow_html=True)

    col_ref, _ = st.columns([1, 4])
    with col_ref:
        if st.button("Refresh", type="secondary", width="stretch"):
            st.rerun()

    try:
        from mongo_store import get_recent_runs, get_run_stats, get_run_by_id
    except ImportError:
        st.error("pymongo is not installed. Run: `pip install pymongo`")
        st.stop()

    stats = get_run_stats()
    if "error" in stats:
        st.warning(f"MongoDB not reachable: {stats['error']}")
        st.info(
            "Set `MONGO_URI` and `MONGO_DB` in your `.env` and make sure "
            "MongoDB is running."
        )
        st.stop()

    _render_stats(stats)
    st.markdown("<br>", unsafe_allow_html=True)

    runs = get_recent_runs(limit=100)
    selected_id = _render_run_list(runs)

    if selected_id:
        st.markdown("<br>", unsafe_allow_html=True)
        run = get_run_by_id(selected_id)
        if run:
            _render_run_detail(run)
        else:
            st.warning("Could not load run details.")

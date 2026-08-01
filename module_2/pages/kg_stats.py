"""pages/kg_stats.py - Knowledge Graph Statistics page."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st

_CARD_OPEN  = '<div class="kg-card">'
_CARD_CLOSE = '</div>'


# ── Sub-section renderers ─────────────────────────────────────────────────────

def _render_summary_metrics(nodes: dict[str, int], edges: dict[str, int]) -> None:
    st.markdown('<div class="kg-section-title">Overview</div>', unsafe_allow_html=True)
    m1, m2, m3, m4 = st.columns(4)
    metrics = [
        (m1, sum(nodes.values()), "Total Nodes",         "#7986cb"),
        (m2, sum(edges.values()), "Total Relationships", "#81c784"),
        (m3, len(nodes),          "Node Types",          "#ffb74d"),
        (m4, len(edges),          "Relation Types",      "#f48fb1"),
    ]
    for col, val, label, color in metrics:
        col.markdown(
            f'<div class="kg-metric-card">'
            f'<div class="kg-metric-value" style="color:{color}">{val}</div>'
            f'<div class="kg-metric-label">{label}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )


def _render_nodes_chart(nodes: dict[str, int]) -> None:
    import pandas as pd
    import altair as alt

    st.markdown('<div class="kg-section-title">Nodes by Type</div>', unsafe_allow_html=True)
    st.markdown(_CARD_OPEN, unsafe_allow_html=True)

    node_colors = {
        "King": "#b71c1c", "Monk": "#1565c0", "Person": "#6a1b9a",
        "Place": "#2e7d32", "Monument": "#e65100", "Dynasty": "#4a148c",
        "Battle": "#880e4f", "Chronicle": "#37474f", "Relic": "#f57f17",
    }
    df = pd.DataFrame(
        {"Type": list(nodes.keys()), "Count": list(nodes.values())}
    ).sort_values("Count", ascending=False)
    df["Color"] = df["Type"].map(lambda x: node_colors.get(x, "#78909c"))

    chart = (
        alt.Chart(df)
        .mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4)
        .encode(
            x=alt.X("Type:N", sort="-y", axis=alt.Axis(labelAngle=-30)),
            y=alt.Y("Count:Q", title="Number of Nodes"),
            color=alt.Color(
                "Type:N",
                scale=alt.Scale(
                    domain=list(node_colors.keys()),
                    range=list(node_colors.values()),
                ),
                legend=None,
            ),
            tooltip=["Type", "Count"],
        )
        .properties(height=280)
        .configure_view(strokeWidth=0)
        .configure_axis(
            gridColor="rgba(255,255,255,0.06)",
            labelColor="rgba(255,255,255,0.55)",
            titleColor="rgba(255,255,255,0.4)",
        )
    )
    st.altair_chart(chart, width="stretch")
    st.markdown(_CARD_CLOSE, unsafe_allow_html=True)


def _render_edges_chart(edges: dict[str, int]) -> None:
    import pandas as pd
    import altair as alt

    st.markdown('<div class="kg-section-title">Relationships by Type</div>', unsafe_allow_html=True)
    st.markdown(_CARD_OPEN, unsafe_allow_html=True)

    df = pd.DataFrame(
        {"Relation": list(edges.keys()), "Count": list(edges.values())}
    ).sort_values("Count", ascending=True)

    chart = (
        alt.Chart(df)
        .mark_bar(cornerRadiusTopRight=4, cornerRadiusBottomRight=4, color="#5c6bc0")
        .encode(
            x=alt.X("Count:Q", title="Number of Relationships"),
            y=alt.Y("Relation:N", sort="-x", title=""),
            tooltip=["Relation", "Count"],
        )
        .properties(height=max(220, len(df) * 28))
        .configure_view(strokeWidth=0)
        .configure_axis(
            gridColor="rgba(255,255,255,0.06)",
            labelColor="rgba(255,255,255,0.55)",
            titleColor="rgba(255,255,255,0.4)",
        )
    )
    st.altair_chart(chart, width="stretch")
    st.markdown(_CARD_CLOSE, unsafe_allow_html=True)


def _render_top_connected(top10: list[dict]) -> None:
    import pandas as pd

    st.markdown('<div class="kg-section-title">Top 10 Most Connected Nodes</div>', unsafe_allow_html=True)
    st.markdown(_CARD_OPEN, unsafe_allow_html=True)

    df = pd.DataFrame(top10).rename(columns={
        "name": "Entity", "label": "Type", "degree": "Connections",
    })
    st.dataframe(df, width="stretch", hide_index=True)
    st.markdown(_CARD_CLOSE, unsafe_allow_html=True)


# ── Page entry point ──────────────────────────────────────────────────────────

def render() -> None:
    st.markdown("""
    <div class="kg-page-title">📊 Statistics</div>
    <div class="kg-page-subtitle">
      Summary metrics, entity distributions, and connectivity analysis of the Knowledge Graph.
    </div>
    """, unsafe_allow_html=True)

    col_refresh, _ = st.columns([1, 4])
    with col_refresh:
        if st.button("Refresh from Neo4j", type="secondary", width="stretch"):
            st.cache_data.clear()
            st.rerun()

    try:
        from kg_store import get_kg_stats, get_top_connected
        stats = get_kg_stats()
        top10 = get_top_connected(n=10)
    except Exception as e:
        st.error(f"Could not reach Neo4j: {e}")
        st.stop()

    if "error" in stats:
        st.warning(f"{stats['error']}")
        st.info("Start Neo4j and set `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD` in your `.env`.")
        st.stop()

    nodes: dict[str, int] = stats.get("nodes", {})
    edges: dict[str, int] = stats.get("edges", {})

    if not nodes and not edges:
        st.info(
            "The Knowledge Graph is empty. "
            "Go to **Extract & Save** and save some sentences first."
        )
        st.stop()

    _render_summary_metrics(nodes, edges)
    st.markdown("<br>", unsafe_allow_html=True)

    col_left, col_right = st.columns(2, gap="large")
    with col_left:
        if nodes:
            _render_nodes_chart(nodes)
    with col_right:
        if edges:
            _render_edges_chart(edges)

    st.markdown("<br>", unsafe_allow_html=True)

    if top10:
        _render_top_connected(top10)
    else:
        st.info("No connectivity data available yet.")

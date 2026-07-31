from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import streamlit as st
from dotenv import load_dotenv
from streamlit_option_menu import option_menu

load_dotenv()

from relation_extractor import (
    _ENV_PROVIDER,
    _ENV_MODEL,
    _env_api_key,
)

# Page config

st.set_page_config(
    page_title="Sinhala Historical KG",
    page_icon="📜",
    layout="wide",
    initial_sidebar_state="expanded",
)

#  Global design system CSS
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+Sinhala:wght@400;600;700&family=Inter:wght@400;500;600;700&display=swap');

/* ── Reset & base ── */
html, body, [class*="css"] {
    font-family: 'Inter', 'Noto Sans Sinhala', 'Segoe UI', sans-serif !important;
}
.stTextArea textarea, .stTextInput input,
.stMarkdown p, .stMarkdown span, .stMarkdown div {
    font-family: 'Noto Sans Sinhala', 'Inter', 'Segoe UI', sans-serif !important;
}
.stTextArea textarea {
    font-size: 1.05em !important;
    line-height: 1.8 !important;
}
mark strong { color: #111 !important; }
mark sup    { font-weight: 700; }

/* ── Sidebar ── */
[data-testid="stSidebar"] {
    background: #111827 !important;
    border-right: 1px solid rgba(255,255,255,0.06) !important;
    padding-top: 0 !important;
}
[data-testid="stSidebar"] > div:first-child {
    padding-top: 0 !important;
}

/* ── Hide Streamlit chrome we don't need ── */
[data-testid="collapsedControl"],
[data-testid="stSidebarCollapseButton"],
[data-testid="stSidebarNav"],
[data-testid="stSidebarNavContainer"],
header[data-testid="stHeader"],
#MainMenu {
    display: none !important;
}

/* ── Main content area ── */
[data-testid="stAppViewContainer"] > section:last-child {
    background: #0e1117 !important;
}

/* ── Remove default Streamlit top padding (header is hidden so reclaim the space) ── */
[data-testid="stMainBlockContainer"] {
    padding-top: 2rem !important;
}

/* ── Streamlit button overrides ── */
.stButton > button {
    border-radius: 10px !important;
    font-weight: 600 !important;
    font-family: 'Inter', sans-serif !important;
    transition: transform 0.1s, box-shadow 0.1s !important;
}
.stButton > button:hover {
    transform: translateY(-1px) !important;
    box-shadow: 0 4px 12px rgba(0,0,0,0.3) !important;
}
.stButton > button[kind="primary"] {
    background: linear-gradient(135deg, #5c6bc0, #3949ab) !important;
    border: none !important;
    color: white !important;
}
.stButton > button[kind="secondary"] {
    border: 1.5px solid #5c6bc0 !important;
    color: #7986cb !important;
    background: rgba(92,107,192,0.1) !important;
}

/* ── Alerts / banners ── */
[data-testid="stSuccess"] {
    background: rgba(67,160,71,0.12) !important;
    border: 1px solid rgba(67,160,71,0.35) !important;
    border-radius: 10px !important;
}
[data-testid="stError"] {
    background: rgba(229,57,53,0.12) !important;
    border: 1px solid rgba(229,57,53,0.35) !important;
    border-radius: 10px !important;
}
[data-testid="stWarning"] {
    background: rgba(251,140,0,0.12) !important;
    border: 1px solid rgba(251,140,0,0.35) !important;
    border-radius: 10px !important;
}
[data-testid="stInfo"] {
    background: rgba(33,150,243,0.10) !important;
    border: 1px solid rgba(33,150,243,0.30) !important;
    border-radius: 10px !important;
}

/* ── Divider ── */
hr { border-color: rgba(255,255,255,0.08) !important; }

/* ── Expander ── */
[data-testid="stExpander"] {
    border: 1px solid rgba(255,255,255,0.08) !important;
    border-radius: 12px !important;
    background: rgba(255,255,255,0.02) !important;
}

/* ── Dataframe ── */
[data-testid="stDataFrame"] {
    border-radius: 10px !important;
    overflow: hidden !important;
}

/* ── Number input ── */
[data-testid="stNumberInput"] input {
    border-radius: 8px !important;
}

/* ── Scrollbar ── */
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.15); border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: rgba(255,255,255,0.25); }

/* ── Utility classes (used in page HTML) ── */
.kg-card {
    background: rgba(255,255,255,0.04);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 14px;
    padding: 20px 24px;
    margin: 10px 0;
    box-shadow: 0 2px 12px rgba(0,0,0,0.2);
}
.kg-section-title {
    font-family: 'Inter', sans-serif !important;
    font-size: 0.72em;
    font-weight: 700;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    color: rgba(255,255,255,0.35);
    margin: 0 0 10px 2px;
}
.kg-page-title {
    font-family: 'Inter', sans-serif !important;
    font-size: 1.7em;
    font-weight: 700;
    color: #f0f2f6;
    margin: 0 0 4px 0;
}
.kg-page-subtitle {
    font-family: 'Inter', sans-serif !important;
    font-size: 0.9em;
    color: rgba(255,255,255,0.4);
    margin-bottom: 20px;
}
.kg-badge {
    display: inline-block;
    padding: 3px 10px;
    border-radius: 20px;
    font-size: 0.75em;
    font-weight: 600;
    letter-spacing: 0.04em;
    font-family: 'Inter', sans-serif !important;
}
.kg-metric-card {
    background: rgba(255,255,255,0.04);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 14px;
    padding: 18px 22px;
    text-align: center;
}
.kg-metric-value {
    font-size: 2.2em;
    font-weight: 700;
    color: #7986cb;
    line-height: 1.1;
    font-family: 'Inter', sans-serif !important;
}
.kg-metric-label {
    font-size: 0.8em;
    color: rgba(255,255,255,0.45);
    font-weight: 500;
    margin-top: 4px;
    font-family: 'Inter', sans-serif !important;
}
</style>
""", unsafe_allow_html=True)

# ── Sidebar: branding + navigation ───────────────────────────────────────────

with st.sidebar:
    # App brand
    st.markdown("""
    <div style="padding:28px 20px 16px 20px;border-bottom:1px solid rgba(255,255,255,0.06);margin-bottom:8px">
      <div style="font-family:'Inter',sans-serif;font-size:1.15em;font-weight:700;
                  color:#fff;letter-spacing:0.02em;display:flex;align-items:center;gap:10px">
        <span style="font-size:1.4em">📜</span>
        <span>Sinhala Historical KG</span>
      </div>
    </div>
    """, unsafe_allow_html=True)

    # Provider badge
    _active_key = _env_api_key(_ENV_PROVIDER)
    if _active_key:
        st.markdown(f"""
        <div style="margin:0 12px 12px 12px;padding:8px 12px;
                    background:rgba(67,160,71,0.15);border:1px solid rgba(67,160,71,0.3);
                    border-radius:8px;font-family:'Inter',sans-serif">
          <div style="font-size:0.65em;font-weight:600;letter-spacing:.06em;
                      text-transform:uppercase;color:rgba(255,255,255,.4)">Active LLM</div>
          <div style="font-size:0.85em;font-weight:600;color:#81c784;margin-top:2px">
            {_ENV_PROVIDER}
          </div>
          <div style="font-size:0.72em;color:rgba(255,255,255,.35);font-family:monospace">
            {_ENV_MODEL}
          </div>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown(f"""
        <div style="margin:0 12px 12px 12px;padding:8px 12px;
                    background:rgba(229,57,53,0.15);border:1px solid rgba(229,57,53,0.3);
                    border-radius:8px;font-family:'Inter',sans-serif">
          <div style="font-size:0.75em;color:#ef9a9a">
            ❌ No API key for <strong>{_ENV_PROVIDER}</strong>
          </div>
        </div>
        """, unsafe_allow_html=True)

    # Navigation menu
    selected = option_menu(
        menu_title=None,
        options=["Extract & Save", "Knowledge Graph", "Statistics", "Essay Checker", "Run History"],
        icons=["search-circle-fill", "diagram-3-fill", "bar-chart-line-fill", "file-earmark-check-fill", "clock-history"],
        default_index=0,
        styles={
            "container": {
                "padding": "4px 8px",
                "background-color": "transparent",
            },
            "icon": {
                "color": "#7986cb",
                "font-size": "16px",
            },
            "nav-link": {
                "font-family": "'Inter', sans-serif",
                "font-size": "14px",
                "font-weight": "500",
                "color": "rgba(255,255,255,0.65)",
                "padding": "10px 14px",
                "border-radius": "10px",
                "margin": "2px 0",
                "--hover-color": "rgba(255,255,255,0.07)",
            },
            "nav-link-selected": {
                "background": "linear-gradient(135deg,rgba(92,107,192,0.35),rgba(57,73,171,0.35))",
                "color": "#ffffff",
                "font-weight": "600",
                "border-left": "3px solid #5c6bc0",
            },
        },
    )

    # Footer
    st.markdown("""
    <div style="position:absolute;bottom:20px;left:0;right:0;padding:0 20px;
                font-family:'Inter',sans-serif;font-size:0.68em;
                color:rgba(255,255,255,.2);text-align:center;line-height:1.6">
      XLM-RoBERTa NER → LLM Extraction<br>→ Neo4j Knowledge Graph
    </div>
    """, unsafe_allow_html=True)

# ── Route to selected page ────────────────────────────────────────────────────

if selected == "Extract & Save":
    from pages.extract import render
    render()
elif selected == "Knowledge Graph":
    from pages.kg_viewer import render
    render()
elif selected == "Statistics":
    from pages.kg_stats import render
    render()
elif selected == "Essay Checker":
    from pages.essay_checker import render
    render()
else:
    from pages.history import render
    render()

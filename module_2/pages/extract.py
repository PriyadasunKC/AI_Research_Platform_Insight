"""pages/extract.py - Extract & Save page."""

from __future__ import annotations

import html as _html
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st
from relation_extractor import _ENV_PROVIDER, _ENV_MODEL, extract_relations

# ── NER label colours ─────────────────────────────────────────────────────────

_COLORS: dict[str, tuple[str, str]] = {
    "PERSON_KING":  ("#ef5350", "#ff8a80"),
    "PERSON_MONK":  ("#42a5f5", "#82b1ff"),
    "PERSON_OTHER": ("#ab47bc", "#ea80fc"),
    "LOCATION":     ("#66bb6a", "#b9f6ca"),
    "MONUMENT":     ("#ffa726", "#ffd180"),
    "DYNASTY":      ("#7e57c2", "#b388ff"),
    "BATTLE_EVENT": ("#ec407a", "#ff80ab"),
    "DATE_ERA":     ("#26a69a", "#a7ffeb"),
    "CHRONICLE":    ("#78909c", "#cfd8dc"),
    "RELIC":        ("#ffca28", "#ffe57f"),
}

_BG: dict[str, str] = {
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

EXAMPLES: list[str] = [
    "දේවානම්පිය රජු ඉශුරුමුණිය ඉදිකළේය.",
    "දුටුගැමුණු රජු රුවන්වැලිසෑය ඉදිකළේය.",
    "දුටුගැමුණු රජු එළාර රජු පරාජය කළේය.",
    "මිහිඳු හිමි ශ්‍රී ලංකාවට පැමිණියේය.",
    "කාශ්‍යප රජු සීගිරිය ඉදිකළේය.",
]

# ── HTML helpers ──────────────────────────────────────────────────────────────

def _mark_entity(ent: str, label: str) -> str:
    fg = _COLORS.get(label, ("#aaa", "#aaa"))[0]
    bg = _BG.get(label, "rgba(150,150,150,0.12)")
    return (
        f'<mark style="background:{bg};border:1.5px solid {fg}33;color:{fg};'
        f'border-radius:6px;padding:2px 10px;margin:0 3px;display:inline-block;'
        f'vertical-align:middle;white-space:nowrap;font-weight:600;'
        f'font-family:\'Noto Sans Sinhala\',sans-serif">'
        f'{_html.escape(ent)}'
        f'<sup style="font-size:.62em;margin-left:5px;opacity:.75;'
        f'font-family:\'Inter\',sans-serif">{label}</sup></mark>'
    )


def _parts_positioned(sentence: str, tags: list) -> list[str]:
    parts: list[str] = []
    cursor = 0
    for tag in sorted(tags, key=lambda t: t.start):
        if tag.start < cursor:
            continue
        if tag.start > cursor:
            parts.append(_html.escape(sentence[cursor:tag.start]))
        parts.append(_mark_entity(sentence[tag.start:tag.end], tag.label))
        cursor = tag.end
    parts.append(_html.escape(sentence[cursor:]))
    return parts


def _parts_fallback(sentence: str, tags: list) -> list[str]:
    parts: list[str] = []
    remaining = sentence
    for tag in tags:
        idx = remaining.find(tag.entity)
        if idx == -1:
            continue
        if idx > 0:
            parts.append(_html.escape(remaining[:idx]))
        parts.append(_mark_entity(tag.entity, tag.label))
        remaining = remaining[idx + len(tag.entity):]
    parts.append(_html.escape(remaining))
    return parts


def _ner_inline_html(sentence: str, tags: list) -> str:
    positioned = [t for t in tags if t.end > t.start]
    parts = _parts_positioned(sentence, positioned) if positioned else _parts_fallback(sentence, tags)
    return (
        '<div style="font-size:1.1em;line-height:3.2;padding:18px 22px;'
        'background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.07);'
        'border-radius:12px;word-break:break-word;font-family:\'Noto Sans Sinhala\',sans-serif">'
        + "".join(parts) + "</div>"
    )


def _entity_pill(entity: str, label: str) -> str:
    fg = _COLORS.get(label, ("#aaa", "#aaa"))[0]
    bg = _BG.get(label, "rgba(150,150,150,0.12)")
    return (
        f'<div style="background:{bg};border:1px solid {fg}44;'
        f'border-radius:10px;padding:10px 14px;margin:4px 0;">'
        f'<div style="font-family:\'Noto Sans Sinhala\',sans-serif;'
        f'color:#f0f2f6;font-weight:600;font-size:.95em;word-break:break-all">'
        f'{_html.escape(entity)}</div>'
        f'<div style="font-family:\'Inter\',sans-serif;color:{fg};'
        f'font-size:.68em;font-weight:700;letter-spacing:.06em;'
        f'text-transform:uppercase;margin-top:3px">{label}</div>'
        f'</div>'
    )


def _triple_card(triple: dict) -> str:
    subj   = _html.escape(triple.get("subject",  ""))
    rel    = _html.escape(triple.get("relation", ""))
    obj    = _html.escape(triple.get("object",   ""))
    period = triple.get("period", "")
    period_html = (
        f'<div style="margin-top:12px;padding-top:10px;'
        f'border-top:1px solid rgba(255,255,255,0.07);'
        f'font-family:\'Inter\',sans-serif;font-size:.82em;'
        f'color:rgba(255,255,255,.45)">🕐 {_html.escape(period)}</div>'
    ) if period else ""
    return (
        f'<div style="background:rgba(255,255,255,0.04);'
        f'border:1px solid rgba(92,107,192,0.25);border-radius:14px;'
        f'padding:18px 22px;margin:10px 0;box-shadow:0 2px 12px rgba(0,0,0,0.2)">'
        f'<div style="display:flex;align-items:center;gap:12px;flex-wrap:wrap">'
        f'<span style="background:rgba(33,150,243,0.15);border:1px solid rgba(33,150,243,0.3);'
        f'color:#90caf9;border-radius:8px;padding:7px 16px;font-weight:600;'
        f'font-family:\'Noto Sans Sinhala\',sans-serif;font-size:.95em">{subj}</span>'
        f'<span style="color:#7986cb;font-family:\'Inter\',sans-serif;'
        f'font-weight:700;font-size:.85em;letter-spacing:.04em;white-space:nowrap;'
        f'padding:0 4px">── {rel} ──▶</span>'
        f'<span style="background:rgba(102,187,106,0.15);border:1px solid rgba(102,187,106,0.3);'
        f'color:#a5d6a7;border-radius:8px;padding:7px 16px;font-weight:600;'
        f'font-family:\'Noto Sans Sinhala\',sans-serif;font-size:.95em">{obj}</span>'
        f'</div>{period_html}</div>'
    )


def _json_block(data: object) -> str:
    raw = data if isinstance(data, str) else json.dumps(data, ensure_ascii=False, indent=2)
    lines = []
    for line in raw.split("\n"):
        n = len(line) - len(line.lstrip(" "))
        lines.append("&nbsp;" * n + _html.escape(line.lstrip(" ")))
    body = "<br>".join(lines)
    return (
        f'<div style="font-family:\'Fira Code\',monospace;font-size:.82em;'
        f'line-height:1.8;background:rgba(0,0,0,0.3);padding:16px 20px;'
        f'border-radius:10px;color:#b0bec5;border:1px solid rgba(255,255,255,0.06);'
        f'overflow-x:auto;word-break:break-word">{body}</div>'
    )


@st.cache_resource(show_spinner="⏳ Loading NER model…")
def _load_ner_once():
    from ner_pipeline import _load_pipeline
    _load_pipeline()


# ── Section renderers ─────────────────────────────────────────────────────────

def _render_input_section() -> tuple[str, bool]:
    """Renders Step 1 input area. Returns (sentence, tag_btn_pressed).
    Calls st.stop() when sentence is empty."""
    st.markdown('<div class="kg-section-title">Step 1 - Input</div>', unsafe_allow_html=True)

    col_in, col_ex = st.columns([3, 1], gap="medium")

    with col_ex:
        st.markdown(
            '<div style="font-family:\'Inter\',sans-serif;font-size:.8em;font-weight:600;'
            'color:rgba(255,255,255,.4);letter-spacing:.05em;text-transform:uppercase;'
            'margin-bottom:8px">Examples</div>',
            unsafe_allow_html=True,
        )
        for i, ex in enumerate(EXAMPLES):
            label = ex if len(ex) <= 28 else ex[:26] + "…"
            if st.button(label, key=f"ex_{i}", width="stretch", help=ex):
                st.session_state.sentence_input = ex
                st.session_state.ner_tags       = None
                st.session_state.triples        = None
                st.session_state.kg_saved       = False
                st.rerun()

    with col_in:
        sentence: str = st.text_area(
            "Sinhala historical sentence",
            key="sentence_input",
            height=110,
            placeholder="e.g. දේවානම්පිය රජු ඉශුරුමුණිය ඉදිකළේය.",
            label_visibility="collapsed",
        )
        tag_btn = st.button(
            "① Extract Named Entities",
            type="primary",
            disabled=not sentence.strip(),
            width="content",
        )

    current = sentence.strip()
    if not current:
        st.markdown(
            '<div style="text-align:center;padding:40px;color:rgba(255,255,255,.25);'
            'font-family:\'Inter\',sans-serif;font-size:.9em">'
            'Enter a sentence above or pick an example →</div>',
            unsafe_allow_html=True,
        )
        st.stop()

    return current, tag_btn


def _run_ner_if_needed(sentence: str, tag_btn: bool) -> list | None:
    """Resets state if sentence changed; runs NER if button was pressed."""
    if sentence != st.session_state["ner_sentence"]:
        st.session_state.ner_tags     = None
        st.session_state.triples      = None
        st.session_state.kg_saved     = False
        st.session_state.mongo_run_id = None

    if tag_btn:
        with st.spinner("Running NER model…"):
            from ner_pipeline import run_ner
            st.session_state.ner_tags     = run_ner(sentence)
            st.session_state.ner_sentence = sentence
            st.session_state.triples      = None
            st.session_state.kg_saved     = False

    return st.session_state["ner_tags"]


def _render_ner_section(sentence: str, ner_tags: list) -> None:
    """Renders Step 2 NER results. Calls st.stop() when entities are insufficient."""
    st.divider()
    st.markdown('<div class="kg-section-title">Step 2 - Named Entities</div>', unsafe_allow_html=True)

    if not ner_tags:
        st.warning("No named entities detected. Try a different sentence.")
        st.stop()

    st.markdown(_ner_inline_html(sentence, ner_tags), unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)

    pill_cols = st.columns(min(len(ner_tags), 5))
    for i, tag in enumerate(ner_tags):
        pill_cols[i % 5].markdown(_entity_pill(tag.entity, tag.label), unsafe_allow_html=True)

    with st.expander("Entity type legend", expanded=False):
        leg_cols = st.columns(5)
        for j, (lbl, (fg, _)) in enumerate(_COLORS.items()):
            bg = _BG.get(lbl, "rgba(150,150,150,.1)")
            leg_cols[j % 5].markdown(
                f'<div style="background:{bg};border:1px solid {fg}55;'
                f'border-radius:7px;padding:6px 10px;margin:3px 0;'
                f'font-family:\'Inter\',sans-serif;font-size:.75em;'
                f'font-weight:600;color:{fg}">{lbl}</div>',
                unsafe_allow_html=True,
            )

    non_date = [t for t in ner_tags if t.label != "DATE_ERA"]
    if len(non_date) < 2:
        st.info("At least 2 non-DATE_ERA entities are needed to form a triple.")
        st.stop()


def _render_extraction_section(sentence: str, ner_tags: list) -> None:
    """Renders Step 3 relation extraction button and calls the LLM if pressed."""
    st.divider()
    st.markdown('<div class="kg-section-title">Step 3 - Relation Extraction</div>', unsafe_allow_html=True)

    st.markdown(
        f'<div style="font-family:\'Inter\',sans-serif;font-size:.85em;'
        f'color:rgba(255,255,255,.45);margin-bottom:10px">'
        f'Provider: <strong style="color:#7986cb">{_ENV_PROVIDER}</strong>'
        f' &nbsp;·&nbsp; Model: <code style="color:#80cbc4">{_ENV_MODEL}</code></div>',
        unsafe_allow_html=True,
    )

    rel_btn = st.button("② Extract Relations  -  calls LLM API", type="primary")
    if not rel_btn:
        return

    _dbg: dict = {}
    with st.spinner(f"Calling {_ENV_PROVIDER} ({_ENV_MODEL})…"):
        try:
            result = extract_relations(sentence, ner_tags, _debug=_dbg)
            st.session_state.triples      = result
            st.session_state["_debug"]    = _dbg
            st.session_state.kg_saved     = False
            st.session_state.mongo_run_id = None
            # Reset per-triple checkboxes for the new result
            keys_to_delete = [k for k in st.session_state if k.startswith("triple_check_")]
            for key in keys_to_delete:
                del st.session_state[key]
        except ImportError as e:
            st.error(f"Missing package: {e}")
            st.stop()
        except Exception as e:
            st.error(f"API error: {e}")
            st.stop()

    # Persist run to MongoDB (non-blocking - failure is logged, not surfaced)
    try:
        from mongo_store import save_run
        run_id = save_run(
            sentence=sentence,
            ner_tags=ner_tags,
            llm_provider=_ENV_PROVIDER,
            llm_model=_ENV_MODEL,
            llm_raw=_dbg.get("raw", ""),
            llm_parsed=_dbg.get("parsed", []),
            validated_triples=st.session_state.triples or [],
        )
        st.session_state.mongo_run_id = run_id
    except Exception:
        pass


def _do_save_to_kg(sentence: str, ner_tags: list, selected_triples: list) -> None:
    """Executes the KG save and updates session state. Called on button click."""
    from kg_store import save_pipeline_result
    counts = save_pipeline_result(sentence, ner_tags, selected_triples)
    st.session_state.kg_saved = True
    run_id = st.session_state.get("mongo_run_id")
    if run_id:
        try:
            from mongo_store import mark_kg_saved
            mark_kg_saved(run_id)
        except Exception:
            pass
    st.success(
        f"Saved - **{counts['nodes_processed']}** nodes · "
        f"**{counts['edges_created']}** new edges"
    )
    st.rerun()


def _render_save_button(sentence: str, ner_tags: list, selected_triples: list) -> None:
    """Renders the Save to KG button using only the caller-selected triples."""
    if st.session_state.get("kg_saved"):
        st.markdown(
            '<div style="padding:10px 14px;background:rgba(67,160,71,0.12);'
            'border:1px solid rgba(67,160,71,0.3);border-radius:10px;'
            'font-family:\'Inter\',sans-serif;font-size:.85em;color:#81c784">'
            '✅ Saved to Knowledge Graph</div>',
            unsafe_allow_html=True,
        )
        return

    n = len(selected_triples)
    if n:
        plural = "s" if n != 1 else ""
        label = f"💾 Save {n} triple{plural} to KG"
    else:
        label = "💾 Nothing selected"
    if st.button(label, type="secondary", width="stretch", disabled=(n == 0)):
        try:
            _do_save_to_kg(sentence, ner_tags, selected_triples)
        except Exception as e:
            st.error(f"KG save failed: {e}")


def _render_llm_debug(debug: dict) -> None:
    """Shows collapsible LLM input and output panels when debug data is available."""
    if not debug:
        return
    col_in, col_out = st.columns(2)
    with col_in:
        with st.expander("📨 LLM Input", expanded=False):
            st.markdown(
                f'<pre style="font-size:.8em;white-space:pre-wrap;word-break:break-word;">'
                f'{_html.escape(debug.get("input", ""))}</pre>',
                unsafe_allow_html=True,
            )
    with col_out:
        with st.expander("📩 LLM Output (raw)", expanded=False):
            st.markdown(_json_block(debug.get("raw", "")), unsafe_allow_html=True)
            if debug.get("parsed"):
                st.markdown("**Parsed (pre-validation):**")
                st.markdown(_json_block(debug.get("parsed", [])), unsafe_allow_html=True)


def _render_results_section(sentence: str, ner_tags: list, triples: list, debug: dict) -> None:
    """Renders Step 4 validated triples, save button, and raw JSON toggle."""
    st.divider()
    st.markdown('<div class="kg-section-title">Step 4 - Validated Triples</div>', unsafe_allow_html=True)

    if not triples:
        st.info(
            "No valid triples extracted. The sentence may not express a historical "
            "relation between two named entities, or neither entity appeared in the NER output."
        )
        _render_llm_debug(debug)
        return

    count = len(triples)
    st.success(
        f"**{count}** valid triple{'s' if count > 1 else ''} extracted "
        f"via {_ENV_PROVIDER} / `{_ENV_MODEL}`"
    )

    # ── Per-triple checkboxes ─────────────────────────────────────────────────
    st.markdown(
        '<div style="font-family:\'Inter\',sans-serif;font-size:.8em;'
        'color:rgba(255,255,255,.45);margin-bottom:6px">'
        'Check the relations you want to save - uncheck wrong ones before saving.</div>',
        unsafe_allow_html=True,
    )

    # Select-all / deselect-all controls
    ca_col, da_col, _ = st.columns([1, 1, 5])
    with ca_col:
        if st.button("✅ All", key="triple_select_all", width="stretch"):
            for i in range(len(triples)):
                st.session_state[f"triple_check_{i}"] = True
            st.rerun()
    with da_col:
        if st.button("☐ None", key="triple_deselect_all", width="stretch"):
            for i in range(len(triples)):
                st.session_state[f"triple_check_{i}"] = False
            st.rerun()

    selected_triples = []
    for i, triple in enumerate(triples):
        key = f"triple_check_{i}"
        if key not in st.session_state:
            st.session_state[key] = True          # default: selected
        chk_col, card_col = st.columns([1, 12])
        with chk_col:
            st.markdown("<br>", unsafe_allow_html=True)
            checked = st.checkbox("Include", key=key, label_visibility="collapsed")
        with card_col:
            st.markdown(_triple_card(triple), unsafe_allow_html=True)
        if checked:
            selected_triples.append(triple)

    st.markdown("<br>", unsafe_allow_html=True)

    col_save, col_json, _ = st.columns([2, 2, 3])
    with col_save:
        _render_save_button(sentence, ner_tags, selected_triples)
    with col_json:
        if st.button("{ } Raw JSON", width="stretch"):
            st.session_state.show_json = not st.session_state["show_json"]

    if st.session_state["show_json"]:
        st.markdown(_json_block(triples), unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    _render_llm_debug(debug)


# ── Page entry point ──────────────────────────────────────────────────────────

def render() -> None:
    _load_ner_once()

    st.markdown("""
    <div class="kg-page-title">🔍 Extract & Save</div>
    <div class="kg-page-subtitle">
      Run the NER → LLM → Validation pipeline on a Sinhala historical sentence,
      then persist the result to the Knowledge Graph.
    </div>
    """, unsafe_allow_html=True)

    for k, v in [
        ("sentence_input", ""),
        ("ner_sentence",   ""),
        ("ner_tags",       None),
        ("triples",        None),
        ("show_json",      False),
        ("show_debug",     False),
        ("kg_saved",       False),
        ("mongo_run_id",   None),
    ]:
        if k not in st.session_state:
            st.session_state[k] = v

    current, tag_btn = _render_input_section()

    ner_tags = _run_ner_if_needed(current, tag_btn)
    if ner_tags is None:
        st.stop()

    _render_ner_section(current, ner_tags)
    _render_extraction_section(current, ner_tags)

    triples = st.session_state.get("triples")
    if triples is None:
        st.stop()

    _render_results_section(current, ner_tags, triples, st.session_state.get("_debug", {}))

    st.markdown("<br><br>", unsafe_allow_html=True)
    st.markdown(
        '<div style="text-align:center;font-family:\'Inter\',sans-serif;'
        'font-size:.72em;color:rgba(255,255,255,.18);letter-spacing:.04em">'
        'XLM-RoBERTa NER → LLM Relation Extraction → Ontology Validator</div>',
        unsafe_allow_html=True,
    )

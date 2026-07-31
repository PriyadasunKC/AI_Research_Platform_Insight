"""pages/kg_viewer.py — Interactive Knowledge Graph visualization page."""

from __future__ import annotations

import sys
import tempfile
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st
import streamlit.components.v1 as components

#  Constants 

_NODE_COLORS: dict[str, str] = {
    "King":      "#b71c1c",
    "Monk":      "#1565c0",
    "Person":    "#6a1b9a",
    "Place":     "#2e7d32",
    "Monument":  "#e65100",
    "Dynasty":   "#4a148c",
    "Battle":    "#880e4f",
    "Chronicle": "#37474f",
    "Relic":     "#f57f17",
    "Era":        "#00838f",
    "Technology": "#0277bd",
    "Animal":     "#558b2f",
}

_ALL_NODE_TYPES = list(_NODE_COLORS.keys())
_EDGE_COLOR     = "#5c6bc0"
_MAX_NODES      = 1000  # graph display cap — largest component shown when exceeded
_MAX_TRIPLES    = 5000  # Neo4j fetch limit for table / edit / delete
_CARD_OPEN      = '<div class="kg-card">'
_CARD_CLOSE     = '</div>'

_ALL_LABELS          = list(_NODE_COLORS.keys())
_NEW_ENTITY_SENTINEL = "── Create new entity ──"
_CUSTOM_REL_SENTINEL = "── Custom relation type ──"
_ERR_REL_REQUIRED    = "Relation type is required."
_MANUAL_SOURCE_TAG   = "[manual]"

# JavaScript injected into the PyVis HTML so node clicks are sent back to Streamlit
_STREAMLIT_GRAPH_JS = """
<script>
(function () {
  function post(type, data) {
    window.parent.postMessage(
      Object.assign({ isStreamlitMessage: true, type: type }, data), "*"
    );
  }
  window.addEventListener("load", function () {
    post("streamlit:componentReady", { apiVersion: 1 });
    post("streamlit:setFrameHeight", { height: 640 });
    var tries = 0;
    var poll = setInterval(function () {
      if (typeof network !== "undefined") {
        clearInterval(poll);

        function killPhysics() {
          network.setOptions({ physics: { enabled: false } });
          network.stopSimulation();
        }

        network.once("stabilizationIterationsDone", function () {
          killPhysics();
          network.fit();
        });
        network.on("stabilizationProgress", function (p) {
          if (p.iterations >= p.total) { killPhysics(); }
        });

        // Hard fallback: force physics off at 3 s and 6 s regardless of events
        setTimeout(function () { killPhysics(); }, 3000);
        setTimeout(function () { killPhysics(); network.fit(); }, 6000);

        network.on("click", function (p) {
          var val = (p.nodes && p.nodes.length > 0) ? p.nodes[0] : "__CLEAR__";
          post("streamlit:setComponentValue", { value: val });
        });
      }
      if (++tries > 60) clearInterval(poll);
    }, 100);
  });
})();
</script>
"""


#  Graph builder helpers 

def _filter_triples(
    triples: list[dict],
    selected_node_types: list[str],
    selected_relations: list[str],
) -> list[dict]:
    return [
        t for t in triples
        if (t.get("subject_label") in selected_node_types or t.get("subject_label") is None)
        and (t.get("object_label") in selected_node_types or t.get("object_label") is None)
        and t.get("relation") in selected_relations
    ]


def _build_nx_graph(filtered: list[dict], search_term: str):
    import networkx as nx

    # MultiDiGraph allows multiple edges between the same pair of nodes
    # (e.g. KILLED and DEFEATED both from X to Y).
    graph = nx.MultiDiGraph()
    for t in filtered:
        subj = t["subject"]
        obj  = t["object"]
        if subj:
            graph.add_node(subj, label=t.get("subject_label") or "Person")
        if obj:
            graph.add_node(obj,  label=t.get("object_label")  or "Person")
        if subj and obj:
            graph.add_edge(subj, obj, relation=t["relation"])

    oversized = graph.number_of_nodes() > _MAX_NODES
    if oversized:
        wcc = list(nx.weakly_connected_components(graph))
        if wcc:
            graph = graph.subgraph(max(wcc, key=len)).copy()

    highlight_set: set[str] = set()
    if search_term:
        import unicodedata as _ud
        def _ks(s: str) -> str:
            return _ud.normalize("NFC", s).replace("‍", "").replace("‌", "").lower()
        _needle = _ks(search_term)
        matched = {n for n in graph.nodes if _needle in _ks(n)}
        if matched:
            # Keep matched nodes + every immediate neighbour (in both directions)
            keep: set[str] = set(matched)
            for n in matched:
                keep.update(graph.predecessors(n))
                keep.update(graph.successors(n))
            graph = graph.subgraph(keep).copy()
            highlight_set = matched

    return graph, highlight_set, oversized


def _populate_pyvis_net(net, graph, highlight_set: set[str]) -> None:
    degree_map: dict[str, int] = dict(graph.degree())
    for node_name, data in graph.nodes(data=True):
        lbl    = data.get("label") or "Person"
        color  = _NODE_COLORS.get(lbl, "#78909c")
        degree = degree_map.get(node_name, 1)
        size   = max(12, min(40, 12 + degree * 4))
        border = "#ff6f00" if node_name in highlight_set else color
        net.add_node(
            node_name,
            label=node_name,
            color={"background": color, "border": border,
                   "highlight": {"background": color, "border": "#ff6f00"}},
            size=size,
            title=f"{lbl}: {node_name}  (degree: {degree})",
            borderWidth=3 if node_name in highlight_set else 1,
        )
    for u, v, _key, data in graph.edges(data=True, keys=True):
        rel = data.get("relation", "")
        net.add_edge(u, v, label=rel, title=rel, color=_EDGE_COLOR)


def _net_to_html(net) -> str:
    with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as tmp:
        tmp_path = tmp.name
    try:
        net.save_graph(tmp_path)
        with open(tmp_path, "r", encoding="utf-8") as f:
            return f.read()
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


def _build_pyvis_html(
    triples: list[dict],
    selected_node_types: list[str],
    selected_relations: list[str],
    search_term: str,
) -> tuple[str, list[dict], bool]:
    from pyvis.network import Network

    filtered = _filter_triples(triples, selected_node_types, selected_relations)
    graph, highlight_set, oversized = _build_nx_graph(filtered, search_term)

    net = Network(
        height="680px", width="100%",
        bgcolor="#fafafa", font_color="#333333", directed=True,
    )
    net.set_options("""{
      "nodes": {
        "shape": "dot",
        "scaling": {"min": 12, "max": 40},
        "font": {"size": 14, "face": "Noto Sans Sinhala, Segoe UI, sans-serif"}
      },
      "edges": {
        "arrows": {"to": {"enabled": true, "scaleFactor": 0.6}},
        "color": {"color": "#5c6bc0"},
        "font": {"size": 11, "color": "#5c6bc0", "strokeWidth": 0},
        "smooth": {"type": "dynamic", "roundness": 0.3}
      },
      "interaction": {
        "hover": true, "tooltipDelay": 150,
        "navigationButtons": true, "keyboard": true
      },
      "physics": {
        "stabilization": {"enabled": true, "iterations": 250, "fit": true},
        "barnesHut": {
          "gravitationalConstant": -30000,
          "centralGravity": 0.0,
          "springLength": 280,
          "springConstant": 0.02,
          "damping": 0.2,
          "avoidOverlap": 1
        }
      }
    }""")

    _populate_pyvis_net(net, graph, highlight_set)
    return _net_to_html(net), filtered, oversized


#  Sub-section renderers

def _render_filters(all_relations: list[str]) -> tuple[list[str], list[str], str]:
    """Renders filter card. Returns (selected_types, selected_rels, search_term)."""

    # Auto-include any relation types that were added since the filter was last set.
    # This prevents newly saved manual triples from being silently excluded.
    stored_rels = st.session_state.get("kg_rel_filter")
    if stored_rels is not None:
        new_rels = [r for r in all_relations if r not in stored_rels]
        if new_rels:
            st.session_state["kg_rel_filter"] = list(stored_rels) + new_rels

    st.markdown('<div class="kg-section-title">Filters</div>', unsafe_allow_html=True)
    st.markdown(_CARD_OPEN, unsafe_allow_html=True)

    col1, col2, col3 = st.columns([2, 2, 1])
    with col1:
        selected_types = st.multiselect(
            "Node types", options=_ALL_NODE_TYPES, default=_ALL_NODE_TYPES,
            key="kg_type_filter",
        )
    with col2:
        selected_rels = st.multiselect(
            "Relation types", options=all_relations, default=all_relations,
            key="kg_rel_filter",
        )
    with col3:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("Reset", width="stretch", help="Reset all filters"):
            st.session_state["kg_type_filter"] = _ALL_NODE_TYPES
            st.session_state["kg_rel_filter"]  = all_relations
            st.session_state["kg_search"]      = ""
            st.session_state.pop("kg_focused_node", None)
            st.rerun()

    search_term: str = st.text_input(
        "Highlight node by name (partial match)",
        key="kg_search",
        placeholder="e.g. දුටුගැමුණු",
    )
    st.markdown(_CARD_CLOSE, unsafe_allow_html=True)
    return selected_types, selected_rels, search_term


def _render_node_legend() -> None:
    cols = st.columns(len(_NODE_COLORS))
    for i, (lbl, color) in enumerate(_NODE_COLORS.items()):
        cols[i].markdown(
            f'<div style="background:{color}22;border:1px solid {color}66;'
            f'border-radius:6px;padding:5px 8px;text-align:center;'
            f'font-family:\'Inter\',sans-serif;font-size:.7em;'
            f'font-weight:600;color:{color}">{lbl}</div>',
            unsafe_allow_html=True,
        )


def _collect_hit_names(search_term: str, triples: list[dict]) -> list[str]:
    seen: set[str] = set()
    hit_names: list[str] = []
    term = search_term.lower()
    for t in triples:
        for field in ("subject", "object"):
            n = t.get(field, "")
            if n and term in n.lower() and n not in seen:
                hit_names.append(n)
                seen.add(n)
    return hit_names


def _render_detail_panel(detail: dict) -> None:
    c1, c2 = st.columns(2)
    with c1:
        st.markdown(f"**Name:** {detail['name']}")
        st.markdown(f"**Type:** {detail['label']}")
        aliases = detail.get("aliases") or []
        if aliases:
            st.markdown(f"**Aliases:** {', '.join(aliases)}")
    with c2:
        out = detail.get("outgoing") or []
        inc = detail.get("incoming") or []
        if out:
            st.markdown("**Outgoing relations:**")
            for e in out:
                st.markdown(
                    f"&nbsp;&nbsp;→ `{e['relation']}` → **{e['target']}**",
                    unsafe_allow_html=True,
                )
        if inc:
            st.markdown("**Incoming relations:**")
            for e in inc:
                st.markdown(
                    f"&nbsp;&nbsp;**{e['source']}** → `{e['relation']}` →",
                    unsafe_allow_html=True,
                )


def _render_node_detail(search_term: str, triples: list[dict]) -> None:
    hit_names = _collect_hit_names(search_term, triples)
    if not hit_names:
        return

    st.markdown('<div class="kg-section-title">Node Detail</div>', unsafe_allow_html=True)
    st.markdown(_CARD_OPEN, unsafe_allow_html=True)

    selected_node = st.selectbox(
        "Select node to inspect", options=hit_names, key="kg_detail_node",
    )
    try:
        from kg_store import get_node_detail
        detail = get_node_detail(selected_node)
    except Exception:
        detail = None

    if detail:
        _render_detail_panel(detail)
    else:
        st.info("Node details not found in KG.")

    st.markdown(_CARD_CLOSE, unsafe_allow_html=True)


def _render_delete_section(df) -> None:
    st.markdown('<div class="kg-section-title">Delete a Relation</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="kg-card" style="border-left: 4px solid #c62828;">',
        unsafe_allow_html=True,
    )

    if df.empty:
        st.info("No relations visible with current filters.")
        st.markdown(_CARD_CLOSE, unsafe_allow_html=True)
        return

    options = [
        f"{row['Subject']}  ──{row['Relation']}──▶  {row['Object']}"
        for _, row in df.iterrows()
    ]

    col_sel, col_btn = st.columns([4, 1])
    with col_sel:
        selected = st.selectbox(
            "Select relation to remove", options=options, key="kg_delete_select",
            label_visibility="collapsed",
        )
    with col_btn:
        if st.button("🗑️ Delete", type="primary", key="kg_delete_btn", width="stretch"):
            idx = options.index(selected)
            row = df.iloc[idx]
            try:
                from kg_store import delete_relation
                removed = delete_relation(row["Subject"], row["Relation"], row["Object"])
                if removed:
                    _bump_graph_version()
                    st.session_state["_kg_save_msg"] = f"Deleted: {selected}"
                    st.rerun()
                else:
                    st.warning("Relation not found in Neo4j — may have already been deleted.")
            except Exception as exc:
                st.error(f"Delete failed: {exc}")

    st.markdown(_CARD_CLOSE, unsafe_allow_html=True)


def _render_relation_table(filtered_triples: list[dict]) -> None:
    import pandas as pd

    st.markdown('<div class="kg-section-title">Relation Browser</div>', unsafe_allow_html=True)
    st.markdown(_CARD_OPEN, unsafe_allow_html=True)

    df = pd.DataFrame([
        {
            "Subject":  t.get("subject",  ""),
            "Relation": t.get("relation", ""),
            "Object":   t.get("object",   ""),
            "Period":   t.get("period",   "") or "",
            "Source":   (t.get("source",  "") or "")[:60],
        }
        for t in filtered_triples
    ])

    subj_filter = st.text_input(
        "Filter by subject name", key="kg_table_filter",
        placeholder="e.g. දේවානම්පිය",
    )
    if subj_filter:
        import unicodedata as _ud

        def _ks(s: str) -> str:
            # NFC-normalise + strip ZWJ/ZWNJ so pipeline names match keyboard input
            return _ud.normalize("NFC", str(s)).replace("‍", "").replace("‌", "").lower()

        _needle = _ks(subj_filter)
        df = df[df["Subject"].apply(lambda s: _needle in _ks(s))]

    df = df.sort_values("Relation").reset_index(drop=True)

    page_size = 20
    total   = len(df)
    n_pages = max(1, (total + page_size - 1) // page_size)
    page    = st.number_input(
        f"Page (total {total} rows, {n_pages} pages)",
        min_value=1, max_value=n_pages, value=1, step=1, key="kg_table_page",
    )
    start = (page - 1) * page_size
    st.dataframe(df.iloc[start:start + page_size], width="stretch")

    st.markdown("<br>", unsafe_allow_html=True)
    _render_delete_section(df)

    st.markdown(_CARD_CLOSE, unsafe_allow_html=True)


#  Edit existing data

def _reset_edit_form_if_changed(
    selected_label: str,
    triple: dict,
    all_nodes: list[dict],
    all_relations: list[str],
) -> None:
    if st.session_state.get("_kg_edit_rel_prev") == selected_label:
        return
    st.session_state["_kg_edit_rel_prev"] = selected_label

    # Pre-seed dropdowns directly so no extra rerun is needed
    node_names = [n["name"] for n in all_nodes]
    subj = triple["subject"]
    obj  = triple["object"]
    rel  = triple.get("relation", "")

    if subj in node_names:
        st.session_state["kg_edit_subj_sel"] = subj
    else:
        st.session_state.pop("kg_edit_subj_sel", None)

    if obj in node_names:
        st.session_state["kg_edit_obj_sel"] = obj
    else:
        st.session_state.pop("kg_edit_obj_sel", None)

    if rel in all_relations:
        st.session_state["kg_edit_rel_type"] = rel
    else:
        st.session_state.pop("kg_edit_rel_type", None)

    for k in (
        "kg_edit_subj_new_name", "kg_edit_subj_new_label",
        "kg_edit_rel_custom",
        "kg_edit_obj_new_name",  "kg_edit_obj_new_label",
        "kg_edit_period",        "kg_edit_source",
    ):
        st.session_state.pop(k, None)


def _entity_selector(
    all_nodes: list[dict],
    key_prefix: str,
    cur_name: str,
    field_label: str,
) -> tuple[str, str, bool]:
    """Dropdown for existing node or new entity. Returns (name, label, is_new)."""
    node_names     = [n["name"] for n in all_nodes]
    node_label_map = {n["name"]: n["label"] for n in all_nodes}
    options        = node_names + [_NEW_ENTITY_SENTINEL]
    default_idx    = node_names.index(cur_name) if cur_name in node_names else 0

    selected = st.selectbox(
        field_label, options=options,
        index=default_idx, key=f"{key_prefix}_sel",
    )
    if selected != _NEW_ENTITY_SENTINEL:
        return selected, node_label_map.get(selected, "Person"), False

    new_name = st.text_input(
        f"New {field_label.lower()} name", key=f"{key_prefix}_new_name",
        placeholder="Enter name...",
    ).strip()
    new_label = st.selectbox(
        f"{field_label} type", options=_ALL_LABELS,
        key=f"{key_prefix}_new_label",
    )
    return new_name, new_label, True


def _bump_graph_version() -> None:
    """Increment graph version so the iframe always reloads after data changes.

    Also clears cached filter state so newly added relation/node types are
    included in the filter defaults on the next render.
    """
    st.session_state["_kg_graph_ver"] = st.session_state.get("_kg_graph_ver", 0) + 1
    st.session_state.pop("kg_focused_node", None)
    st.session_state.pop("kg_rel_filter", None)
    st.session_state.pop("kg_type_filter", None)


def _do_edit_triple(
    triple: dict,
    new_subj: str, new_subj_label: str, subj_is_new: bool,
    new_rel: str,
    new_obj: str, new_obj_label: str, obj_is_new: bool,
    new_period: str,
    new_note: str,
) -> None:
    if not new_rel:
        st.session_state["_kg_edit_msg"] = {"type": "error", "text": _ERR_REL_REQUIRED}
        st.rerun()
        return
    if not new_subj:
        st.session_state["_kg_edit_msg"] = {"type": "error", "text": "Subject name is required."}
        st.rerun()
        return
    if not new_obj:
        st.session_state["_kg_edit_msg"] = {"type": "error", "text": "Object name is required."}
        st.rerun()
        return

    old_source = (triple.get("source", "") or "").removeprefix("[manual] ")
    new_source = f"{_MANUAL_SOURCE_TAG} {new_note}".strip() if new_note.strip() else _MANUAL_SOURCE_TAG

    if (
        new_subj == triple["subject"] and new_rel == triple["relation"]
        and new_obj == triple["object"]
        and new_period == (triple.get("period", "") or "")
        and new_note == old_source
    ):
        st.session_state["_kg_edit_msg"] = {"type": "warning", "text": "No changes detected."}
        st.rerun()
        return

    try:
        from kg_store import delete_triple, upsert_entity, upsert_relation, normalize_name
        import kg_aliases

        if subj_is_new:
            new_subj = normalize_name(new_subj)
            upsert_entity(new_subj, new_subj_label, kg_aliases.get_aliases_for(new_subj))
        if obj_is_new:
            new_obj = normalize_name(new_obj)
            upsert_entity(new_obj, new_obj_label, kg_aliases.get_aliases_for(new_obj))

        delete_triple(triple["subject"], triple["relation"], triple["object"])
        upsert_relation(new_subj, new_rel, new_obj, new_period, new_source)

        # Clear edit form state so user cannot accidentally re-save
        for k in ("kg_edit_subj_sel", "kg_edit_subj_new_name", "kg_edit_subj_new_label",
                  "kg_edit_rel_type", "kg_edit_rel_custom",
                  "kg_edit_obj_sel",  "kg_edit_obj_new_name",  "kg_edit_obj_new_label",
                  "kg_edit_period",   "kg_edit_source",        "_kg_edit_rel_prev"):
            st.session_state.pop(k, None)
        _bump_graph_version()
        st.session_state["_kg_edit_msg"] = {
            "type": "success",
            "text": f"Saved: **{new_subj}** ──{new_rel}──▶ **{new_obj}**",
        }
        st.rerun()
    except Exception as exc:
        st.session_state["_kg_edit_msg"] = {"type": "error", "text": f"Save failed: {exc}"}
        st.rerun()


def _relation_type_input(rel_options: list[str], cur_rel: str) -> str:
    rel_default_idx = rel_options.index(cur_rel) if cur_rel in rel_options else 0
    rel_sel = st.selectbox(
        "Relation type", options=rel_options,
        index=rel_default_idx, key="kg_edit_rel_type",
    )
    if rel_sel != _CUSTOM_REL_SENTINEL:
        return rel_sel
    raw = st.text_input(
        "Custom relation", key="kg_edit_rel_custom",
        placeholder="e.g. PATRONIZED",
    ).strip()
    sanitized = "".join(
        c for c in raw.upper().replace(" ", "_").replace("-", "_")
        if c.isalnum() or c == "_"
    )
    if sanitized:
        st.caption(f"Stored as: `{sanitized}`")
    return sanitized


def _render_edit_relation(
    all_nodes: list[dict],
    all_relations: list[str],
    all_triples: list[dict],
) -> None:
    if not all_triples:
        st.info("No relations in KG yet.")
        return

    triple_labels = [
        f"{t['subject']}  ──{t['relation']}──▶  {t['object']}"
        for t in all_triples
    ]
    selected_label = st.selectbox(
        "Select triple to edit", options=triple_labels,
        key="kg_edit_rel_sel", label_visibility="collapsed",
    )
    triple = all_triples[triple_labels.index(selected_label)]
    _reset_edit_form_if_changed(selected_label, triple, all_nodes, all_relations)

    col_s, col_o = st.columns(2)
    with col_s:
        new_subj, new_subj_label, subj_is_new = _entity_selector(
            all_nodes, "kg_edit_subj", triple["subject"], "Subject",
        )
    with col_o:
        new_obj, new_obj_label, obj_is_new = _entity_selector(
            all_nodes, "kg_edit_obj", triple["object"], "Object",
        )

    rel_options = all_relations + (
        [_CUSTOM_REL_SENTINEL] if _CUSTOM_REL_SENTINEL not in all_relations else []
    )
    cur_period = triple.get("period", "") or ""
    cur_source = (triple.get("source", "") or "").removeprefix("[manual] ")

    col_r, col_p = st.columns(2)
    with col_r:
        new_relation = _relation_type_input(rel_options, triple.get("relation", ""))
    with col_p:
        new_period = st.text_input(
            "Period", key="kg_edit_period",
            value=cur_period, placeholder="e.g. ක්‍රි.පූ. 29",
        )

    new_note = st.text_input(
        "Source / note", key="kg_edit_source",
        value=cur_source, placeholder="e.g. Mahavamsa Ch. 9",
    )

    _edit_msg = st.session_state.pop("_kg_edit_msg", None)
    if _edit_msg:
        if _edit_msg["type"] == "success":
            st.success(_edit_msg["text"])
        elif _edit_msg["type"] == "warning":
            st.warning(_edit_msg["text"])
        else:
            st.error(_edit_msg["text"])

    if st.button("💾 Save Changes", type="primary", key="kg_edit_rel_btn"):
        _do_edit_triple(
            triple,
            new_subj, new_subj_label, subj_is_new,
            new_relation,
            new_obj, new_obj_label, obj_is_new,
            new_period, new_note,
        )


def _render_edit_section(
    all_nodes: list[dict],
    all_relations: list[str],
    all_triples: list[dict],
) -> None:
    st.markdown(
        '<div class="kg-section-title">Edit Triple</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="kg-card" style="border-left: 4px solid #7b1fa2;">',
        unsafe_allow_html=True,
    )
    _render_edit_relation(all_nodes, all_relations, all_triples)
    st.markdown(_CARD_CLOSE, unsafe_allow_html=True)


#  Manual relation helpers

_MANUAL_FORM_KEYS = (
    "kg_man_subj_sel", "kg_man_subj_name", "kg_man_subj_label",
    "kg_man_rel_sel",  "kg_man_rel_custom",
    "kg_man_obj_sel",  "kg_man_obj_name",  "kg_man_obj_label",
    "kg_man_period",   "kg_man_note",
)


def _clear_manual_form() -> None:
    for k in _MANUAL_FORM_KEYS:
        st.session_state.pop(k, None)


def _validate_manual_inputs(subj_name: str, obj_name: str, relation: str) -> list[str]:
    errors: list[str] = []
    if not subj_name.strip():
        errors.append("Subject name is required.")
    if not obj_name.strip():
        errors.append("Object name is required.")
    if not relation.strip():
        errors.append(_ERR_REL_REQUIRED)
    return errors


def _do_save_manual(
    subj_name: str,
    subj_label: str,
    subj_is_new: bool,
    relation: str,
    obj_name: str,
    obj_label: str,
    obj_is_new: bool,
    period: str,
    note: str,
) -> None:
    from kg_store import upsert_entity, upsert_relation, normalize_name
    import kg_aliases

    errors = _validate_manual_inputs(subj_name, obj_name, relation)
    if errors:
        for msg in errors:
            st.session_state["_kg_manual_msg"] = {"type": "error", "text": msg}
        st.rerun()
        return

    subj_name = normalize_name(subj_name) if subj_is_new else subj_name.strip()
    obj_name  = normalize_name(obj_name)  if obj_is_new  else obj_name.strip()

    relation  = "".join(
        c for c in relation.upper().replace(" ", "_").replace("-", "_")
        if c.isalnum() or c == "_"
    )
    if not relation:
        st.session_state["_kg_manual_msg"] = {"type": "error", "text": "Relation type is invalid."}
        st.rerun()
        return

    source = f"{_MANUAL_SOURCE_TAG} {note}".strip() if note.strip() else _MANUAL_SOURCE_TAG

    try:
        if subj_is_new:
            upsert_entity(subj_name, subj_label, kg_aliases.get_aliases_for(subj_name))
        if obj_is_new:
            upsert_entity(obj_name, obj_label, kg_aliases.get_aliases_for(obj_name))

        created = upsert_relation(subj_name, relation, obj_name, period, source)
        if created is True:
            _clear_manual_form()
            _bump_graph_version()
            st.session_state["_kg_manual_msg"] = {
                "type": "success",
                "text": f"Saved: **{subj_name}** ──{relation}──▶ **{obj_name}**",
            }
        elif created is False:
            st.session_state["_kg_manual_msg"] = {
                "type": "warning",
                "text": f"Already in KG (duplicate skipped): **{subj_name}** ──{relation}──▶ **{obj_name}**",
            }
        else:  # None — one or both nodes not found
            st.session_state["_kg_manual_msg"] = {
                "type": "error",
                "text": (
                    f"Could not save — one or both nodes not found in KG: "
                    f"**{subj_name}** / **{obj_name}**. "
                    "Make sure both entities exist before creating a relation."
                ),
            }
        st.rerun()
    except Exception as exc:
        st.session_state["_kg_manual_msg"] = {"type": "error", "text": f"Save failed: {exc}"}
        st.rerun()


def _render_manual_relation_section(
    all_nodes: list[dict],
    all_relations: list[str],
) -> None:
    st.markdown(
        '<div class="kg-section-title">Add Manual Relation</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="kg-card" style="border-left: 4px solid #2e7d32;">',
        unsafe_allow_html=True,
    )
    st.caption(
        "Add historically accurate relations the pipeline missed — e.g. entities the "
        "NER model does not tag (Buddhist councils, festivals, treaties, etc.). "
        "Select an existing node or create a new one on either side."
    )

    node_options   = [_NEW_ENTITY_SENTINEL] + [n["name"] for n in all_nodes]
    node_label_map = {n["name"]: n["label"] for n in all_nodes}
    rel_options    = all_relations + [_CUSTOM_REL_SENTINEL]

    col_s, col_r, col_o = st.columns([3, 2, 3])

    #  Subject
    with col_s:
        st.markdown("**Subject**")
        subj_sel = st.selectbox(
            "Subject node", options=node_options,
            key="kg_man_subj_sel", label_visibility="collapsed",
        )
        if subj_sel == _NEW_ENTITY_SENTINEL:
            subj_name = st.text_input(
                "New subject name", key="kg_man_subj_name",
                placeholder="e.g. සිව්වන බෞද්ධ සංගායනාව",
            )
            subj_label = st.selectbox(
                "Subject type", options=_ALL_LABELS, key="kg_man_subj_label",
            )
            subj_is_new = True
        else:
            subj_name  = subj_sel
            subj_label = node_label_map.get(subj_sel, "Person")
            subj_is_new = False
            st.caption(f"Type: **{subj_label}**")

    #  Relation
    with col_r:
        st.markdown("**Relation**")
        rel_sel = st.selectbox(
            "Relation type", options=rel_options,
            key="kg_man_rel_sel", label_visibility="collapsed",
        )
        if rel_sel == _CUSTOM_REL_SENTINEL:
            raw_custom = st.text_input(
                "Custom relation", key="kg_man_rel_custom",
                placeholder="e.g. PATRONIZED",
            ).strip()
            # Show sanitized preview so user knows exactly what gets stored
            sanitized = "".join(
                c for c in raw_custom.upper().replace(" ", "_").replace("-", "_")
                if c.isalnum() or c == "_"
            )
            if sanitized:
                st.caption(f"Stored as: `{sanitized}`")
            relation = sanitized
        else:
            relation = rel_sel

    #  Object
    with col_o:
        st.markdown("**Object**")
        obj_sel = st.selectbox(
            "Object node", options=node_options,
            key="kg_man_obj_sel", label_visibility="collapsed",
        )
        if obj_sel == _NEW_ENTITY_SENTINEL:
            obj_name = st.text_input(
                "New object name", key="kg_man_obj_name",
                placeholder="e.g. සිව්වන බෞද්ධ සංගායනාව",
            )
            obj_label = st.selectbox(
                "Object type", options=_ALL_LABELS, key="kg_man_obj_label",
            )
            obj_is_new = True
        else:
            obj_name  = obj_sel
            obj_label = node_label_map.get(obj_sel, "Person")
            obj_is_new = False
            st.caption(f"Type: **{obj_label}**")

    #  Metadata
    col_p, col_n = st.columns(2)
    with col_p:
        period = st.text_input(
            "Period (optional)", key="kg_man_period",
            placeholder="e.g. ක්‍රි.පූ. 29",
        )
    with col_n:
        note = st.text_input(
            "Source / note", key="kg_man_note",
            placeholder="e.g. Mahavamsa Ch. 33 — manual entry",
        )

    # Show feedback from previous save attempt (cleared on next save)
    _man_msg = st.session_state.pop("_kg_manual_msg", None)
    if _man_msg:
        if _man_msg["type"] == "success":
            st.success(_man_msg["text"])
        elif _man_msg["type"] == "warning":
            st.warning(_man_msg["text"])
        else:
            st.error(_man_msg["text"])

    if st.button("💾 Save Manual Relation", type="primary", key="kg_man_save"):
        _do_save_manual(
            subj_name, subj_label, subj_is_new,
            relation,
            obj_name, obj_label, obj_is_new,
            period, note,
        )

    st.markdown(_CARD_CLOSE, unsafe_allow_html=True)


#  Interactive graph component

@st.cache_resource
def _make_graph_component():
    """Create a persistent temp dir + declared Streamlit component for the graph."""
    comp_dir = tempfile.mkdtemp()
    with open(os.path.join(comp_dir, "index.html"), "w", encoding="utf-8") as fh:
        fh.write("<html><body></body></html>")
    comp = components.declare_component("kg_graph", path=comp_dir)
    return comp_dir, comp


def _render_interactive_graph(html: str, height: int = 620) -> str | None:
    """Render interactive graph and return the last clicked value.

    A content-hash suffix in the component key forces the iframe to reload
    whenever the graph HTML changes (Streamlit reuses iframes for the same key).
    """
    import hashlib
    comp_dir, graph_comp = _make_graph_component()
    injected = html.replace("</body>", _STREAMLIT_GRAPH_JS + "\n</body>")
    with open(os.path.join(comp_dir, "index.html"), "w", encoding="utf-8") as fh:
        fh.write(injected)
    graph_ver = st.session_state.get("_kg_graph_ver", 0)
    html_hash = hashlib.md5(injected.encode()).hexdigest()[:10]
    return graph_comp(key=f"kg_c_{html_hash}_v{graph_ver}", default=None, height=height + 50)


# Page entry point

def _render_graph_section(
    triples: list[dict],
    selected_types: list[str],
    selected_rels: list[str],
    search_term: str,
) -> str | None:
    """Render graph + table. Returns the raw value sent by the last node click."""
    st.markdown(
        '<div class="kg-section-title">Interactive Graph</div>',
        unsafe_allow_html=True,
    )
    try:
        html, filtered_triples, oversized = _build_pyvis_html(
            triples, selected_types, selected_rels, search_term
        )
    except ImportError:
        st.error("pyvis is not installed. Run: `pip install pyvis`")
        st.stop()
    except Exception as e:
        st.error(f"Graph rendering error: {e}")
        st.stop()

    if oversized:
        st.info(
            f"The KG has more than {_MAX_NODES} nodes — showing only the "
            "largest connected component."
        )

    clicked: str | None = None
    if not filtered_triples:
        st.warning("No triples match the current filters.")
    else:
        _render_node_legend()
        st.markdown("<br>", unsafe_allow_html=True)
        clicked = _render_interactive_graph(html, height=700)

    st.markdown("<br>", unsafe_allow_html=True)

    if search_term:
        _render_node_detail(search_term, triples)

    # Always pass the full triple list so the table/delete section shows every
    # relation regardless of which node-types/relation-types the graph filter
    # has selected.  (Graph filters affect the visual only, not the browser.)
    _render_relation_table(triples)

    return clicked


def _render_graph_with_focus(triples: list[dict], all_relations: list[str]) -> None:
    selected_types, selected_rels, search_term = _render_filters(all_relations)

    focused: str | None = st.session_state.get("kg_focused_node")

    view_triples = (
        [t for t in triples
         if t.get("subject") == focused or t.get("object") == focused]
        if focused else triples
    )

    if focused:
        st.info(f"Focused on **{focused}** — click empty area in the graph to show all")
        if st.button("✕ Show full graph", key="kg_clear_focus"):
            st.session_state.pop("kg_focused_node", None)
            st.rerun()

    if not selected_types:
        st.warning("Select at least one node type.")
    elif not selected_rels:
        st.warning("Select at least one relation type.")
    else:
        raw = _render_graph_section(
            view_triples, selected_types, selected_rels, search_term.strip()
        )
        if raw and raw != "__CLEAR__" and raw != focused:
            st.session_state["kg_focused_node"] = raw
            st.rerun()
        elif raw == "__CLEAR__" and focused:
            st.session_state.pop("kg_focused_node", None)
            st.rerun()


def render() -> None:
    st.markdown("""
    <div class="kg-page-title">🕸️ Knowledge Graph</div>
    <div class="kg-page-subtitle">
      Interactive visualisation of the Sinhala Historical Knowledge Graph stored in Neo4j.
    </div>
    """, unsafe_allow_html=True)

    save_msg = st.session_state.pop("_kg_save_msg", None)
    if save_msg:
        st.success(save_msg)

    try:
        from kg_store import get_all_triples, get_all_relation_types, get_all_node_names
        triples       = get_all_triples(limit=_MAX_TRIPLES)
        all_relations = get_all_relation_types()
        all_nodes     = get_all_node_names()
    except Exception as e:
        st.warning(f"Could not load KG data: {e}")
        triples, all_relations, all_nodes = [], [], []

    if not triples:
        st.info("No data in KG yet. Go to **Extract & Save** and save some sentences first.")
    else:
        _render_graph_with_focus(triples, all_relations)

    if all_nodes:
        st.markdown("<br>", unsafe_allow_html=True)
        _render_edit_section(all_nodes, all_relations, triples)

    st.markdown("<br>", unsafe_allow_html=True)
    _render_manual_relation_section(all_nodes, all_relations)
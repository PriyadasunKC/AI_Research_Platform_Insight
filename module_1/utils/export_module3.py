"""
utils/export_module3.py
========================
Generates a file for every scored essay so it can be sent to Module 3
manually (however you like - email, WhatsApp, USB stick) until the two
modules are wired together via a direct API call.

Produces, per essay:
  - a .json file → exact payload shape from "10.2 What Module 1 Sends
                    to Module 3 at Runtime" in the Module 1 docs
  - a .txt file  → short human-readable version of the same data,
                    useful for a quick look without opening the JSON

Nothing here talks to Module 3 or any messaging service - it only
writes the files. Sharing them is up to you.
"""

import json
import os
import re
import unicodedata
from datetime import datetime, timezone

EXPORT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           "module3_exports")
os.makedirs(EXPORT_DIR, exist_ok=True)

# How each dimension code should be labelled in the file sent to Module 3.
DIMENSION_NAMES = {
    "D1": "Historical Accuracy(D1)",
    "D2": "Coherence & Idea Flow(D2)",
    "D3": "Vocabulary Richness(D3)",
    "D4": "Structural Adherence(D4)",
}


def _dim_label(code: str) -> str:
    """'D2' -> 'Coherence & Idea Flow(D2)' (unmapped codes pass through unchanged)."""
    return DIMENSION_NAMES.get(code, code)


def _rename_score_keys(scores: dict) -> dict:
    """{'D1':3,'D2':4,...} -> {'D1':3,'Coherence & Idea Flow':4,...}"""
    return {_dim_label(k): v for k, v in scores.items()}


def _rename_note_keys(notes: dict) -> dict:
    """{'D2_note': {...}} -> {'Coherence & Idea Flow': {...}}"""
    renamed = {}
    for key, note in notes.items():
        code = key.replace("_note", "")
        renamed[_dim_label(code)] = note
    return renamed


def _weakest_area_block(weakest_code, renamed_scores: dict, renamed_notes: dict):
    """
    Builds the 'weakest area' entry that goes after the three dimensions,
    e.g. weakest_code='D4' ->
        {
          "dimension": "Structural Adherence",
          "score": 3,
          "hint": "රචනා ව්‍යූහයේ පහත කොටස්..."
        }
    Returns None if no weakest dimension was determined.
    """
    if not weakest_code:
        return None
    label = _dim_label(weakest_code)
    note = renamed_notes.get(label) or {}
    return {
        "dimension": label,
        "score": renamed_scores.get(label),
        "hint": note.get("short_note_si", ""),
    }


def _safe_slug(text: str, max_len: int = 24) -> str:
    """Turn a possibly-empty/None id into a filesystem-safe slug."""
    if not text:
        return "essay"
    text = unicodedata.normalize("NFKD", text)
    text = re.sub(r"[^a-zA-Z0-9_-]+", "-", text).strip("-")
    return (text or "essay")[:max_len]


def build_module3_payload(essay_text: str, scores: dict, notes: dict,
                           weakest: str | None = None,
                           rag_context: list | None = None) -> dict:
    """
    Build the object sent to Module 3, based on the shape documented in
    section 10.2 of the Module 1 docs - with all four dimensions relabelled
    to their full names (D1 included, via Module 2's server-side result -
    see utils/module2_client.py), and a "weakest_area" block added right
    after them:

        {
          "essay_text": "...",
          "scores": {"Historical Accuracy(D1)":3, "Coherence & Idea Flow(D2)":2,
                     "Vocabulary Richness(D3)":3, "Structural Adherence(D4)":2},
          "notes": {"Historical Accuracy(D1)": {...},
                    "Coherence & Idea Flow(D2)": {...},
                    "Vocabulary Richness(D3)": {...},
                    "Structural Adherence(D4)": {...}},
          "weakest_area": {"dimension": "Structural Adherence(D4)", "score": 2,
                            "hint": "..."},
          "rag_context": [{"text":"...", "source":"...", "relevance":0.87}]
        }
    """
    renamed_scores = _rename_score_keys(scores)
    renamed_notes = _rename_note_keys(notes)

    return {
        "essay_text": essay_text,
        "scores": renamed_scores,
        "notes": renamed_notes,
        "weakest_area": _weakest_area_block(weakest, renamed_scores, renamed_notes),
        # RAG isn't wired into app.py's /score yet (Stage 3 in the docs) -
        # left as an empty list so the shape matches what Module 3 expects.
        "rag_context": rag_context or [],
    }


def build_readable_summary(essay_id: str, payload: dict, average_score=None,
                            summary_si: str = "") -> str:
    """A short plain-text version, good for WhatsApp / email bodies."""
    scores = payload.get("scores", {})
    notes = payload.get("notes", {})

    lines = [
        "INSIGHT - Module 1 → Module 3 handoff",
        f"Essay ID   : {essay_id}",
        f"Generated  : {datetime.now(timezone.utc).isoformat(timespec='seconds')}Z",
        f"Word count : {len(payload.get('essay_text', '').split())}",
        "",
        "Scores:",
    ]
    for label, value in scores.items():
        lines.append(f"  {label}: {value}")
    if average_score is not None:
        lines.append(f"  Average: {average_score}")

    lines.append("")
    lines.append("Notes for Module 3:")
    for key, note in notes.items():
        lines.append(f"  [{key}]")
        if isinstance(note, dict):
            if note.get("what_wrong"):
                lines.append(f"    what_wrong    : {note['what_wrong']}")
            if note.get("how_to_improve"):
                lines.append(f"    how_to_improve: {note['how_to_improve']}")
            if note.get("short_note_si"):
                lines.append(f"    short_note_si : {note['short_note_si']}")

    weakest_area = payload.get("weakest_area")
    if weakest_area:
        lines.append("")
        lines.append("වැඩිදියුණු කළ යුතු ප්‍රධාන ක්ෂේත්‍රය:")
        lines.append(f"  Dimension: {weakest_area.get('dimension', '')}")
        lines.append(f"  Score    : {weakest_area.get('score', '')}")
        if weakest_area.get("hint"):
            lines.append(f"  Hint     : {weakest_area['hint']}")

    if summary_si:
        lines.append("")
        lines.append(f"Summary (SI): {summary_si}")

    lines.append("")
    lines.append("Full essay text and RAG context are in the attached JSON file.")
    return "\n".join(lines)


def save_export_files(essay_text: str, scores: dict, notes: dict,
                       essay_id: str | None = None, rag_context=None,
                       average_score=None, summary_si: str = "",
                       weakest: str | None = None):
    """
    Writes both files to EXPORT_DIR and returns everything the Flask
    route needs to hand back to the client:

        {
          "essay_id": "...",
          "json_filename": "module3_export_....json",
          "txt_filename":  "module3_export_....txt",
          "json_path": "/abs/path/....json",
          "txt_path":  "/abs/path/....txt",
        }

    `weakest` is the dimension code (e.g. "D4") the /score route already
    computes as the essay's weakest area - pass it through so it gets
    added to the exported files right after the three dimensions.
    """
    payload = build_module3_payload(essay_text, scores, notes,
                                     weakest=weakest, rag_context=rag_context)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    slug = _safe_slug(essay_id or f"essay-{timestamp}")
    base_name = f"module3_export_{slug}_{timestamp}"

    json_filename = f"{base_name}.json"
    txt_filename = f"{base_name}.txt"

    json_path = os.path.join(EXPORT_DIR, json_filename)
    txt_path = os.path.join(EXPORT_DIR, txt_filename)

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    readable = build_readable_summary(essay_id or slug, payload,
                                       average_score=average_score,
                                       summary_si=summary_si)
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(readable)

    return {
        "essay_id": essay_id or slug,
        "json_filename": json_filename,
        "txt_filename": txt_filename,
        "json_path": json_path,
        "txt_path": txt_path,
        "readable_summary": readable,
    }
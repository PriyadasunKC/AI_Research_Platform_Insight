"""
kg_fact_retriever.py - KG Fact Retrieval (Stage 2, Module 2, 214161L)

Queries the LIVE Neo4j database first (via kg_store). The static KG export
(data/neo4j_query_table_data_2026-7-29.json) is used only as a fallback -
per king, only when Neo4j is unreachable or genuinely returns zero facts
for that king (which can happen if the static snapshot is newer/more
complete for that specific king than what's currently in the live graph).
See get_facts_for_king() below for exactly when each source is used.

Given a canonical king name, resolves every alternate name that refers to
the same person (kg_aliases + transitive ALSO_KNOWN_AS edges) and returns
every KG fact relevant to that person, formatted for the Claude prompt.
"""

from __future__ import annotations

import json
import unicodedata
from pathlib import Path

import kg_aliases
import kg_store

_DATA_DIR    = Path(__file__).resolve().parent / "data"
_KG_JSON_FILE = _DATA_DIR / "neo4j_query_table_data_2026-7-29.json"

# Relation types prioritised first when a king has more than 80 facts -
# the ones most likely to matter for essay fact-checking.
_PRIORITY_RELATIONS: tuple[str, ...] = (
    "BUILT", "DEFEATED", "RULED", "UNITED", "FATHER_OF", "MOTHER_OF", "SON_OF",
    "BROTHER_OF", "MARRIED", "WIFE_OF", "BORN_IN", "DIED_AT", "ALSO_KNOWN_AS",
)
_MAX_FACTS = 80

_kg_cache: list[dict] | None = None


def load_kg() -> list[dict]:
    """Load and return all KG triples from the JSON file (cached after first call)."""
    global _kg_cache
    if _kg_cache is not None:
        return _kg_cache
    if not _KG_JSON_FILE.exists():
        _kg_cache = []
        return _kg_cache
    try:
        _kg_cache = json.loads(_KG_JSON_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        _kg_cache = []
    return _kg_cache


def _nfc(name: str) -> str:
    return unicodedata.normalize("NFC", (name or "").strip())


def get_all_kg_names_for_king(canonical_name: str) -> set[str]:
    """Collect every name in the KG that refers to the same king as canonical_name.

    1. canonical_name itself
    2. kg_aliases.get_aliases_for(canonical_name)
    3. Transitive ALSO_KNOWN_AS closure (both directions) in the KG JSON
    """
    canonical_name = _nfc(canonical_name)
    names: set[str] = {canonical_name}
    names.update(_nfc(a) for a in kg_aliases.get_aliases_for(canonical_name))

    aka_triples = [t for t in load_kg() if t.get("relation") == "ALSO_KNOWN_AS"]

    changed = True
    while changed:
        changed = False
        for t in aka_triples:
            subj = _nfc(t.get("subject", ""))
            obj  = _nfc(t.get("object", ""))
            if not subj or not obj:
                continue
            if subj in names and obj not in names:
                names.add(obj)
                changed = True
            if obj in names and subj not in names:
                names.add(subj)
                changed = True

    return names


def _facts_from_static_export(canonical_name: str) -> list[dict]:
    """The original static-export lookup - now used only as a fallback."""
    names = get_all_kg_names_for_king(canonical_name)
    facts: list[dict] = []
    for t in load_kg():
        if _nfc(t.get("subject", "")) in names or _nfc(t.get("object", "")) in names:
            facts.append(t)
    return facts


def get_facts_for_king(canonical_name: str) -> list[dict]:
    """Return all KG triples where subject OR object is one of this king's names.

    Tries live Neo4j first (kg_store.get_facts_for_entity_cluster), falling
    back to the static export (data/neo4j_query_table_data_2026-7-29.json)
    only when:
      - Neo4j is unreachable (get_facts_for_entity_cluster returns None), or
      - Neo4j is reachable but returns zero facts for this specific king
        (the static snapshot may cover a king not yet re-extracted live).
    A non-empty live result is used as-is and never merged with the static
    export, so a single essay-check run's facts all come from one source.

    ALSO_KNOWN_AS triples ARE included in both sources - an essay may state
    a king's alternate name or title as a fact in its own right (e.g. "he
    was honored with the title Pandita Vijayabahu"), and the KG already
    records that as an ALSO_KNOWN_AS edge. Excluding these left such claims
    wrongly UNVERIFIABLE even though the KG could confirm them.
    """
    canonical_name = _nfc(canonical_name)
    seed_names = [canonical_name] + [_nfc(a) for a in kg_aliases.get_aliases_for(canonical_name)]

    live_facts = kg_store.get_facts_for_entity_cluster(seed_names)
    if live_facts:
        return live_facts
    if live_facts is None:
        print(f"[EssayChecker] Neo4j unreachable - falling back to static KG export for {canonical_name!r}")
    else:
        print(f"[EssayChecker] Live KG has no facts for {canonical_name!r} - falling back to static KG export")

    return _facts_from_static_export(canonical_name)


def format_facts_for_prompt(facts: list[dict]) -> str:
    """Format facts as a numbered Sinhala-readable list for the Claude prompt.

    If more than 80 facts, prioritizes relation types in _PRIORITY_RELATIONS
    order, then all remaining relation types, and truncates to 80.
    """
    if not facts:
        return "(මෙම රජු පිළිබඳව Knowledge Graph හි කිසිදු කරුණක් සටහන් වී නොමැත.)"

    ordered = facts
    if len(facts) > _MAX_FACTS:
        priority_rank = {rel: i for i, rel in enumerate(_PRIORITY_RELATIONS)}
        ordered = sorted(
            facts,
            key=lambda t: priority_rank.get(t.get("relation", ""), len(_PRIORITY_RELATIONS)),
        )[:_MAX_FACTS]

    lines: list[str] = []
    for i, t in enumerate(ordered, start=1):
        subj   = t.get("subject", "")
        rel    = t.get("relation", "")
        obj    = t.get("object", "")
        period = (t.get("period") or "").strip()
        period_str = f" (කාලය: {period})" if period else ""
        lines.append(f"{i}. {subj} - {rel} - {obj}{period_str}")

    return "\n".join(lines)

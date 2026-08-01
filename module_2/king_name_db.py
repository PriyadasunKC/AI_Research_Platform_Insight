"""
king_name_db.py - King Name Knowledge Base (Stage 2, Module 2, 214161L)

Builds a master lookup of every Sri Lankan king / monarch name we know about,
merging three sources:

    1. data/sri_lankan_kings_all_names.txt - the authoritative name list,
       including kings not yet represented in the KG.
    2. kg_aliases.CANONICAL_ALIASES        - the same-person alias map used
       by the storage layer (kg_store.py) when writing to Neo4j.
    3. ALSO_KNOWN_AS edges - alternate names discovered by the extraction
       pipeline itself. Read from the LIVE Neo4j database first; falls back
       to the static export (neo4j_query_table_data_2026-7-29.json) only if
       Neo4j is unreachable.

This index is the single lookup used by the essay-checking pipeline to
recognise which king(s) a student essay is talking about, independent of
which exact surface form (title, spelling, ancient name, ...) the essay uses.
"""

from __future__ import annotations

import difflib
import json
import re
import unicodedata
from pathlib import Path

import kg_aliases

_DATA_DIR         = Path(__file__).resolve().parent / "data"
_KING_NAMES_FILE  = _DATA_DIR / "sri_lankan_kings_all_names.txt"
_KG_JSON_FILE     = _DATA_DIR / "neo4j_query_table_data_2026-7-29.json"

# Trailing Sinhala royal/monastic title suffixes stripped for comparison
# purposes only - the underlying entity name is unaffected.
#
# Beyond the suffixes explicitly required by the spec, "රජ" and "මහරජු" are
# included because data/sri_lankan_kings_all_names.txt uses the informal
# spelling "රජ" (no ු) for the vast majority of its 105 entries, while
# kg_aliases.py's canonical keys mostly use the formal "රජු" - without this,
# most of the name-list entries would fail to resolve against the KG at all.
_TITLE_SUFFIXES: tuple[str, ...] = (
    "හාමුදුරුවන්",
    "හාමුදුරුවෝ",
    "කුමාරයා",
    "හිමිණිය",
    "මහරජු",
    "මහරජ",
    "කුමරු",
    "දේවිය",
    "රැජින",
    "රාජා",
    "රාජ",
    "රජු",
    "රජ",
    "හිමි",
)
_SORTED_SUFFIXES: tuple[str, ...] = tuple(
    sorted(_TITLE_SUFFIXES, key=len, reverse=True)
)

_FUZZY_THRESHOLD = 0.85

# kg_aliases.CANONICAL_ALIASES also carries LOCATIONS / MONUMENTS / DYNASTIES /
# CHRONICLES sections (needed by kg_store.py for entity normalization) - those
# are not people and must not be treated as "kings found" in an essay. The KG
# JSON export has no per-entity type field to filter on programmatically, so
# these canonical keys (exactly as they appear in kg_aliases.py) are excluded
# by name. Kept: KINGS / RULERS, MONKS / RELIGIOUS FIGURES, OTHER PERSONS.
_NON_PERSON_CANONICALS: frozenset[str] = frozenset({
    # LOCATIONS
    "ශ්‍රී ලංකාව", "අනුරාධපුරය", "පොළොන්නරුව", "රුහුණ", "උපතිස්ස නුවර", "මාගම", "දඹදෙණිය",
    # MONUMENTS / SITES
    "රුවන්වැලිසෑය", "සීගිරිය", "ඉශුරුමුණිය", "තූපාරාමය", "අභයගිරි විහාරය",
    "දළදා මාළිගාව", "මහමෙවුනා උද්‍යානය", "රන්ගිරි දඹුළු රජමහා විහාරය",
    # DYNASTIES
    "ලම්බකර්ණ රාජ වංශය", "නායක්කාර රාජ වංශය",
    # CHRONICLES
    "මහාවංශය", "චූලවංශය", "දීපවංශය",
})


# NORMALIZATION

def normalize_sinhala(text: str) -> str:
    """Normalize Sinhala text for name comparison.

    - Unicode NFC normalize + strip whitespace
    - Strip a single trailing title suffix (රජු, රාජ, රාජා, හිමි, ...)
    """
    text = unicodedata.normalize("NFC", text).strip()
    if not text:
        return text
    for suffix in _SORTED_SUFFIXES:
        if text.endswith(suffix):
            stem = text[: -len(suffix)].strip()
            if len(stem) >= 2:
                return stem
    return text


# SOURCE 1 - sri_lankan_kings_all_names.txt

_NUM_LINE_RE = re.compile(r"^\d+\.\s*(.+)$")
_PAREN_RE    = re.compile(r"\s*\([^)]*\)\s*$")


def _parse_king_names_file() -> list[str]:
    """Extract the numbered king-name entries from the raw text file."""
    names: list[str] = []
    if not _KING_NAMES_FILE.exists():
        return names
    for line in _KING_NAMES_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        m = _NUM_LINE_RE.match(line)
        if not m:
            continue
        name = _PAREN_RE.sub("", m.group(1)).strip()
        if name:
            names.append(unicodedata.normalize("NFC", name))
    return names


KING_NAME_DB: list[str] = _parse_king_names_file()


# SOURCE 3 - ALSO_KNOWN_AS edges, live Neo4j first, static export as fallback

def _load_kg_json() -> list[dict]:
    """Return ALSO_KNOWN_AS-relevant triples: live Neo4j first, falling back
    to the static export only if Neo4j is unreachable (see kg_store.
    get_also_known_as_edges - None signals "couldn't ask", not "no edges").
    """
    import kg_store
    live = kg_store.get_also_known_as_edges()
    if live is not None:
        return live

    if not _KG_JSON_FILE.exists():
        return []
    try:
        return json.loads(_KG_JSON_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []


def _kg_also_known_as_clusters(kg_data: list[dict]) -> dict[str, str]:
    """Union-Find clustering of every ALSO_KNOWN_AS-linked entity name.

    Returns: {member_name: representative_canonical_name} for every name
    that appears as subject or object of an ALSO_KNOWN_AS triple.

    Representative choice, in priority order:
      1. A cluster member that is itself a kg_aliases.CANONICAL_ALIASES key.
      2. The member that occurs most often (as subject or object) anywhere
         else in the KG - a proxy for "the name actually used elsewhere".
      3. Arbitrary first member (Union-Find root).
    """
    parent: dict[str, str] = {}

    def find(x: str) -> str:
        parent.setdefault(x, x)
        root = x
        while parent[root] != root:
            root = parent[root]
        while parent[x] != root:
            parent[x], x = root, parent[x]
        return root

    def union(a: str, b: str) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    for triple in kg_data:
        if triple.get("relation") != "ALSO_KNOWN_AS":
            continue
        subj = unicodedata.normalize("NFC", (triple.get("subject") or "").strip())
        obj  = unicodedata.normalize("NFC", (triple.get("object")  or "").strip())
        if subj and obj:
            union(subj, obj)

    if not parent:
        return {}

    counts: dict[str, int] = {}
    for t in kg_data:
        for field in ("subject", "object"):
            n = unicodedata.normalize("NFC", (t.get(field) or "").strip())
            if n:
                counts[n] = counts.get(n, 0) + 1

    groups: dict[str, list[str]] = {}
    for name in parent:
        groups.setdefault(find(name), []).append(name)

    member_to_canonical: dict[str, str] = {}
    for members in groups.values():
        canonical_key_members = [m for m in members if m in kg_aliases.CANONICAL_ALIASES]
        if canonical_key_members:
            rep = max(canonical_key_members, key=len)
        else:
            rep = max(members, key=lambda m: (counts.get(m, 0), m))
        for m in members:
            member_to_canonical[m] = rep

    return member_to_canonical


# MASTER INDEX

def build_king_index() -> dict[str, str]:
    """Return {normalized_or_raw_name: canonical_name} covering every source.

    Covers:
      - Every name in KING_NAME_DB (exact)
      - Every alias from kg_aliases.CANONICAL_ALIASES
      - Every entity appearing as subject or object of ALSO_KNOWN_AS in the KG JSON
    """
    index: dict[str, str] = {}

    def _register(raw_name: str, canonical: str) -> None:
        raw_name  = unicodedata.normalize("NFC", raw_name).strip()
        canonical = unicodedata.normalize("NFC", canonical).strip()
        if not raw_name or not canonical:
            return
        for key in {raw_name, normalize_sinhala(raw_name)}:
            if key and key not in index:
                index[key] = canonical

    # 1. KING_NAME_DB - resolve to the KG canonical if already known there.
    for raw_name in KING_NAME_DB:
        stripped  = normalize_sinhala(raw_name)
        canonical = kg_aliases.resolve_to_canonical(stripped)
        if canonical == stripped:
            alt = kg_aliases.resolve_to_canonical(raw_name)
            if alt != raw_name:
                canonical = alt
        _register(raw_name, canonical)

    # 2. kg_aliases.CANONICAL_ALIASES - canonical keys + every alias,
    #    excluding the non-person (location/monument/dynasty/chronicle) entries.
    for canonical, aliases in kg_aliases.CANONICAL_ALIASES.items():
        if canonical in _NON_PERSON_CANONICALS:
            continue
        _register(canonical, canonical)
        for alias in aliases:
            _register(alias, canonical)

    # 3. ALSO_KNOWN_AS entities from the KG JSON (transitively clustered).
    # The JSON has no per-entity type field, so a cluster is only accepted
    # into this *king* index if at least one of its members is already a
    # known person name from step 1 or step 2 above - this keeps unrelated
    # place/monument ALSO_KNOWN_AS chains (e.g. temple alt-names) out.
    known_person_names: set[str] = set(index.keys()) | set(index.values())
    kg_data = _load_kg_json()
    for name, canonical in _kg_also_known_as_clusters(kg_data).items():
        cluster_is_person = (
            name in known_person_names
            or canonical in known_person_names
            or normalize_sinhala(name) in known_person_names
            or normalize_sinhala(canonical) in known_person_names
        )
        if cluster_is_person:
            _register(name, canonical)

    return index


# TEXT SCANNING

# Word-boundary guard for Pass 1 (see _has_clean_boundary): a short index
# entry like the alias "සිංහ" (for සිංහබාහු) is a literal substring of the
# ordinary word "සිංහල" ("Sinhala"/the nation) - which appears constantly in
# any Sinhala historical essay. Naive substring matching turned every mention
# of "Sinhala" into a false hit for king සිංහබාහු, which was frequent enough
# to hijack primary-subject detection on essays that never mention him at
# all. A match is only accepted if it isn't glued to more Sinhala-script
# text on either side - except when that continuation is a recognised
# grammatical case/title suffix (e.g. "දුටුගැමුණුගේ" must still match, since
# that's a legitimate inflected form of "දුටුගැමුණු", not a different word).
_SINHALA_LO, _SINHALA_HI = "඀", "෿"

_BOUNDARY_CONTINUATIONS: tuple[str, ...] = tuple(
    sorted(
        set(_TITLE_SUFFIXES) | {
            "ගේ", "ෙන්", "ෙහි", "ේදී", "හිදී", "ෙකු", "හු", "ට", "ේ", "ව", "න්",
        },
        key=len, reverse=True,
    )
)


def _is_sinhala_char(ch: str) -> bool:
    return _SINHALA_LO <= ch <= _SINHALA_HI


def _has_clean_boundary(text: str, start: int, end: int) -> bool:
    """True if text[start:end) is a whole name/word, not embedded inside a
    longer, unrelated run of Sinhala-script text."""
    if start > 0 and _is_sinhala_char(text[start - 1]):
        return False
    if end < len(text) and _is_sinhala_char(text[end]):
        tail = text[end:]
        if not any(tail.startswith(suf) for suf in _BOUNDARY_CONTINUATIONS):
            return False
    return True


def find_king_in_text(text: str) -> list[dict]:
    """Scan text for any king name from the master index.

    Pass 1 - exact substring match against every index entry, with a
             word-boundary check (see _has_clean_boundary) so a short name
             embedded inside an unrelated longer word doesn't count.
    Pass 2 - fuzzy match (difflib.SequenceMatcher, threshold 0.85) -
             only runs if Pass 1 finds nothing.

    Returns a list of hits sorted by position in text.
    """
    if not text or not text.strip():
        return []

    index = build_king_index()
    text_nfc = unicodedata.normalize("NFC", text)

    # Pass 1 - exact match, longest names first so e.g. "විජයබාහු" is not
    # shadowed by a shorter name like "විජය" matching inside it.
    sorted_names = sorted((n for n in index if len(n) >= 2), key=len, reverse=True)
    covered = bytearray(len(text_nfc))
    hits: list[dict] = []

    for name in sorted_names:
        search_from = 0
        while True:
            idx = text_nfc.find(name, search_from)
            if idx == -1:
                break
            end = idx + len(name)
            if not any(covered[idx:end]) and _has_clean_boundary(text_nfc, idx, end):
                hits.append({
                    "found_name": name,
                    "canonical":  index[name],
                    "method":     "exact",
                    "confidence": 1.0,
                    "position":   idx,
                })
                for i in range(idx, end):
                    covered[i] = 1
            search_from = idx + 1

    if hits:
        hits.sort(key=lambda h: h["position"])
        return hits

    # Pass 2 - fuzzy match against Sinhala word-like tokens in the text.
    fuzzy_hits: list[dict] = []
    for m in re.finditer(r"[඀-෿]+", text_nfc):
        token = m.group()
        if len(token) < 2:
            continue
        best_name, best_score = None, 0.0
        for name in index:
            if len(name) < 2:
                continue
            score = difflib.SequenceMatcher(None, token, name).ratio()
            if score > best_score:
                best_name, best_score = name, score
        if best_name is not None and best_score >= _FUZZY_THRESHOLD:
            fuzzy_hits.append({
                "found_name": token,
                "canonical":  index[best_name],
                "method":     "fuzzy",
                "confidence": round(best_score, 3),
                "position":   m.start(),
            })

    fuzzy_hits.sort(key=lambda h: h["position"])
    return fuzzy_hits

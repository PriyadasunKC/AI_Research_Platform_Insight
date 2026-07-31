"""
kg_store.py — Neo4j storage module for the Sinhala Historical KG.

Design principle: switching to a different graph DB only requires changing
this file. All callers (pipeline.py, Streamlit pages) use only the public
functions defined at the bottom of this module.

Connection is lazy — the driver is created on first use so that importing
this module never raises, even when Neo4j is not running.
"""

from __future__ import annotations

import os
import re
import time
import unicodedata

from dotenv import load_dotenv

import kg_aliases
from normalizer import normalize_entity

load_dotenv()

#  Config (read from .env)

NEO4J_URI:      str = os.environ.get("NEO4J_URI",      "bolt://localhost:7687")
NEO4J_USER:     str = os.environ.get("NEO4J_USER",     "neo4j")
NEO4J_PASSWORD: str = os.environ.get("NEO4J_PASSWORD", "")

# NER label → Neo4j node label mapping

_LABEL_MAP: dict[str, str | None] = {
    "PERSON_KING":  "King",
    "PERSON_MONK":  "Monk",
    "PERSON_OTHER": "Person",
    "LOCATION":     "Place",
    "MONUMENT":     "Monument",
    "DYNASTY":      "Dynasty",
    "BATTLE_EVENT": "Battle",
    "DATE_ERA":     None,       # never stored as a node
    "CHRONICLE":    "Chronicle",
    "RELIC":        "Relic",
}

# Reusable Cypher fragments for node lookup by name / alias
_CQL_EID_BY_NAME  = "MATCH (n:Entity) WHERE n.name = $name RETURN elementId(n) AS eid LIMIT 1"
_CQL_EID_BY_ALIAS = (
    "MATCH (n:Entity) WHERE $name IN coalesce(n.aliases, []) "
    "RETURN elementId(n) AS eid LIMIT 1"
)

# Driver (lazily initialised)

_driver = None
_indexes_ensured = False

# If a connection attempt fails, don't retry on every single call for a
# while — essay-checker callers may call into this module once per king
# found in an essay (see kg_fact_retriever.get_facts_for_king), and without
# this cooldown, a genuinely-down Neo4j would pay a fresh connection-timeout
# cost on every one of those calls instead of failing fast after the first.
_last_connect_failure: float | None = None
_CONNECT_RETRY_COOLDOWN_SECS = 30.0


def _get_driver():
    """Return a live Neo4j driver, or None if the connection cannot be made."""
    global _driver, _last_connect_failure
    if _driver is not None:
        return _driver
    if (
        _last_connect_failure is not None
        and time.monotonic() - _last_connect_failure < _CONNECT_RETRY_COOLDOWN_SECS
    ):
        return None
    try:
        from neo4j import GraphDatabase
        drv = GraphDatabase.driver(
            NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD)
        )
        drv.verify_connectivity()
        _driver = drv
        _last_connect_failure = None
        _ensure_indexes(_driver)
        return _driver
    except Exception as exc:
        print(f"[KG] Neo4j connection failed ({NEO4J_URI}): {exc}")
        _last_connect_failure = time.monotonic()
        return None


def _ensure_indexes(driver) -> None:
    """Create the Entity.name index once per process lifetime."""
    global _indexes_ensured
    if _indexes_ensured:
        return
    try:
        with driver.session() as s:
            s.run(
                "CREATE INDEX entity_name_idx IF NOT EXISTS "
                "FOR (n:Entity) ON (n.name)"
            )
        _indexes_ensured = True
    except Exception as exc:
        print(f"[KG] Could not create index: {exc}")


# Internal helpers

def _find_existing_node(session, name: str):
    """Return a neo4j Node if a node with this name or alias exists.

    Exact name match is checked first so a node stored under this exact name
    is always preferred over another node that merely lists it as an alias.
    """
    result = session.run(
        "MATCH (n:Entity) WHERE n.name = $name RETURN n LIMIT 1",
        name=name,
    ).single()
    if result:
        return result["n"]
    result = session.run(
        "MATCH (n:Entity) WHERE $name IN coalesce(n.aliases, []) RETURN n LIMIT 1",
        name=name,
    ).single()
    return result["n"] if result else None


_SINHALA_CASE_SUFFIXES: tuple[str, ...] = (
    "ෙකු",  # dative (human classifier)
    "ෙන්",  # ablative/instrumental
    "ෙහි",  # locative formal
    "ේදී",  # locative+particle "at": "විහාරයේදී" → "විහාරය"
    "හිදී", # formal locative+particle: "ලංකාහිදී" → "ලංකා"
    "ගේ",   # genitive
    "ේ",    # locative
    "ට",    # dative
    "හු",   # plural/formal
)


def _nfc(name: str) -> str:
    """Unicode NFC-normalize and strip whitespace — prevents invisible-char duplicates."""
    return unicodedata.normalize("NFC", name.strip())


def _canonical_entity(name: str) -> str:
    """Strip Sinhala grammatical case suffix, apply morphological normalization,
    then resolve to the KG canonical name via the alias map.

    Three-step pipeline:
      1. Strip grammatical case suffix ("විජයට" → "විජය")
      2. normalize_entity: morphological alias map ("ලංකාව" → "ශ්‍රී ලංකාව")
      3. resolve_to_canonical: cross-source alias map ("රත්නදීපය" → "ශ්‍රී ලංකාව")

    Step 3 prevents creating duplicate nodes when the NER outputs an ancient
    or alternative name that kg_aliases already registers as an alias.
    """
    name = _nfc(name)
    for suffix in _SINHALA_CASE_SUFFIXES:
        if name.endswith(suffix):
            stem = name[: -len(suffix)]
            if len(stem) >= 2:
                name = stem
                break
    name = normalize_entity(name)
    return kg_aliases.resolve_to_canonical(name)


def _safe_label(label: str) -> str:
    """Validate label against allowed set to prevent Cypher injection."""
    allowed = {"King", "Monk", "Person", "Place", "Monument",
               "Dynasty", "Battle", "Chronicle", "Relic", "Era", "Technology", "Animal"}
    if label not in allowed:
        raise ValueError(f"Unknown KG label: {label!r}")
    return label


def _safe_relation(relation: str) -> str:
    """Sanitize relation type to safe UPPER_SNAKE_CASE for Cypher backtick use."""
    clean = re.sub(r"[^A-Z0-9_]", "", relation.upper().replace(" ", "_").replace("-", "_"))
    if not clean:
        raise ValueError(f"Relation type cannot be made safe: {relation!r}")
    return clean


# Public API

def resolve_entity_name(name: str) -> str:
    """Public wrapper — resolve any name/alias to its KG canonical form."""
    return _canonical_entity(name)


def normalize_name(name: str) -> str:
    """NFC-normalize and strip whitespace only — no suffix stripping or alias resolution.

    Use this for manually entered entity names where the user has already chosen
    the exact canonical form they want stored.
    """
    return _nfc(name)


def update_node_label(name: str, new_label: str) -> bool:
    """Change the type label of an existing node.

    Finds the node by exact name first (alias fallback), removes the old
    type label, and sets the new one. Returns True on success.
    """
    drv = _get_driver()
    if drv is None:
        return False

    new_label = _safe_label(new_label)

    with drv.session() as s:
        rec = s.run(
            "MATCH (n:Entity) WHERE n.name = $name "
            "RETURN elementId(n) AS eid, "
            "[x IN labels(n) WHERE x <> 'Entity'][0] AS old_label LIMIT 1",
            name=name,
        ).single()
        if not rec:
            rec = s.run(
                "MATCH (n:Entity) WHERE $name IN coalesce(n.aliases, []) "
                "RETURN elementId(n) AS eid, "
                "[x IN labels(n) WHERE x <> 'Entity'][0] AS old_label LIMIT 1",
                name=name,
            ).single()
        if not rec:
            return False

        eid       = rec["eid"]
        old_label = rec["old_label"]

        if old_label == new_label:
            return True  # nothing to do

        # old_label is sourced from Neo4j and constrained to the allowed set — safe to embed
        if old_label:
            _safe_label(old_label)  # validate before embedding in Cypher
            s.run(
                f"MATCH (n:Entity) WHERE elementId(n) = $eid "
                f"REMOVE n:{old_label} SET n:{new_label}",
                eid=eid,
            )
        else:
            s.run(
                f"MATCH (n:Entity) WHERE elementId(n) = $eid SET n:{new_label}",
                eid=eid,
            )
        return True


def update_relation_properties(
    subject: str,
    old_relation: str,
    obj: str,
    new_relation: str,
    new_period: str,
    new_source: str,
) -> bool:
    """Edit an existing relation's type and/or properties.

    If only period/source changed: updates in place.
    If relation type changed: deletes old edge, creates new one with updated properties.

    Subject and object are looked up by exact name (they are existing nodes).
    All alias and canonical checks are applied to the new relation type.
    Returns True if the edit succeeded.
    """
    drv = _get_driver()
    if drv is None:
        return False

    old_relation = _safe_relation(old_relation)
    new_relation = _safe_relation(new_relation)

    with drv.session() as s:
        # Exact-name lookup — subject/object are real node names from the UI
        subj_rec = s.run(_CQL_EID_BY_NAME, name=subject).single()
        if not subj_rec:
            subj_rec = s.run(_CQL_EID_BY_ALIAS, name=subject).single()

        obj_rec = s.run(_CQL_EID_BY_NAME, name=obj).single()
        if not obj_rec:
            obj_rec = s.run(_CQL_EID_BY_ALIAS, name=obj).single()

        if not subj_rec or not obj_rec:
            return False

        a_eid = subj_rec["eid"]
        b_eid = obj_rec["eid"]

        if old_relation == new_relation:
            # Only period/source changed — update in place
            result = s.run(
                f"MATCH (a:Entity)-[r:`{old_relation}`]->(b:Entity) "
                "WHERE elementId(a) = $a AND elementId(b) = $b "
                "SET r.period = $period, r.source_citation = $source "
                "RETURN r",
                a=a_eid, b=b_eid, period=new_period, source=new_source,
            )
            return result.single() is not None

        # Relation type changed — delete old, create new
        s.run(
            f"MATCH (a:Entity)-[r:`{old_relation}`]->(b:Entity) "
            "WHERE elementId(a) = $a AND elementId(b) = $b DELETE r",
            a=a_eid, b=b_eid,
        )
        # Duplicate check before creating
        dup = s.run(
            f"MATCH (a:Entity)-[r:`{new_relation}`]->(b:Entity) "
            "WHERE elementId(a) = $a AND elementId(b) = $b RETURN r LIMIT 1",
            a=a_eid, b=b_eid,
        ).single()
        if dup:
            return True  # already exists with new type — old deleted, done
        result = s.run(
            "MATCH (a:Entity), (b:Entity) "
            "WHERE elementId(a) = $a AND elementId(b) = $b "
            f"CREATE (a)-[r:`{new_relation}` {{"
            "  relation_type: $rel, period: $period, "
            "  source_citation: $source, confidence: 1.0"
            "}]->(b) RETURN r",
            a=a_eid, b=b_eid,
            rel=new_relation, period=new_period, source=new_source,
        )
        return result.single() is not None


def delete_triple(subject: str, relation: str, obj: str) -> bool:
    """Delete a specific directed relationship between two nodes.

    Looks up subject and object by exact name first, then alias fallback.
    Returns True if the edge existed and was deleted.
    """
    drv = _get_driver()
    if drv is None:
        return False
    relation = _safe_relation(relation)
    with drv.session() as s:
        def _eid(name: str):
            r = s.run(_CQL_EID_BY_NAME, name=name).single()
            if r:
                return r["eid"]
            r = s.run(_CQL_EID_BY_ALIAS, name=name).single()
            return r["eid"] if r else None

        a_eid = _eid(subject)
        b_eid = _eid(obj)
        if a_eid is None or b_eid is None:
            return False
        result = s.run(
            f"MATCH (a:Entity)-[r:`{relation}`]->(b:Entity) "
            "WHERE elementId(a) = $a AND elementId(b) = $b "
            "DELETE r RETURN count(r) AS n",
            a=a_eid, b=b_eid,
        )
        rec = result.single()
        return rec is not None and rec["n"] > 0


def upsert_entity(name: str, label: str, aliases: list[str] | None = None) -> None:
    """Insert or update a KG node.

    MERGE logic (alias rule):
      If a node already exists where n.name = $name OR $name IN n.aliases,
      merge into that node (add new aliases). Otherwise create a fresh node.

    Args:
        name:    Canonical entity name.
        label:   Neo4j node label (King, Monk, Place, …).
        aliases: Additional alternative names to store on the node.
    """
    drv = _get_driver()
    if drv is None:
        return

    name      = _nfc(name)
    label     = _safe_label(label)
    aliases   = [_nfc(a) for a in (aliases or [])]
    with drv.session() as s:
        existing = _find_existing_node(s, name)
        if existing:
            print(f"[KG] upsert_entity MERGE  name={name!r}  elementId={existing.element_id}  new_aliases={aliases}")
            s.run(
                "MATCH (n:Entity) WHERE elementId(n) = $nid "
                "SET n.aliases = "
                "  [a IN coalesce(n.aliases,[]) WHERE a IS NOT NULL] + "
                "  [a IN $new_aliases WHERE NOT a IN coalesce(n.aliases,[])]",
                nid=existing.element_id,
                new_aliases=aliases,
            )
            print("[KG] upsert_entity MERGE  OK")
        else:
            print(f"[KG] upsert_entity CREATE name={name!r}  label={label}  aliases={aliases}")
            s.run(
                f"CREATE (n:Entity:{label} {{name: $name, aliases: $aliases}})",
                name=name,
                aliases=aliases,
            )
            print("[KG] upsert_entity CREATE OK")


def upsert_relation(
    subject: str,
    relation: str,
    obj: str,
    period: str,
    source_sentence: str,
) -> bool:
    """Insert a directed relationship between two existing nodes.

    Duplicate check: skips creation if an edge of the same type already
    exists between these two nodes.

    Returns:
        True if a new edge was created, False if skipped (duplicate or error).
    """
    drv = _get_driver()
    if drv is None:
        return False

    subject  = _nfc(subject)
    obj      = _nfc(obj)
    relation = _safe_relation(relation)
    print(f"[KG] upsert_relation  subj={subject!r}  rel={relation!r}  obj={obj!r}")

    with drv.session() as s:
        # Resolve nodes — exact name first, alias fallback.
        # Exact-name priority ensures a node stored under this name is always
        # preferred over a different node that merely lists it as an alias.
        def _lookup_eid(session, name: str):
            r = session.run(_CQL_EID_BY_NAME, name=name).single()
            if r:
                return r
            return session.run(_CQL_EID_BY_ALIAS, name=name).single()

        subj_rec = _lookup_eid(s, subject)
        obj_rec  = _lookup_eid(s, obj)

        print(f"[KG] upsert_relation  subj_found={subj_rec is not None}  obj_found={obj_rec is not None}")
        if subj_rec is None or obj_rec is None:
            print("[KG] upsert_relation  FAILED — one or both nodes missing in Neo4j")
            return False

        a_eid = subj_rec["eid"]
        b_eid = obj_rec["eid"]

        # Duplicate check by element IDs
        dup = s.run(
            f"MATCH (a:Entity)-[r:`{relation}`]->(b:Entity) "
            "WHERE elementId(a) = $a_eid AND elementId(b) = $b_eid "
            "RETURN r LIMIT 1",
            a_eid=a_eid,
            b_eid=b_eid,
        ).single()
        if dup:
            print("[KG] upsert_relation  SKIP (duplicate)")
            return False

        # Create edge using element IDs — avoids name-mismatch if node was found via alias
        result = s.run(
            "MATCH (a:Entity), (b:Entity) "
            "WHERE elementId(a) = $a_eid AND elementId(b) = $b_eid "
            f"CREATE (a)-[r:`{relation}` {{"
            "  relation_type: $rel, "
            "  period: $period, "
            "  source_citation: $source, "
            "  confidence: 1.0"
            "}]->(b) "
            "RETURN r",
            a_eid=a_eid,
            b_eid=b_eid,
            rel=relation,
            period=period,
            source=source_sentence,
        )
        created = result.single() is not None
        print(f"[KG] upsert_relation  {'CREATED' if created else 'FAILED (MATCH returned no rows)'}")
        return created


def save_pipeline_result(
    sentence: str,
    ner_tags: list,
    triples: list[dict],
) -> dict:
    """Persist all NER entities and validated triples for one sentence.

    Args:
        sentence:  Raw Sinhala sentence (used as source_citation on edges).
        ner_tags:  List of NERTag objects from ner_pipeline.run_ner().
        triples:   Validated triple dicts from relation_extractor.extract_relations().

    Returns:
        {"nodes_processed": int, "edges_created": int}
    """
    nodes_processed = 0
    edges_created   = 0

    print(f"[KG] save_pipeline_result  ner_tags={len(ner_tags)}  triples={len(triples)}")

    for tag in ner_tags:
        node_label = _LABEL_MAP.get(tag.label)
        if node_label is None:
            continue                          # DATE_ERA — never a KG node
        canonical = _canonical_entity(tag.entity)
        aliases   = kg_aliases.get_aliases_for(canonical)
        upsert_entity(canonical, node_label, aliases)
        nodes_processed += 1

    for triple in triples:
        subj   = triple.get("subject",  "")
        rel    = triple.get("relation", "")
        obj    = triple.get("object",   "")
        period = triple.get("period",   "")
        print(f"[KG]   triple  subj={subj!r}  rel={rel!r}  obj={obj!r}  period={period!r}")
        if subj and rel and obj:
            created = upsert_relation(subj, rel, obj, period, sentence)
            if created:
                edges_created += 1
        else:
            print("[KG]   triple SKIPPED — missing subj/rel/obj")

    print(f"[KG] save_pipeline_result  done  nodes={nodes_processed}  edges={edges_created}")
    return {"nodes_processed": nodes_processed, "edges_created": edges_created}


def delete_relation(subject: str, relation: str, obj: str) -> bool:
    """Delete a specific directed relationship between two nodes.

    Returns True if at least one edge was removed, False otherwise.
    """
    drv = _get_driver()
    if drv is None:
        return False

    relation = _safe_relation(relation)

    with drv.session() as s:
        result = s.run(
            f"MATCH (a:Entity {{name: $subj}})-[r:`{relation}`]->(b:Entity {{name: $obj}}) "
            "DELETE r "
            "RETURN count(r) AS deleted",
            subj=subject,
            obj=obj,
        )
        record = result.single()
        return bool(record and record["deleted"] > 0)


def get_kg_stats() -> dict:
    """Return node counts by label and edge counts by relation type.

    Returns:
        {
            "nodes": {"King": 5, "Place": 12, ...},
            "edges": {"BUILT": 8, "RULED": 3, ...},
        }
        or {"error": "..."} if Neo4j is not reachable.
    """
    drv = _get_driver()
    if drv is None:
        return {"error": "Neo4j not connected"}

    with drv.session() as s:
        node_rows = s.run(
            "MATCH (n:Entity) "
            "WITH [x IN labels(n) WHERE x <> 'Entity'][0] AS lbl, count(n) AS cnt "
            "RETURN lbl, cnt ORDER BY cnt DESC"
        )
        nodes: dict[str, int] = {
            r["lbl"]: r["cnt"] for r in node_rows if r["lbl"]
        }

        edge_rows = s.run(
            "MATCH ()-[r]->() "
            "RETURN type(r) AS rel_type, count(r) AS cnt ORDER BY cnt DESC"
        )
        edges: dict[str, int] = {r["rel_type"]: r["cnt"] for r in edge_rows}

    return {"nodes": nodes, "edges": edges}


def get_all_relation_types() -> list[str]:
    """Return all distinct relation types currently in the KG, sorted alphabetically.

    Returns an empty list if Neo4j is not reachable.
    """
    drv = _get_driver()
    if drv is None:
        return []

    with drv.session() as s:
        rows = s.run(
            "MATCH ()-[r]->() "
            "RETURN DISTINCT type(r) AS rel_type ORDER BY rel_type"
        )
        return [r["rel_type"] for r in rows]


def get_also_known_as_edges() -> list[dict] | None:
    """Return every ALSO_KNOWN_AS triple live from Neo4j.

    Used by king_name_db.py to build its king-name index from the current
    graph instead of a static export. Returns None (not []) if Neo4j is
    unreachable, so callers can tell "no ALSO_KNOWN_AS edges exist" apart
    from "couldn't ask" and fall back to the static export only in the
    latter case.
    """
    drv = _get_driver()
    if drv is None:
        return None
    with drv.session() as s:
        rows = s.run(
            "MATCH (a:Entity)-[r:ALSO_KNOWN_AS]->(b:Entity) "
            "RETURN a.name AS subject, b.name AS object"
        )
        return [
            {"subject": r["subject"], "relation": "ALSO_KNOWN_AS", "object": r["object"]}
            for r in rows
        ]


def get_facts_for_entity_cluster(seed_names: list[str]) -> list[dict] | None:
    """Return every live KG triple touching any node reachable from seed_names.

    "Reachable" means: matches one of seed_names by exact node name or by an
    entry in that node's stored aliases, OR is linked to such a node via an
    ALSO_KNOWN_AS edge (any number of hops, either direction) — the live
    equivalent of kg_fact_retriever.get_all_kg_names_for_king's transitive
    closure over the static export.

    Returns None (not []) if Neo4j is unreachable, so the caller
    (kg_fact_retriever.get_facts_for_king) can distinguish "Neo4j is down,
    fall back to the static export" from "queried successfully, this entity
    genuinely has zero facts right now" — in the second case an empty list
    is the correct, real answer and must not trigger a fallback.
    """
    drv = _get_driver()
    if drv is None:
        return None
    if not seed_names:
        return []

    with drv.session() as s:
        rows = s.run(
            "MATCH (start:Entity) "
            "WHERE start.name IN $names "
            "   OR ANY(a IN coalesce(start.aliases, []) WHERE a IN $names) "
            "WITH collect(DISTINCT start) AS starts "
            "UNWIND starts AS s0 "
            "MATCH (s0)-[:ALSO_KNOWN_AS*0..10]-(c:Entity) "
            "WITH collect(DISTINCT c) AS clusterNodes "
            "UNWIND clusterNodes AS c "
            "MATCH (c)-[r]-(o:Entity) "
            "RETURN DISTINCT "
            "  CASE WHEN startNode(r) = c THEN c.name ELSE o.name END AS subject, "
            "  type(r) AS relation, "
            "  CASE WHEN startNode(r) = c THEN o.name ELSE c.name END AS object, "
            "  r.period AS period",
            names=seed_names,
        )
        return [dict(r) for r in rows]


def get_all_triples(limit: int = 500) -> list[dict]:
    """Return up to `limit` triples from the KG.

    Each entry has keys:
        subject, subject_label, relation, object, object_label,
        period, source
    """
    drv = _get_driver()
    if drv is None:
        return []

    with drv.session() as s:
        rows = s.run(
            "MATCH (a:Entity)-[r]->(b:Entity) "
            "RETURN "
            "  a.name AS subject, "
            "  [x IN labels(a) WHERE x <> 'Entity'][0] AS subject_label, "
            "  type(r) AS relation, "
            "  b.name AS object, "
            "  [x IN labels(b) WHERE x <> 'Entity'][0] AS object_label, "
            "  r.period AS period, "
            "  r.source_citation AS source "
            "LIMIT $lim",
            lim=limit,
        )
        return [dict(r) for r in rows]


def get_node_detail(name: str) -> dict | None:
    """Return full details for one node, including all edges.

    Returns:
        {
            "name": str,
            "label": str,
            "aliases": list[str],
            "outgoing": [{"relation": str, "target": str}, ...],
            "incoming": [{"relation": str, "source": str}, ...],
        }
        or None if no node with that name exists.
    """
    drv = _get_driver()
    if drv is None:
        return None

    with drv.session() as s:
        node_row = s.run(
            "MATCH (n:Entity) WHERE n.name = $name "
            "RETURN n.name AS name, "
            "  [x IN labels(n) WHERE x <> 'Entity'][0] AS label, "
            "  coalesce(n.aliases, []) AS aliases "
            "LIMIT 1",
            name=name,
        ).single()
        if not node_row:
            return None

        out_rows = s.run(
            "MATCH (n:Entity)-[r]->(m:Entity) WHERE n.name = $name "
            "RETURN type(r) AS relation, m.name AS target",
            name=name,
        )
        inc_rows = s.run(
            "MATCH (p:Entity)-[r]->(n:Entity) WHERE n.name = $name "
            "RETURN type(r) AS relation, p.name AS source",
            name=name,
        )

        return {
            "name":     node_row["name"],
            "label":    node_row["label"],
            "aliases":  list(node_row["aliases"] or []),
            "outgoing": [{"relation": r["relation"], "target": r["target"]} for r in out_rows],
            "incoming": [{"relation": r["relation"], "source": r["source"]} for r in inc_rows],
        }


def get_top_connected(n: int = 10) -> list[dict]:
    """Return the top n nodes by total degree (in + out edges).

    Returns:
        [{"name": str, "label": str, "degree": int}, ...]
    """
    drv = _get_driver()
    if drv is None:
        return []

    with drv.session() as s:
        rows = s.run(
            "MATCH (n:Entity) "
            "OPTIONAL MATCH (n)-[r]-() "
            "WITH n, count(r) AS degree "
            "ORDER BY degree DESC LIMIT $n "
            "RETURN n.name AS name, "
            "  [x IN labels(n) WHERE x <> 'Entity'][0] AS label, "
            "  degree",
            n=n,
        )
        return [dict(r) for r in rows]


def merge_duplicate_node(from_name: str, to_name: str) -> dict:
    """Move all relations from a duplicate node into the canonical node, then delete the duplicate.

    Handles both outgoing and incoming edges. Skips edges that already exist
    on the canonical node (duplicate check). Safe to run multiple times.

    Returns:
        {"migrated": int, "deleted": bool}
        or {"migrated": 0, "deleted": False, "error": str} on failure.
    """
    drv = _get_driver()
    if drv is None:
        return {"migrated": 0, "deleted": False, "error": "Neo4j not connected"}

    with drv.session() as s:
        from_rec = s.run(_CQL_EID_BY_NAME, name=from_name).single()
        to_rec   = s.run(_CQL_EID_BY_NAME, name=to_name).single()

        if not from_rec:
            return {"migrated": 0, "deleted": False, "error": f"Node not found: {from_name!r}"}
        if not to_rec:
            return {"migrated": 0, "deleted": False, "error": f"Node not found: {to_name!r}"}

        from_eid = from_rec["eid"]
        to_eid   = to_rec["eid"]

        # Materialise all relations before running any writes (avoids open-cursor conflicts)
        out_rels = s.run(
            "MATCH (a:Entity)-[r]->(b:Entity) WHERE elementId(a) = $eid "
            "RETURN type(r) AS rel_type, elementId(b) AS b_eid, properties(r) AS props",
            eid=from_eid,
        ).data()

        in_rels = s.run(
            "MATCH (a:Entity)-[r]->(b:Entity) WHERE elementId(b) = $eid "
            "RETURN type(r) AS rel_type, elementId(a) AS a_eid, properties(r) AS props",
            eid=from_eid,
        ).data()

        migrated = 0

        for row in out_rels:
            safe_type = "".join(
                c for c in row["rel_type"] if c.isalnum() or c == "_"
            )
            if not safe_type:
                continue
            b_eid = row["b_eid"]
            if b_eid == to_eid:
                continue  # self-loop after merge — skip
            dup = s.run(
                f"MATCH (a:Entity)-[r:`{safe_type}`]->(b:Entity) "
                "WHERE elementId(a) = $a AND elementId(b) = $b RETURN r LIMIT 1",
                a=to_eid, b=b_eid,
            ).single()
            if not dup:
                s.run(
                    "MATCH (a:Entity), (b:Entity) "
                    "WHERE elementId(a) = $a AND elementId(b) = $b "
                    f"CREATE (a)-[r:`{safe_type}`]->(b) SET r = $props",
                    a=to_eid, b=b_eid, props=row["props"],
                )
                migrated += 1

        for row in in_rels:
            safe_type = "".join(
                c for c in row["rel_type"] if c.isalnum() or c == "_"
            )
            if not safe_type:
                continue
            a_eid = row["a_eid"]
            if a_eid == to_eid:
                continue  # self-loop after merge — skip
            dup = s.run(
                f"MATCH (a:Entity)-[r:`{safe_type}`]->(b:Entity) "
                "WHERE elementId(a) = $a AND elementId(b) = $b RETURN r LIMIT 1",
                a=a_eid, b=to_eid,
            ).single()
            if not dup:
                s.run(
                    "MATCH (a:Entity), (b:Entity) "
                    "WHERE elementId(a) = $a AND elementId(b) = $b "
                    f"CREATE (a)-[r:`{safe_type}`]->(b) SET r = $props",
                    a=a_eid, b=to_eid, props=row["props"],
                )
                migrated += 1

        # Add from_name as an alias on the canonical node so the name is preserved
        s.run(
            "MATCH (n:Entity) WHERE elementId(n) = $eid "
            "SET n.aliases = "
            "  [a IN coalesce(n.aliases, []) WHERE a IS NOT NULL] + "
            "  [a IN [$alias] WHERE NOT a IN coalesce(n.aliases, [])]",
            eid=to_eid,
            alias=from_name,
        )

        s.run(
            "MATCH (n:Entity) WHERE elementId(n) = $eid DETACH DELETE n",
            eid=from_eid,
        )

    return {"migrated": migrated, "deleted": True}


def get_all_node_names() -> list[dict]:
    """Return all entity nodes sorted alphabetically.

    Returns:
        [{"name": str, "label": str}, ...]
        or [] if Neo4j is not reachable.
    """
    drv = _get_driver()
    if drv is None:
        return []

    with drv.session() as s:
        rows = s.run(
            "MATCH (n:Entity) "
            "RETURN n.name AS name, "
            "  [x IN labels(n) WHERE x <> 'Entity'][0] AS label "
            "ORDER BY n.name"
        )
        return [{"name": r["name"], "label": r["label"]} for r in rows]
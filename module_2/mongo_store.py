"""
mongo_store.py - MongoDB storage for pipeline run history.

Stores each pipeline execution: input sentence, NER tags, raw LLM
response, validated triples, and whether the run was saved to the KG.
Connection is lazy - importing this module never raises even if MongoDB
is not running.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

from dotenv import load_dotenv

load_dotenv()

MONGO_URI:        str = os.environ.get("MONGO_URI",  "mongodb://localhost:27017")
MONGO_DB:         str = os.environ.get("MONGO_DB",   "sinhala_kg")
COLLECTION:       str = "pipeline_runs"
ESSAY_COLLECTION: str = "essay_check_runs"

_client = None


def _get_db_collection(name: str):
    """Return a MongoDB collection by name, or None if the connection fails."""
    global _client
    if _client is None:
        try:
            from pymongo import MongoClient
            cl = MongoClient(MONGO_URI, serverSelectionTimeoutMS=3000)
            cl.admin.command("ping")   # fail fast if unreachable
            _client = cl
        except Exception as exc:
            print(f"[Mongo] connection failed ({MONGO_URI}): {exc}")
            return None
    try:
        return _client[MONGO_DB][name]
    except Exception:
        return None


def _get_collection():
    """Return the pipeline-runs collection, or None if the connection fails."""
    return _get_db_collection(COLLECTION)


def _get_essay_collection():
    """Return the essay-check-runs collection, or None if the connection fails."""
    return _get_db_collection(ESSAY_COLLECTION)


# Write operations

def save_run(
    sentence: str,
    ner_tags: list,
    llm_provider: str,
    llm_model: str,
    llm_raw: str,
    llm_parsed: list,
    validated_triples: list,
) -> str | None:
    """Persist one pipeline run.

    Args:
        sentence:           Raw Sinhala input sentence.
        ner_tags:           List of NERTag objects from ner_pipeline.
        llm_provider:       Provider name string (e.g. "Google Gemini").
        llm_model:          Model identifier string.
        llm_raw:            Raw text response from the LLM.
        llm_parsed:         Pre-validation triples parsed from LLM output.
        validated_triples:  Final ontology-validated triples.

    Returns:
        Inserted document _id as a string, or None on error.
    """
    col = _get_collection()
    if col is None:
        return None
    try:
        doc = {
            "timestamp":           datetime.now(timezone.utc),
            "input_text":          sentence,
            "ner_tags":            [
                {
                    "entity": t.entity,
                    "label":  t.label,
                    "start":  t.start,
                    "end":    t.end,
                }
                for t in ner_tags
            ],
            "ner_entity_count":    len(ner_tags),
            "llm_provider":        llm_provider,
            "llm_model":           llm_model,
            "llm_raw_response":    llm_raw,
            "llm_parsed_triples":  llm_parsed,
            "validated_triples":   validated_triples,
            "triple_count":        len(validated_triples),
            "kg_saved":            False,
        }
        result = col.insert_one(doc)
        return str(result.inserted_id)
    except Exception as exc:
        print(f"[Mongo] save_run failed: {exc}")
        return None


def mark_kg_saved(run_id: str) -> None:
    """Set kg_saved=True on the given run document."""
    col = _get_collection()
    if col is None:
        return
    try:
        from bson import ObjectId
        col.update_one({"_id": ObjectId(run_id)}, {"$set": {"kg_saved": True}})
    except Exception as exc:
        print(f"[Mongo] mark_kg_saved failed: {exc}")


#  Read operations

def get_recent_runs(limit: int = 100) -> list[dict]:
    """Return the most recent pipeline runs, newest first.

    Returns an empty list if MongoDB is unreachable.
    Each document has _id converted to a string.
    """
    col = _get_collection()
    if col is None:
        return []
    try:
        docs = []
        for doc in col.find({}, sort=[("timestamp", -1)]).limit(limit):
            doc["_id"] = str(doc["_id"])
            ts = doc.get("timestamp")
            doc["timestamp"] = ts.isoformat() if ts else ""
            docs.append(doc)
        return docs
    except Exception as exc:
        print(f"[Mongo] get_recent_runs failed: {exc}")
        return []


def get_run_by_id(run_id: str) -> dict | None:
    """Fetch one run document by its string _id. Returns None on error."""
    col = _get_collection()
    if col is None:
        return None
    try:
        from bson import ObjectId
        doc = col.find_one({"_id": ObjectId(run_id)})
        if doc:
            doc["_id"] = str(doc["_id"])
            ts = doc.get("timestamp")
            doc["timestamp"] = ts.isoformat() if ts else ""
        return doc
    except Exception as exc:
        print(f"[Mongo] get_run_by_id failed: {exc}")
        return None


def get_run_stats() -> dict:
    """Aggregate stats across all saved runs.

    Returns:
        {
            "total_runs": int,
            "kg_saved_runs": int,
            "total_entities": int,
            "total_triples": int,
        }
        or {"error": "..."} if MongoDB is unreachable.
    """
    col = _get_collection()
    if col is None:
        return {"error": "MongoDB not connected"}
    try:
        pipeline = [
            {
                "$group": {
                    "_id":             None,
                    "total_runs":      {"$sum": 1},
                    "kg_saved_runs":   {"$sum": {"$cond": ["$kg_saved", 1, 0]}},
                    "total_entities":  {"$sum": "$ner_entity_count"},
                    "total_triples":   {"$sum": "$triple_count"},
                }
            }
        ]
        result = list(col.aggregate(pipeline))
        if not result:
            return {"total_runs": 0, "kg_saved_runs": 0,
                    "total_entities": 0, "total_triples": 0}
        r = result[0]
        return {
            "total_runs":     r.get("total_runs",     0),
            "kg_saved_runs":  r.get("kg_saved_runs",  0),
            "total_entities": r.get("total_entities", 0),
            "total_triples":  r.get("total_triples",  0),
        }
    except Exception as exc:
        print(f"[Mongo] get_run_stats failed: {exc}")
        return {"error": str(exc)}


# Essay Accuracy Checker - write operations

def _claim_to_dict(c: Any) -> dict:
    return {
        "claim_sinhala":       c.claim_sinhala,
        "claim_type":          c.claim_type,
        "verdict":             c.verdict,
        "unverifiable_reason": c.unverifiable_reason,
        "matched_kg_fact":     c.matched_kg_fact,
        "explanation":         c.explanation,
        "teacher_feedback":    c.teacher_feedback,
        "batch_number":        c.batch_number,
    }


def save_essay_check_run(
    essay_text: str,
    result: Any,
    source: str = "streamlit_ui",
    caller: str | None = None,
    submitted_by: str | None = None,
) -> str | None:
    """Persist one essay accuracy check - the raw essay text plus the full
    AccuracyResult: every claim, every batch's exact Claude input/output, and
    all computed scores. Lets a user reopen a past check later and see
    everything the Essay Checker page showed at the time, unchanged.

    Args:
        essay_text:   The raw student essay text that was checked.
        result:       An essay_accuracy_checker.AccuracyResult instance.
        source:       "streamlit_ui" (default) or "api" - which front door
                      this check came through.
        caller:       Which authenticated API client sent this (resolved
                      from the API key in api_server.py) - None for the
                      Streamlit UI, which has no separate caller identity.
        submitted_by: Optional free-text identifier the caller supplied
                      (e.g. a student ID or essay ID from Module 3) for
                      their own traceability - not validated, just stored.

    Returns:
        Inserted document _id as a string, or None on error.
    """
    col = _get_essay_collection()
    if col is None:
        return None
    try:
        doc = {
            "timestamp":            datetime.now(timezone.utc),
            "source":               source,
            "caller":               caller,
            "submitted_by":         submitted_by,
            "essay_text":           essay_text,
            "essay_subject":        result.essay_subject,
            "all_kings_found":      result.all_kings_found,
            "accuracy_score":       result.accuracy_score,
            "coverage_ratio":       result.coverage_ratio,
            "confidence_level":     result.confidence_level,
            "coverage_warning":     result.coverage_warning,
            "total_claims":         result.total_claims,
            "total_factual_claims": result.total_factual_claims,
            "editorial_claims":     result.editorial_claims,
            "correct_claims":       result.correct_claims,
            "incorrect_claims":     result.incorrect_claims,
            "unverifiable_claims":  result.unverifiable_claims,
            "kg_gap_claims":        result.kg_gap_claims,
            "not_factual_claims":   result.not_factual_claims,
            "kg_facts_used":        result.kg_facts_used,
            "batch_count":          result.batch_count,
            "essay_sentence_count": result.essay_sentence_count,
            "kg_facts_text":        result.kg_facts_text,
            "combined_teacher_feedback": result.combined_teacher_feedback,
            "all_claim_results": [_claim_to_dict(c) for c in result.all_claim_results],
            "batch_logs": [
                {
                    "batch_number":  log.batch_number,
                    "total_batches": log.total_batches,
                    "sentences":     log.sentences,
                    "system_prompt": log.system_prompt,
                    "user_message":  log.user_message,
                    "raw_response":  log.raw_response,
                    "parse_retried": log.parse_retried,
                    "claim_results": [_claim_to_dict(c) for c in log.claim_results],
                }
                for log in result.batch_logs
            ],
        }
        res = col.insert_one(doc)
        return str(res.inserted_id)
    except Exception as exc:
        print(f"[Mongo] save_essay_check_run failed: {exc}")
        return None


# Essay Accuracy Checker - read operations

def get_recent_essay_runs(limit: int = 100) -> list[dict]:
    """Return the most recent essay-check runs, newest first.

    Returns an empty list if MongoDB is unreachable.
    Each document has _id converted to a string.
    """
    col = _get_essay_collection()
    if col is None:
        return []
    try:
        docs = []
        for doc in col.find({}, sort=[("timestamp", -1)]).limit(limit):
            doc["_id"] = str(doc["_id"])
            ts = doc.get("timestamp")
            doc["timestamp"] = ts.isoformat() if ts else ""
            docs.append(doc)
        return docs
    except Exception as exc:
        print(f"[Mongo] get_recent_essay_runs failed: {exc}")
        return []


def get_essay_run_by_id(run_id: str) -> dict | None:
    """Fetch one essay-check run document by its string _id. Returns None on error."""
    col = _get_essay_collection()
    if col is None:
        return None
    try:
        from bson import ObjectId
        doc = col.find_one({"_id": ObjectId(run_id)})
        if doc:
            doc["_id"] = str(doc["_id"])
            ts = doc.get("timestamp")
            doc["timestamp"] = ts.isoformat() if ts else ""
        return doc
    except Exception as exc:
        print(f"[Mongo] get_essay_run_by_id failed: {exc}")
        return None


def get_essay_run_stats() -> dict:
    """Aggregate stats across all saved essay-check runs.

    Returns:
        {"total_runs": int, "avg_accuracy_score": float | None, "total_claims": int}
        or {"error": "..."} if MongoDB is unreachable.
    """
    col = _get_essay_collection()
    if col is None:
        return {"error": "MongoDB not connected"}
    try:
        pipeline = [
            {
                "$group": {
                    "_id":                None,
                    "total_runs":         {"$sum": 1},
                    "avg_accuracy_score": {"$avg": "$accuracy_score"},
                    "total_claims":       {"$sum": "$total_claims"},
                }
            }
        ]
        result = list(col.aggregate(pipeline))
        if not result:
            return {"total_runs": 0, "avg_accuracy_score": None, "total_claims": 0}
        r = result[0]
        return {
            "total_runs":         r.get("total_runs", 0),
            "avg_accuracy_score": r.get("avg_accuracy_score"),
            "total_claims":       r.get("total_claims", 0),
        }
    except Exception as exc:
        print(f"[Mongo] get_essay_run_stats failed: {exc}")
        return {"error": str(exc)}

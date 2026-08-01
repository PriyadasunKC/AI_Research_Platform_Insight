"""
utils/mongo_store.py - MongoDB storage for Module 1's combined D1-D4 result.

Uses the SAME MongoDB database Module 2 uses (MONGO_URI/MONGO_DB in
config.py - see module_2/mongo_store.py for the sibling implementation),
in a dedicated `module1_combined_results` collection. Module 2's own
`essay_check_runs` collection is left untouched; the two modules save
different-shaped documents so they get their own collections rather than
being forced into one schema.

Connection is lazy - importing this module never raises even if MongoDB
is not reachable, and every function degrades to returning None/[] rather
than raising, matching module_2/mongo_store.py's behavior.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from typing import Any, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import MONGO_DB, MONGO_URI

COLLECTION = "module1_combined_results"

_client = None


def _get_collection():
    global _client
    if _client is None:
        try:
            from pymongo import MongoClient
            cl = MongoClient(MONGO_URI, serverSelectionTimeoutMS=3000)
            cl.admin.command("ping")  # fail fast if unreachable
            _client = cl
        except Exception as exc:
            print(f"[Mongo] connection failed ({MONGO_URI}): {exc}")
            return None
    try:
        return _client[MONGO_DB][COLLECTION]
    except Exception:
        return None


def save_combined_result(
    essay_id: str,
    essay_text: str,
    scores: dict,
    notes: dict,
    weakest: str,
    average_score: float,
    summary_si: str,
    module2_result: dict,
    module3_export: dict,
) -> Optional[str]:
    """Persist one combined D1-D4 scoring run.

    Args:
        essay_id:        The essay_id this run was scored under.
        essay_text:       The raw essay text that was scored.
        scores:          {"D1":.., "D2":.., "D3":.., "D4":..} (D1 already
                          the converted 1-5 value, or None).
        notes:           Full structured notes dict, incl. D1_note.
        weakest:          The weakest dimension code (e.g. "D4").
        average_score:    The averaged 1-5 score across available dimensions.
        summary_si:       Sinhala summary string.
        module2_result:   {"ok": bool, "error": str} or {"ok": True, "raw": {...}}
                          - kept for traceability of what Module 2 actually
                          returned (or why it didn't) at the time.
        module3_export:   The json_download_url/txt_download_url/api_url
                          dict already built for the HTTP response.

    Returns:
        Inserted document _id as a string, or None if MongoDB is unreachable.
    """
    col = _get_collection()
    if col is None:
        return None
    try:
        doc = {
            "timestamp":      datetime.now(timezone.utc),
            "essay_id":       essay_id,
            "essay_text":     essay_text,
            "scores":         scores,
            "notes":          notes,
            "weakest":        weakest,
            "average_score":  average_score,
            "summary_si":     summary_si,
            "module2_ok":     module2_result.get("ok"),
            "module2_error":  module2_result.get("error"),
            "module3_export": module3_export,
        }
        result = col.insert_one(doc)
        return str(result.inserted_id)
    except Exception as exc:
        print(f"[Mongo] save_combined_result failed: {exc}")
        return None


def get_combined_result(essay_id: str) -> Optional[dict[str, Any]]:
    """Fetch the most recent combined result for one essay_id.

    Returns None if MongoDB is unreachable or nothing was found.
    """
    col = _get_collection()
    if col is None:
        return None
    try:
        doc = col.find_one({"essay_id": essay_id}, sort=[("timestamp", -1)])
        if doc:
            doc["_id"] = str(doc["_id"])
            ts = doc.get("timestamp")
            doc["timestamp"] = ts.isoformat() if ts else ""
        return doc
    except Exception as exc:
        print(f"[Mongo] get_combined_result failed: {exc}")
        return None


def get_recent_combined_results(limit: int = 100) -> list[dict[str, Any]]:
    """Return the most recent combined-scoring runs, newest first.

    Returns an empty list if MongoDB is unreachable.
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
        print(f"[Mongo] get_recent_combined_results failed: {exc}")
        return []

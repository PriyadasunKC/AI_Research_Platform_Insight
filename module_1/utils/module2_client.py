"""
utils/module2_client.py
========================
Server-side HTTP client Module 1 uses to call Module 2's external API
(AI_Research_Platform_Insight/module_2, run separately via
`uvicorn api_server:app --port 8010`) and fold its historical-accuracy
result into Module 1's own /score response as the D1 dimension.

Module 2's accuracy_score is a 0-100 float (Factual Precision). Module 1's
D1 slot requires an integer 1-5 to match how D2/D3/D4 are scored (see
models/rule_based_scorer.py: `if not (1 <= d1_score <= 5): d1_score = None`).
accuracy_to_d1() converts between the two using threshold bands (matching
the rubric-style, bucketed nature of how D2/D3/D4 are already scored,
rather than a smooth linear interpolation).
"""

from __future__ import annotations

import os
import sys
from typing import Optional

import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import MODULE2_API_KEY, MODULE2_BASE_URL, MODULE2_TIMEOUT_SECONDS

CHECK_ENDPOINT = f"{MODULE2_BASE_URL}/api/v1/essay/check"


def accuracy_to_d1(accuracy_score: Optional[float]) -> Optional[int]:
    """Convert Module 2's 0-100 accuracy_score into a 1-5 D1 score.

    None in, None out - Module 2 returns accuracy_score=None when it had
    zero verifiable factual claims to judge (INSUFFICIENT_KG), and D1
    should likewise be excluded from Module 1's average_score rather than
    defaulting to a specific band, matching how D1=None is already treated
    everywhere else in Module 1 (models/rule_based_scorer.py's
    `valid = [v for v in scores.values() if v is not None]`).

    Bands: 90-100 -> 5, 75-89 -> 4, 60-74 -> 3, 40-59 -> 2, 0-39 -> 1.
    """
    if accuracy_score is None:
        return None
    if accuracy_score >= 90:
        return 5
    if accuracy_score >= 75:
        return 4
    if accuracy_score >= 60:
        return 3
    if accuracy_score >= 40:
        return 2
    return 1


def check_historical_accuracy(essay_text: str, submitted_by: Optional[str] = None) -> dict:
    """Call Module 2's /api/v1/essay/check and return a result dict.

    Always returns a dict - never raises. On any failure (Module 2 not
    running, network error, timeout, bad response), returns
    {"ok": False, "error": "..."} so app.py can still return D2/D3/D4 with
    D1=None rather than failing the whole /score request just because
    Module 2 happened to be unreachable.

    On success: {"ok": True, "raw": <Module 2's full JSON response>}.
    """
    if not essay_text or not essay_text.strip():
        return {"ok": False, "error": "essay_text is empty."}

    try:
        response = requests.post(
            CHECK_ENDPOINT,
            json={"essay_text": essay_text, "submitted_by": submitted_by},
            headers={"X-API-Key": MODULE2_API_KEY},
            timeout=MODULE2_TIMEOUT_SECONDS,
        )
    except requests.exceptions.Timeout:
        return {"ok": False, "error": f"Module 2 did not respond within {MODULE2_TIMEOUT_SECONDS}s."}
    except requests.exceptions.ConnectionError as exc:
        return {"ok": False, "error": f"Could not connect to Module 2 at {MODULE2_BASE_URL}: {exc}"}
    except requests.exceptions.RequestException as exc:
        return {"ok": False, "error": f"Module 2 request failed: {exc}"}

    if response.status_code != 200:
        detail = response.text[:500]
        return {"ok": False, "error": f"Module 2 returned HTTP {response.status_code}: {detail}"}

    try:
        return {"ok": True, "raw": response.json()}
    except ValueError as exc:
        return {"ok": False, "error": f"Module 2 response was not valid JSON: {exc}"}


def build_d1_note(module2_call: dict) -> dict:
    """Build a D1_note block shaped like the D2_note/D3_note/D4_note blocks
    in models/rule_based_scorer.py, so utils/export_module3.py's existing
    _rename_note_keys() logic handles it identically - no changes needed
    there. See rule_based_scorer.py's _d2_what_wrong/_d2_how_to_improve for
    the sibling pattern this follows.

    On success also includes a "claims" list - every claim Module 2 graded,
    with its verdict, explanation, and (for INCORRECT claims) the teacher-
    style corrective feedback text - so the combined payload sent to
    Module 3 carries the actual per-claim evidence of what was correct/
    incorrect, not just the aggregate correct_claims/incorrect_claims
    counts.
    """
    if not module2_call.get("ok"):
        error = module2_call.get("error", "Unknown error.")
        return {
            "score": None,
            "what_wrong": f"Could not verify historical accuracy - {error}",
            "how_to_improve": "Ensure Module 2 (the Knowledge Graph accuracy checker) is running and reachable, then re-submit.",
            "short_note_si": "ඓතිහාසික නිරවද්‍යතාව පරීක්ෂා කළ නොහැකි විය - Module 2 සමඟ සම්බන්ධතාවයක් නොමැත.",
        }

    r = module2_call["raw"]
    accuracy = r.get("accuracy_score")
    d1_score = accuracy_to_d1(accuracy)
    incorrect = r.get("incorrect_claims", 0)
    correct = r.get("correct_claims", 0)
    kg_gap = r.get("kg_gap_claims", 0)
    coverage_warning = r.get("coverage_warning", False)

    if accuracy is None:
        what_wrong = "No factual claims in this essay could be verified against the Knowledge Graph."
        how_to_improve = "Include more specific, checkable historical facts (dates, relationships, events) about the king(s) discussed."
    elif incorrect > 0:
        what_wrong = f"{incorrect} claim(s) contradicted the Knowledge Graph out of {correct + incorrect} checkable claims."
        how_to_improve = "Review the incorrect claims below and correct them against the historical record."
    else:
        what_wrong = "All checkable factual claims matched the Knowledge Graph."
        how_to_improve = "Maintain this level of factual accuracy."

    short_note_si = (
        f"ඓතිහාසික නිරවද්‍යතාව: {accuracy}% ({correct} නිවැරදි, {incorrect} වැරදි, "
        f"{kg_gap} KG හි නොමැත)."
        if accuracy is not None
        else "ඓතිහාසික නිරවද්‍යතාව පරීක්ෂා කිරීමට තරම් සත්‍ය හෙළිදරව් කිරීම් රචනාවේ නොමැත."
    )
    if coverage_warning:
        short_note_si += " (අවවාදයයි: Knowledge Graph ආවරණය අඩුය - මෙම ලකුණ සීමිත සාක්ෂි මතය.)"

    return {
        "score": d1_score,
        "accuracy_percent": accuracy,
        "confidence_level": r.get("confidence_level"),
        "coverage_ratio": r.get("coverage_ratio"),
        "coverage_warning": coverage_warning,
        "correct_claims": correct,
        "incorrect_claims": incorrect,
        "kg_gap_claims": kg_gap,
        "what_wrong": what_wrong,
        "how_to_improve": how_to_improve,
        "short_note_si": short_note_si,
        # Every claim's individual teacher_feedback (1-sentence affirmations
        # for CORRECT, 2-3 sentence corrections for INCORRECT) already
        # joined into one block by Module 2 (see essay_accuracy_checker.py's
        # aggregate_results) - forwarded as-is rather than re-joining the
        # per-claim list below, so this can't drift from Module 2's own
        # combined_teacher_feedback field if that joining logic ever changes.
        "combined_teacher_feedback": r.get("combined_teacher_feedback", ""),
        # Per-claim detail - what specifically was correct/incorrect/
        # unverifiable and why, plus each claim's own teacher_feedback.
        # Module 2 computes all of this already (see essay_accuracy_checker.py);
        # this just forwards it into the combined payload instead of only
        # the aggregate counts above, so Module 3 gets the actual evidence,
        # not just a summary.
        "claims": [
            {
                "claim_sinhala": c.get("claim_sinhala"),
                "claim_type": c.get("claim_type"),
                "verdict": c.get("verdict"),
                "unverifiable_reason": c.get("unverifiable_reason"),
                "matched_kg_fact": c.get("matched_kg_fact"),
                "explanation": c.get("explanation"),
                "teacher_feedback": c.get("teacher_feedback"),
            }
            for c in r.get("claims", [])
        ],
    }
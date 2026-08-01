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
    """Build the D1 note for the COMBINED (Module 1 + Module 2) output only.

    Deliberately minimal — just two fields, on purpose:
        {"combined_teacher_feedback": "...", "short_note_si": "..."}

    Module 2's own full result (accuracy_score, confidence_level,
    coverage_ratio, correct/incorrect/kg_gap counts, the per-claim "claims"
    array, etc.) is NOT duplicated here — that full detail already exists
    in Module 2's own API response / the standalone Module 2 page's
    download (see module_2/api_server.py's EssayCheckResponse). This note
    is only what the combined Module 1+2 payload shows for D1; the numeric
    D1 score itself lives in the combined payload's top-level "scores"
    dict (via accuracy_to_d1(), computed in app.py), not in this note.
    """
    if not module2_call.get("ok"):
        error = module2_call.get("error", "Unknown error.")
        return {
            "combined_teacher_feedback": "",
            "short_note_si": f"ඓතිහාසික නිරවද්‍යතාව පරීක්ෂා කළ නොහැකි විය - Module 2 සමඟ සම්බන්ධතාවයක් නොමැත. ({error})",
        }

    r = module2_call["raw"]
    accuracy = r.get("accuracy_score")
    incorrect = r.get("incorrect_claims", 0)
    correct = r.get("correct_claims", 0)
    kg_gap = r.get("kg_gap_claims", 0)
    coverage_warning = r.get("coverage_warning", False)

    short_note_si = (
        f"ඓතිහාසික නිරවද්‍යතාව: {accuracy}% ({correct} නිවැරදි, {incorrect} වැරදි, "
        f"{kg_gap} KG හි නොමැත)."
        if accuracy is not None
        else "ඓතිහාසික නිරවද්‍යතාව පරීක්ෂා කිරීමට තරම් සත්‍ය හෙළිදරව් කිරීම් රචනාවේ නොමැත."
    )
    if coverage_warning:
        short_note_si += " (අවවාදයයි: Knowledge Graph ආවරණය අඩුය - මෙම ලකුණ සීමිත සාක්ෂි මතය.)"

    return {
        "combined_teacher_feedback": r.get("combined_teacher_feedback", ""),
        "short_note_si": short_note_si,
    }
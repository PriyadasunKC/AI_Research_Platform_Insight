"""
Dimension 2 - Coherence & Idea Flow

Scoring method (rule-based baseline):
  Counts how many distinct discourse marker TYPES appear in the essay.
  5 types defined -> score 1–5 maps directly to types found.

  Marker types: cause_effect, contrast, addition, sequence, example

  Types found | Score
  ──────────────────
       4 +    |   5
       3      |   4
       2      |   3
       1      |   2
       0      |   1

Returns a standardised result dict understood by rule_based_scorer.py.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from features.feature_extractor import extract_features
from config import DISCOURSE_MARKERS

# All possible marker type names (used to compute "missing")
ALL_MARKER_TYPES = list(DISCOURSE_MARKERS.keys())


def score_coherence(essay_text: str) -> dict:
    """
    Parameters
    ----------
    essay_text : str
        Raw Sinhala essay.

    Returns
    -------
    dict with keys:
        score           int  1–5
        max             int  5
        dimension       str
        found_markers   dict  {type: [marker strings found]}
        missing_types   list  marker types not found
        type_count      int   how many types were found
        hint_en         str   English debug hint
        hint_si         str   Sinhala feedback to show student
    """
    features = extract_features(essay_text)

    found_markers  = features['discourse_markers']       # dict
    type_count     = features['discourse_type_count']    # 0–5
    missing_types  = [t for t in ALL_MARKER_TYPES if t not in found_markers]

    #  Score mapping (from spec) 
    if   type_count >= 4: score = 5
    elif type_count == 3: score = 4
    elif type_count == 2: score = 3
    elif type_count == 1: score = 2
    else:                 score = 1

    #  Sinhala hint (feedback for student) 
    type_name_si = {
        'cause_effect' : 'හේතු-ප්‍රතිඵල සම්බන්ධතා ("එබැවින්", "ඒ නිසා")',
        'contrast'     : 'විරෝධාභාස ("නමුත්", "එහෙත්")',
        'addition'     : 'එකතු කිරීම ("එසේම", "ඊට අමතරව")',
        'sequence'     : 'අනුක්‍රමය ("ඉන් පසු", "පළමුව")',
        'example'      : 'උදාහරණ ("උදාහරණයක් ලෙස", "එනම්")',
    }

    if score == 5:
        hint_si = "ඔබේ රචනාවේ අදහස් හොඳින් සම්බන්ධ කර ඇත. සම්බන්ධක ලෙස හොඳ ප්‍රගතියක් දැකිය හැකිය."
    else:
        missing_si = ', '.join(type_name_si[t] for t in missing_types)
        hint_si = (
            f"ඔබේ රචනාවේ අදහස් අතර සම්බන්ධය දුර්වලය. "
            f"මෙම සම්බන්ධක වර්ග යොදා ගන්න: {missing_si}."
        )

    hint_en = (
        f"Found {type_count}/5 connector types. "
        f"Missing: {missing_types}. "
        f"Found: {list(found_markers.keys())}."
    )

    return {
        'score'         : score,
        'max'           : 5,
        'dimension'     : 'D2_coherence',
        'type_count'    : type_count,
        'found_markers' : found_markers,
        'missing_types' : missing_types,
        'hint_en'       : hint_en,
        'hint_si'       : hint_si,
    }


# Self-test
if __name__ == '__main__':
    import json

    tests = {
        'No markers': "රජු ගියා. රජු ආවා. රජු ගෙදර ගියා.",
        '1 marker type': "මහින්ද හිමි ලංකාවට පැමිණිය. නමුත් රජතුමා ඒ ගැන නොදැන සිටියා.",
        '3 marker types': (
            "මහින්ද හිමි ලංකාවට පැමිණිය. "
            "එබැවින් බෞද්ධ ධර්මය ව්‍යාප්ත විය. "
            "නමුත් රජතුමාගේ සහාය නොමැතිව මෙය කළ නොහැකිව තිබිණ. "
            "ඉන් පසු මහාවිහාරය ඉදිකෙරිණ."
        ),
    }

    for label, text in tests.items():
        result = score_coherence(text)
        print(f"\n── {label} ──")
        print(f"  Score     : {result['score']}/5")
        print(f"  Type count: {result['type_count']}")
        print(f"  Found     : {list(result['found_markers'].keys())}")
        print(f"  Hint (SI) : {result['hint_si']}")

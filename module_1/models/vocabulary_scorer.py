"""
Dimension 3 - Vocabulary Richness

Scoring formula (from spec):
    raw = (MATTR × 0.35) + (AcademicDensity × 0.40) + (RepetitionScore × 0.25)
          − InformalPenalty

Each component normalised to 0–1 before weighting.
Final raw (0–1) mapped to 1–5 integer score.

Component details
MATTR             Moving Average TTR with window=50.
                  0.70+ -> perfect (1.0). Lower → proportionally lower.

AcademicDensity   % of tokens found in the academic vocab set.
                  0.15+ -> perfect (1.0).

RepetitionScore   Inverted repetition ratio.
                  More repeated words → lower score.

InformalPenalty   Subtracted from raw. Capped at 0.30.
                  informal_ratio × 2 (so 15%+ informal → max penalty).
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from features.feature_extractor import extract_features
from config import VOCAB_WEIGHTS, MATTR_PERFECT, ACADEMIC_PERFECT


def score_vocabulary(essay_text: str) -> dict:
    """
    Parameters
    ----------
    essay_text : str

    Returns
    -------
    dict with keys:
        score               int  1–5
        max                 int  5
        dimension           str
        mattr               float
        academic_density    float
        repetition_ratio    float
        informal_count      int
        repeated_words      dict   top repeated words
        academic_words      list   sample academic words found
        hint_en             str
        hint_si             str
    """
    f = extract_features(essay_text)

    mattr            = f['mattr']
    academic_density = f['academic_density']
    repetition_ratio = f['repetition_ratio']
    informal_ratio   = f['informal_ratio']
    informal_words   = f['informal_words']
    repeated_words   = f['repeated_words']
    academic_words   = f['academic_words']

    # Normalise each component to 0–1
    mattr_score      = min(mattr / MATTR_PERFECT, 1.0)
    academic_score   = min(academic_density / ACADEMIC_PERFECT, 1.0)
    # repetition: higher ratio = worse. Multiply by 3 so even small repetition shows
    repetition_score = max(0.0, 1.0 - repetition_ratio * 3.0)

    # Weighted sum
    raw = (
        mattr_score      * VOCAB_WEIGHTS['mattr']      +
        academic_score   * VOCAB_WEIGHTS['academic']   +
        repetition_score * VOCAB_WEIGHTS['repetition']
    )

    # Informal penalty (subtract, cap at 0.30) 
    informal_penalty = min(informal_ratio * 2.0, 0.30)
    raw = max(0.0, raw - informal_penalty)

    # Map 0–1 -> 1–5 
    # raw=0 -> 1,  raw=1 → 5
    score = max(1, min(5, round(raw * 4.0 + 1.0)))

    # Sinhala hints 
    issues = []
    if mattr < 0.45:
        issues.append("ඔබේ රචනාවේ වචන නැවත නැවත යෙදී ඇත")
    if academic_density < 0.05:
        issues.append("ඉතිහාස රචනාවකට ගැලපෙන උගත් / ශාස්ත්‍රීය වචන ඉතා අඩුය")
    if informal_ratio > 0.05:
        issues.append(
            f"අවිධිමත් වචන ({', '.join(informal_words[:3])}) රචනාවකට ගැලපෙන්නේ නැත"
        )
    if repeated_words:
        top3 = list(repeated_words.items())[:3]
        rep_str = ', '.join(f'"{w}" ({c}×)' for w, c in top3)
        issues.append(f"අධිකව නැවත යෙදූ වචන: {rep_str}")

    if not issues:
        hint_si = "ඔබේ වචන සම්පත හොඳ මට්ටමකය. ශාස්ත්‍රීය වචන ලෙස යෙදීම ඉහළ නංවන්න."
    else:
        hint_si = "වචන සම්පතෙහි දුර්වලතා: " + "; ".join(issues) + "."

    hint_en = (
        f"MATTR={mattr:.3f} (need ≥{MATTR_PERFECT}), "
        f"AcademicDensity={academic_density:.3f} (need ≥{ACADEMIC_PERFECT}), "
        f"RepetitionRatio={repetition_ratio:.3f}, "
        f"InformalRatio={informal_ratio:.3f}, "
        f"RawScore={raw:.3f} → {score}/5"
    )

    return {
        'score'            : score,
        'max'              : 5,
        'dimension'        : 'D3_vocabulary',
        'mattr'            : mattr,
        'academic_density' : academic_density,
        'repetition_ratio' : repetition_ratio,
        'informal_count'   : len(informal_words),
        'informal_words'   : informal_words,
        'repeated_words'   : repeated_words,
        'academic_words'   : academic_words[:10],
        'hint_en'          : hint_en,
        'hint_si'          : hint_si,
    }


# Self-test

if __name__ == '__main__':
    import json

    bad_essay = """
රජු ගියා. රජු ආවා. රජු ගෙදර ගියා. රජු ගියා. රජු ආවා. රජු ගෙදර ගියා.
රජු ගියා. රජු ආවා. රජු ගෙදර ගියා. රජු ගියා.
"""

    good_essay = """
ශ්‍රී ලංකාවේ ඉතිහාසය පිළිබඳ මෙම රචනාව ඉදිරිපත් කරනු ලැබේ.
දේවානම්පියතිස්ස රජතුමා බෞද්ධ ධර්මය ශ්‍රී ලංකාවේ ව්‍යාප්ත කිරීමේ
රාජකීය අනුග්‍රහය දැක්වූ ප්‍රථම රජු ලෙස ඉතිහාසයේ සඳහන් වේ.
මහාවිහාරය ඉදිකිරීමෙන් සංස්කෘතික හා ආගමික ස්ථාවරත්වය ලබා දෙන ලදී.
"""

    for label, essay in [('Poor essay', bad_essay), ('Better essay', good_essay)]:
        r = score_vocabulary(essay)
        print(f"\n── {label} ──")
        print(f"  Score            : {r['score']}/5")
        print(f"  MATTR            : {r['mattr']}")
        print(f"  Academic density : {r['academic_density']}")
        print(f"  Informal count   : {r['informal_count']}")
        print(f"  Hint (SI)        : {r['hint_si']}")

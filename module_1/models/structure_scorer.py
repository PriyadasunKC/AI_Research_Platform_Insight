"""
Dimension 4 - Structural Adherence

Scoring method (rule-based baseline):
  Checks 4 structural components, each weighted:

  Component          Weight   How detected
  Has Introduction    25%     First paragraph contains intro signals
  Has Thesis          25%     First paragraph contains thesis signals
  3+ Body Paragraphs  30%     para_count >= 4 (intro + 2+ body + conclusion)
  Has Conclusion      20%     Last paragraph contains conclusion signals

  raw = intro×0.25 + thesis×0.25 + body×0.30 + conclusion×0.20
  score = round(raw × 4 + 1)  → clamped to 1–5
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from features.feature_extractor import extract_features
from config import STRUCTURE_WEIGHTS


def score_structure(essay_text: str) -> dict:
    """
    Parameters
    ----------
    essay_text : str

    Returns
    -------
    dict with keys:
        score           int  1–5
        max             int  5
        dimension       str
        para_count      int
        has_intro       bool
        has_thesis      bool
        has_body        bool   True if 3+ body paragraphs
        has_conclusion  bool
        missing         list   component names that failed
        hint_en         str
        hint_si         str
    """
    f = extract_features(essay_text)

    has_intro      = f['has_intro']
    has_thesis     = f['has_thesis']
    has_conclusion = f['has_conclusion']
    para_count     = f['para_count']

    # Body score: scales from 0 (<=2 paragraphs) to 1.0 (5+ paragraphs)
    # We need intro + at least 2 body + conclusion = 4 paragraphs minimum
    if para_count <= 2:
        body_score = 0.0
    elif para_count == 3:
        body_score = 0.5       # has something but not full 3-body structure
    else:
        body_score = min((para_count - 2) / 3.0, 1.0)

    has_body = para_count >= 4

    # Weighted raw score
    raw = (
        (1.0 if has_intro      else 0.0) * STRUCTURE_WEIGHTS['intro']      +
        (1.0 if has_thesis     else 0.0) * STRUCTURE_WEIGHTS['thesis']     +
        body_score                        * STRUCTURE_WEIGHTS['body']       +
        (1.0 if has_conclusion else 0.0) * STRUCTURE_WEIGHTS['conclusion']
    )

    score = max(1, min(5, round(raw * 4.0 + 1.0)))

    # Missing components
    missing = []
    if not has_intro:
        missing.append('introduction')
    if not has_thesis:
        missing.append('thesis statement')
    if not has_body:
        missing.append('3+ body paragraphs')
    if not has_conclusion:
        missing.append('conclusion')

    # Sinhala hints
    si_labels = {
        'introduction'      : 'හැඳින්වීම (introduction)',
        'thesis statement'  : 'ප්‍රධාන තර්කය / thesis statement',
        '3+ body paragraphs': 'ප්‍රධාන කොටස් 3ක් (body paragraphs)',
        'conclusion'        : 'නිගමනය (conclusion)',
    }

    para_hint = (
        f"දැනට ඇති ඡේද ගණන: {para_count}. "
        f"අවම වශයෙන් ඡේද 5ක් (හැඳින්වීම + ශරීරය 3 + නිගමනය) අවශ්‍ය වේ."
    )

    if not missing:
        hint_si = (
            "ඔබේ රචනාවේ ව්‍යූහය හොඳය. "
            "හැඳින්වීම, ශරීරය සහ නිගමනය පැහැදිලිව දැකිය හැකිය."
        )
    else:
        missing_si = ', '.join(si_labels[m] for m in missing)
        hint_si = (
            f"රචනා ව්‍යූහයේ පහත කොටස් හෝ දුර්වල හෝ නොමැත: {missing_si}. "
            + para_hint
        )

    hint_en = (
        f"para_count={para_count}, "
        f"intro={has_intro}, thesis={has_thesis}, "
        f"body={has_body}, conclusion={has_conclusion}. "
        f"Missing: {missing}. raw={raw:.3f} → {score}/5"
    )

    return {
        'score'         : score,
        'max'           : 5,
        'dimension'     : 'D4_structure',
        'para_count'    : para_count,
        'has_intro'     : has_intro,
        'has_thesis'    : has_thesis,
        'has_body'      : has_body,
        'has_conclusion': has_conclusion,
        'missing'       : missing,
        'hint_en'       : hint_en,
        'hint_si'       : hint_si,
    }


# Self-test
if __name__ == '__main__':

    no_structure = "රජු ගියා. රජු ආවා. රජු ගෙදර ගියා."

    good_structure = """
ශ්‍රී ලංකාවේ ඉතිහාසය පිළිබඳ මෙම රචනාව ඉදිරිපත් කරනු ලැබේ.
බෞද්ධ ධර්මය ව්‍යාප්ත කිරීම ශ්‍රී ලංකා ඉතිහාසයේ ප්‍රධාන සිදුවීමක් බව සිතිය හැකිය.

මහින්ද හිමිගේ ලංකා ගමනය බෞද්ධ ධර්මය ව්‍යාප්ත කිරීමේ ආරම්භය විය.

දේවානම්පියතිස්ස රජතුමාගේ රාජකීය අනුග්‍රහය නිසා
මහාවිහාරය ඉදිකිරීම සිදු විය.

ශ්‍රී ලංකාවේ සංස්කෘතික ස්ථාවරත්වය බෞද්ධ සංඝයාගේ
ක්‍රියාකාරිත්වයෙන් ශක්තිමත් විය.

අවසාන වශයෙන් මෙලෙස ශ්‍රී ලංකාවේ බෞද්ධ ශිෂ්ටාචාරය ගොඩ නැගිණ.
ඉහත සාකච්ඡා කළ කරුණු අනුව මෙය ඉතිහාසයේ සුවිශේෂ සිදුවීමකි.
"""

    for label, essay in [('No structure', no_structure), ('Good structure', good_structure)]:
        r = score_structure(essay)
        print(f"\n── {label} ──")
        print(f"  Score      : {r['score']}/5")
        print(f"  Para count : {r['para_count']}")
        print(f"  Has intro  : {r['has_intro']}")
        print(f"  Has thesis : {r['has_thesis']}")
        print(f"  Has body   : {r['has_body']}")
        print(f"  Has concl. : {r['has_conclusion']}")
        print(f"  Missing    : {r['missing']}")
        print(f"  Hint (SI)  : {r['hint_si']}")

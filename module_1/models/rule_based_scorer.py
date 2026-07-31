"""
models/rule_based_scorer.py
============================
Master scorer — combines D2, D3, D4 rule-based dimension scores.
Returns unified dict with:
  - scores        : {D1, D2, D3, D4}
  - notes         : structured notes for Module 3 (SinLlama)
  - dimensions    : per-dimension detail for Flask UI
  - average_score : float
  - summary_si    : Sinhala summary
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.coherence_scorer  import score_coherence
from models.vocabulary_scorer import score_vocabulary
from models.structure_scorer  import score_structure


# ── Structured note helpers (for Module 3) ────────────────────────────────

def _d2_what_wrong(d2):
    n       = d2['type_count']
    missing = d2['missing_types']
    if n == 0:
        return "No discourse connectors found at all."
    return f"Only {n}/5 connector types found. Missing: {missing}"

def _d2_how_to_improve(d2):
    tips = {
        'cause_effect': 'Add cause-effect: එබැවින්, ඒ නිසා, ප්‍රතිඵලයක් ලෙස',
        'contrast'    : 'Add contrast: නමුත්, එහෙත්, එසේ වුවද',
        'addition'    : 'Add addition: එසේම, ඊට අමතරව, තවද',
        'sequence'    : 'Add sequence: ඉන් පසු, පළමුව, දෙවනුව',
        'example'     : 'Add examples: උදාහරණයක් ලෙස, එනම්',
    }
    return ' | '.join(tips[t] for t in d2['missing_types'] if t in tips) or 'Good connector usage.'

def _d3_what_wrong(d3):
    issues = []
    if d3['mattr'] < 0.45:
        top = list(d3['repeated_words'].items())[:3]
        issues.append(f"High repetition: {', '.join(f'{w}({c}x)' for w,c in top)}")
    if d3['academic_density'] < 0.05:
        issues.append('Very low academic vocabulary density')
    if d3['informal_count'] > 0:
        issues.append(f"Informal words: {d3['informal_words'][:3]}")
    return ' | '.join(issues) if issues else 'Vocabulary is acceptable.'

def _d3_how_to_improve(d3):
    tips = []
    if d3['repeated_words']:
        tips.append('Replace repeated words with synonyms')
    if d3['academic_density'] < 0.10:
        tips.append('Add academic terms: රාජකීය, සංස්කෘතික, ශිෂ්ටාචාරය, ඓතිහාසික')
    if d3['informal_words']:
        tips.append('Use formal Sinhala — avoid informal verb forms')
    return ' | '.join(tips) if tips else 'Maintain current vocabulary level.'

def _d4_what_wrong(d4):
    issues = []
    if not d4['has_intro']:      issues.append('No clear introduction')
    if not d4['has_thesis']:     issues.append('No thesis statement in intro')
    if not d4['has_body']:       issues.append(f"Only {d4['para_count']} paragraphs (need 4+)")
    if not d4['has_conclusion']: issues.append('No conclusion')
    return ' | '.join(issues) if issues else 'Structure is acceptable.'

def _d4_how_to_improve(d4):
    tips = []
    if not d4['has_intro']:      tips.append('Start with intro paragraph introducing the topic')
    if not d4['has_thesis']:     tips.append('Add thesis — state your main argument in the intro')
    if not d4['has_body']:       tips.append('Write 3 separate body paragraphs, each with one main point')
    if not d4['has_conclusion']: tips.append('End with: අවසාන වශයෙන්, මෙලෙස')
    return ' | '.join(tips) if tips else 'Maintain current structure.'

def _build_summary(d2, d3, d4, avg):
    labels  = {'D2_coherence': 'සම්බන්ධිතතාව',
               'D3_vocabulary': 'වචන සම්පත',
               'D4_structure': 'රචනා ව්‍යූහය'}
    lowest  = min([d2, d3, d4], key=lambda x: x['score'])
    if avg >= 4.0:
        return 'ඔබේ රචනාව ඉතා හොඳ මට්ටමකය. ඉහළ ලකුණු ලබා ගැනීමට දිගටම වැඩ කරන්න.'
    elif avg >= 3.0:
        return f"සාමාන්‍ය මට්ටමකය. {labels.get(lowest['dimension'], '')} වැඩිදියුණු කරන්න."
    else:
        return f"වැඩිදියුණු කළ යුතුය. {labels.get(lowest['dimension'], '')} කෙරෙහි අවධානය යොමු කරන්න."


# ── Main public function ──────────────────────────────────────────────────

def score_essay(essay_text: str, d1_score: int = None) -> dict:
    """
    Score a Sinhala essay on D2, D3, D4.

    Returns
    -------
    dict with keys:
        scores        — {D1, D2, D3, D4}  integer scores
        notes         — structured notes for Module 3
        dimensions    — per-dimension detail dict for Flask UI
        average_score — float
        summary_si    — Sinhala summary string
        model_type    — 'rule_based'
        word_count    — int
        elapsed_sec   — float
    """
    if not essay_text or not essay_text.strip():
        raise ValueError('Essay text cannot be empty.')

    start = time.time()

    d2 = score_coherence(essay_text)
    d3 = score_vocabulary(essay_text)
    d4 = score_structure(essay_text)

    # ── Validate d1_score ─────────────────────────────────────────────────
    if d1_score is not None:
        try:
            d1_score = int(d1_score)
            if not (1 <= d1_score <= 5):
                d1_score = None
        except (ValueError, TypeError):
            d1_score = None

    # ── Scores dict ───────────────────────────────────────────────────────
    scores = {
        'D1': d1_score,
        'D2': d2['score'],
        'D3': d3['score'],
        'D4': d4['score'],
    }

    valid  = [v for v in scores.values() if v is not None]
    avg    = round(sum(valid) / len(valid), 2)

    # ── Structured notes for Module 3 ────────────────────────────────────
    notes = {
        'D2_note': {
            'score'         : d2['score'],
            'what_wrong'    : _d2_what_wrong(d2),
            'found_markers' : d2['found_markers'],
            'missing_types' : d2['missing_types'],
            'how_to_improve': _d2_how_to_improve(d2),
            'short_note_si' : d2['hint_si'],
        },
        'D3_note': {
            'score'          : d3['score'],
            'what_wrong'     : _d3_what_wrong(d3),
            'repeated_words' : d3['repeated_words'],
            'academic_words' : d3['academic_words'],
            'informal_words' : d3['informal_words'],
            'how_to_improve' : _d3_how_to_improve(d3),
            'short_note_si'  : d3['hint_si'],
        },
        'D4_note': {
            'score'          : d4['score'],
            'what_wrong'     : _d4_what_wrong(d4),
            'para_count'     : d4['para_count'],
            'missing'        : d4['missing'],
            'has_intro'      : d4['has_intro'],
            'has_thesis'     : d4['has_thesis'],
            'has_body'       : d4['has_body'],
            'has_conclusion' : d4['has_conclusion'],
            'how_to_improve' : _d4_how_to_improve(d4),
            'short_note_si'  : d4['hint_si'],
        },
    }

    # ── Dimensions dict for Flask UI ──────────────────────────────────────
    dimensions = {
        'D1_historical_accuracy': {
            'score'   : d1_score,
            'max'     : 5,
            'dimension': 'D1_historical_accuracy',
            'hint_si' : ('D1 ලකුණ සහකරු මොඩියුලය මගින් ලැබේ.'
                         if d1_score else
                         'D1 ලකුණ තවමත් ලබා ගෙන නොමැත.'),
            'hint_en' : ('Scored by team member module.'
                         if d1_score else
                         'Not yet integrated.'),
            'source'  : 'external' if d1_score else 'pending',
        },
        'D2_coherence'  : d2,
        'D3_vocabulary' : d3,
        'D4_structure'  : d4,
    }

    return {
        # ── Primary fields ────────────────────────────────────────────────
        'scores'        : scores,
        'notes'         : notes,
        'dimensions'    : dimensions,
        'average_score' : avg,
        'summary_si'    : _build_summary(d2, d3, d4, avg),

        # ── Metadata ──────────────────────────────────────────────────────
        'total_scored'  : len(valid),
        'essay_length'  : len(essay_text),
        'word_count'    : len(essay_text.split()),
        'elapsed_sec'   : round(time.time() - start, 3),
        'model_type'    : 'rule_based',
        'model_note'    : 'Baseline scorer. SinBERT scorer activates when .pt file is present.',
    }
"""
Stage 1 - Feature Extraction (pure rule-based, no ML model needed).

Reads a raw Sinhala essay string and returns a flat dictionary of all
measurable features used by the three dimension scorers (D2, D3, D4).

Usage:
    from features.feature_extractor import extract_features
    features = extract_features(essay_text)
"""

import re
import json
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import (
    ACADEMIC_VOCAB_FILE, NSINA_VOCAB_FILE,
    DISCOURSE_MARKERS, INFORMAL_WORDS,
    INTRO_SIGNALS, THESIS_SIGNALS, CONCLUSION_SIGNALS,
    MATTR_WINDOW,
)

# Load vocabulary files

def _load_json_set(filepath: str, fallback=None) -> set:
    if os.path.exists(filepath):
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if isinstance(data, list):
            return set(data)
        if isinstance(data, dict):
            return set(data.keys())
    print(f"  Vocab file not found: {filepath}")
    print(f" Run data/process_kings_data.py first.")
    return set(fallback or [])


ACADEMIC_VOCAB: set = _load_json_set(ACADEMIC_VOCAB_FILE)
NSINA_VOCAB   : set = _load_json_set(NSINA_VOCAB_FILE)
# Combined formal vocab = kings academic words + NSina common words
FORMAL_VOCAB  : set = ACADEMIC_VOCAB | NSINA_VOCAB

INFORMAL_SET  : set = set(INFORMAL_WORDS)


# Tokenisation & splitting helpers

def tokenize(text: str) -> list:
    """Return list of Sinhala unicode word tokens."""
    return re.findall(r'[\u0D80-\u0DFF]+', text)


def split_sentences(text: str) -> list:
    """Split on sentence-ending punctuation and newlines."""
    raw = re.split(r'[.!?।\n]', text)
    return [s.strip() for s in raw if len(s.strip()) > 10]


def split_paragraphs(text: str) -> list:
    """Split on blank lines."""
    raw = re.split(r'\n\s*\n', text)
    return [p.strip() for p in raw if len(p.strip()) > 20]


# Vocabulary metrics

def compute_ttr(tokens: list) -> float:
    """Type-Token Ratio. Affected by essay length - prefer MATTR."""
    if not tokens:
        return 0.0
    return len(set(tokens)) / len(tokens)


def compute_mattr(tokens: list, window: int = MATTR_WINDOW) -> float:
    """
    Moving Average TTR.
    Slides a fixed window across the token list and averages the TTR
    of each window - not affected by essay length.
    Falls back to simple TTR for short essays.
    """
    if len(tokens) < window:
        return compute_ttr(tokens)
    ttrs = []
    for i in range(len(tokens) - window + 1):
        w = tokens[i: i + window]
        ttrs.append(len(set(w)) / window)
    return sum(ttrs) / len(ttrs)


def get_repeated_words(tokens: list, threshold: int = 5) -> dict:
    """Words that appear >= threshold times (excluding very short tokens)."""
    counts = Counter(t for t in tokens if len(t) >= 3)
    return {w: c for w, c in counts.items() if c >= threshold}


def get_academic_words(tokens: list) -> list:
    """Tokens that are in the academic / domain vocab set."""
    return [t for t in tokens if t in ACADEMIC_VOCAB]


def get_informal_words(tokens: list) -> list:
    return [t for t in tokens if t in INFORMAL_SET]

# Coherence metrics
def detect_discourse_markers(text: str) -> dict:
    """
    Returns dict of {marker_type: [markers_found_in_text]}.
    Only types where at least one marker is present are included.
    """
    found = {}
    for marker_type, markers in DISCOURSE_MARKERS.items():
        hits = [m for m in markers if m in text]
        if hits:
            found[marker_type] = hits
    return found

# Structural metrics
def _contains_any(text: str, signals: list) -> bool:
    return any(sig in text for sig in signals)

def detect_intro(paragraphs: list) -> bool:
    if not paragraphs:
        return False
    return _contains_any(paragraphs[0], INTRO_SIGNALS)

def detect_thesis(paragraphs: list) -> bool:
    if not paragraphs:
        return False
    return _contains_any(paragraphs[0], THESIS_SIGNALS)

def detect_conclusion(paragraphs: list) -> bool:
    if not paragraphs:
        return False
    return _contains_any(paragraphs[-1], CONCLUSION_SIGNALS)

def sentence_length_variance(sentences: list) -> float:
    lengths = [len(tokenize(s)) for s in sentences]
    if len(lengths) < 2:
        return 0.0
    mean = sum(lengths) / len(lengths)
    return sum((l - mean) ** 2 for l in lengths) / len(lengths)

# Main public function
def extract_features(essay_text: str) -> dict:
    """
    Extract all measurable features from a Sinhala essay string.

    Returns
    -------
    dict with keys grouped into:
      vocabulary   - ttr, mattr, repetition info, academic/informal words
      coherence    - discourse marker types and counts
      structure    - paragraph/sentence counts, intro/thesis/conclusion flags
      raw          - paragraph list, sentence list (for scorer debugging)
    """
    if not essay_text or not essay_text.strip():
        raise ValueError("Essay text is empty.")

    tokens     = tokenize(essay_text)
    sentences  = split_sentences(essay_text)
    paragraphs = split_paragraphs(essay_text)

    if not tokens:
        raise ValueError("No Sinhala text found in the essay.")

    # Vocabulary
    ttr              = compute_ttr(tokens)
    mattr            = compute_mattr(tokens)
    repeated_words   = get_repeated_words(tokens)
    academic_words   = get_academic_words(tokens)
    informal_words   = get_informal_words(tokens)

    total_tokens     = len(tokens)
    unique_tokens    = len(set(tokens))
    repetition_ratio = len(repeated_words) / max(unique_tokens, 1)
    academic_density = len(academic_words) / max(total_tokens, 1)
    informal_ratio   = len(informal_words)  / max(total_tokens, 1)

    # Coherence 
    discourse_markers    = detect_discourse_markers(essay_text)
    discourse_type_count = len(discourse_markers)

    # Structure 
    para_count    = len(paragraphs)
    sent_count    = len(sentences)
    has_intro     = detect_intro(paragraphs)
    has_thesis    = detect_thesis(paragraphs)
    has_conclusion= detect_conclusion(paragraphs)
    sent_variance = sentence_length_variance(sentences)

    return {
        # Vocabulary features
        'ttr'              : round(ttr,   4),
        'mattr'            : round(mattr, 4),
        'total_tokens'     : total_tokens,
        'unique_tokens'    : unique_tokens,
        'repetition_ratio' : round(repetition_ratio, 4),
        'repeated_words'   : dict(list(repeated_words.items())[:15]),
        'academic_density' : round(academic_density, 4),
        'academic_words'   : academic_words[:20],
        'informal_ratio'   : round(informal_ratio, 4),
        'informal_words'   : informal_words[:15],

        # Coherence features
        'discourse_type_count' : discourse_type_count,
        'discourse_markers'    : discourse_markers,

        # Structure features
        'para_count'           : para_count,
        'sentence_count'       : sent_count,
        'has_intro'            : has_intro,
        'has_thesis'           : has_thesis,
        'has_conclusion'       : has_conclusion,
        'sent_length_variance' : round(sent_variance, 4),

        # Raw 
        'paragraphs'  : paragraphs,
        'sentences'   : sentences[:30],
    }

# Quick self-test

if __name__ == '__main__':
    sample = """
ශ්‍රී ලංකාවේ ඉතිහාසය පිළිබඳ මෙම රචනාව ඉදිරිපත් කරනු ලැබේ.

මහින්ද හිමි ලංකාවට පැමිණිය. එබැවින් බෞද්ධ ධර්මය ව්‍යාප්ත විය.
නමුත් රජතුමාගේ සහාය නොමැතිව මෙය කළ නොහැකිව තිබිණ.

එසේම මහාවිහාරය ඉදිකිරීම රාජකීය අනුග්‍රහයෙන් සිදු විය.
ඉන් පසු ලංකාවේ බෞද්ධ ශිෂ්ටාචාරය ගොඩ නැගිණ.

අවසාන වශයෙන් මෙලෙස ශ්‍රී ලංකාවේ සංස්කෘතික උරුමය ස්ථාපිත විය.
"""

    try:
        features = extract_features(sample)
        print("=== EXTRACTED FEATURES ===\n")
        for key, val in features.items():
            if key not in ('paragraphs', 'sentences'):
                print(f"  {key:30s}: {val}")
    except Exception as e:
        print(f"Error: {e}")

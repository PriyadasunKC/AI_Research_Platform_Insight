"""
config.py
=========
Central configuration for Insight Module 1.
All paths, constants, and Sinhala language resources live here.

Works on:
  - Windows local (VS Code)       : paths resolve from this file's location
  - Google Colab (Drive mounted)  : same - BASE_DIR auto-detected

DO NOT hardcode any paths. Always use the variables defined here.
"""

import os

from dotenv import load_dotenv

# Loads .env into os.environ (e.g. HF_TOKEN for downloading SinBERT-large -
# see utils/sinbert_embedder.py - and the MODULE2_*/MONGO_* overrides below).
# Must run before any os.environ.get() calls in this file or importers of it.
load_dotenv()

# ─────────────────────────────────────────────────────────────────────────────
# Project root - auto-detected from this file's location
# Works on Windows, Mac, Linux, and Google Colab
# ─────────────────────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ─────────────────────────────────────────────────────────────────────────────
# Data paths
# ─────────────────────────────────────────────────────────────────────────────
DATA_DIR      = os.path.join(BASE_DIR, 'data')
PROCESSED_DIR = os.path.join(DATA_DIR, 'processed')

KINGS_RAW_FILE = os.path.join(
    DATA_DIR,
    'sri_lankan_kings_all_-_normal_sinhala_raw_text.txt'
)

NAMED_ENTITIES_FILE = os.path.join(PROCESSED_DIR, 'named_entities.json')
ACADEMIC_VOCAB_FILE = os.path.join(PROCESSED_DIR, 'academic_vocab.json')
FACT_DATABASE_FILE  = os.path.join(PROCESSED_DIR, 'fact_database.json')
RAG_PASSAGES_FILE   = os.path.join(PROCESSED_DIR, 'rag_passages.json')
NSINA_VOCAB_FILE    = os.path.join(PROCESSED_DIR, 'nsina_vocab.json')

# Essay data
ESSAYS_RAW_FILE       = os.path.join(DATA_DIR, 'essays_raw.json')
ESSAYS_FIXED_FILE     = os.path.join(DATA_DIR, 'essays_raw.json')
ANNOTATED_ESSAYS_FILE = os.path.join(DATA_DIR, 'annotated_essays.json')

# ─────────────────────────────────────────────────────────────────────────────
# Model paths
# ─────────────────────────────────────────────────────────────────────────────
MODELS_DIR        = os.path.join(BASE_DIR, 'models')
SAVED_MODELS_DIR  = os.path.join(MODELS_DIR, 'saved')
SINBERT_SAVE_PATH = os.path.join(SAVED_MODELS_DIR, 'sinbert_scorer.pt')

# ─────────────────────────────────────────────────────────────────────────────
# Flask settings
# ─────────────────────────────────────────────────────────────────────────────
FLASK_PORT  = 5000
FLASK_DEBUG = True

# ─────────────────────────────────────────────────────────────────────────────
# Module 2 integration - historical-accuracy dimension (D1)
# Module 1 calls Module 2's external API (AI_Research_Platform_Insight/module_2,
# run separately via `uvicorn api_server:app --port 8010`) server-side on every
# /score request to get the D1 score. All overridable via env vars so this
# still works if Module 2 runs on a different host/port in another environment.
# ─────────────────────────────────────────────────────────────────────────────
MODULE2_BASE_URL = os.environ.get('MODULE2_BASE_URL', 'http://127.0.0.1:8010')
# Dedicated key registered for Module 1 under ESSAY_API_KEYS in module_2/.env
# (caller name "Module1") - distinct from the LocalTestClient/Module3 keys so
# module_2's saved run history correctly attributes these calls to Module 1.
MODULE2_API_KEY = os.environ.get('MODULE2_API_KEY', '3nHwZAiB7gFz6lqck_FLjk4S72DjFvrv')
# Module 2 grades an essay in batches of up to 6 sentences via the Claude
# API - a long, multi-paragraph essay needs several sequential batch calls.
# On top of that, the frontend calls Module 2 directly AT THE SAME TIME as
# Module 1 does (both fire in parallel so the Module 2 panel can render
# early - see frontend/app/page.tsx), so Module 2 is effectively grading
# the SAME essay twice, concurrently, doubling its real workload for every
# request. 180s was too tight for a long essay under that doubled load -
# raised to 400s. If this still isn't enough for very long essays, the
# more scalable fix is removing the frontend's redundant direct call
# (Module 1's response already embeds Module 2's full result either way).
MODULE2_TIMEOUT_SECONDS = int(os.environ.get('MODULE2_TIMEOUT_SECONDS', '400'))

# ─────────────────────────────────────────────────────────────────────────────
# MongoDB - SAME database Module 2 uses (see module_2/.env MONGO_URI/MONGO_DB),
# so both modules' history lives in one place. Module 1's combined D1-D4
# results are written to their own collection (utils/mongo_store.py) rather
# than Module 2's `essay_check_runs`, since the two have different shapes.
# ─────────────────────────────────────────────────────────────────────────────
MONGO_URI = os.environ.get(
    'MONGO_URI',
    'mongodb+srv://ner_user:nerdb123@sinhalakg.gsxkm5p.mongodb.net/?appName=sinhalakg',
)
MONGO_DB = os.environ.get('MONGO_DB', 'sinhalakg')

# ─────────────────────────────────────────────────────────────────────────────
# Scoring weights  (from project spec)
# ─────────────────────────────────────────────────────────────────────────────
VOCAB_WEIGHTS = {
    'mattr'      : 0.35,
    'academic'   : 0.40,
    'repetition' : 0.25,
}

STRUCTURE_WEIGHTS = {
    'intro'      : 0.25,
    'thesis'     : 0.25,
    'body'       : 0.30,
    'conclusion' : 0.20,
}

# ─────────────────────────────────────────────────────────────────────────────
# Sinhala discourse markers
# 5 types - each type found = +1 to coherence score (max 5/5)
# ─────────────────────────────────────────────────────────────────────────────
DISCOURSE_MARKERS = {
    'cause_effect': [
        'එබැවින්',
        'එම නිසා',
        'ප්‍රතිඵලයක් ලෙස',
        'හේතුවෙන්',
        'නිසා',
        'ඒ හේතුවෙන්',
        'ඒ නිසා',
        'දෙයාකාරයෙන්',
    ],
    'contrast': [
        'එහෙත්',
        'නමුත්',
        'එසේ වුවද',
        'ඒ අතර',
        'ඊට වෙනස්ව',
        'කෙසේ නමුත්',
        'වෙනස් ව',
        'ඊට පටහැනිව',
    ],
    'addition': [
        'එසේම',
        'එමෙන්ම',
        'ඊට අමතරව',
        'තවද',
        'එපමණක් නොව',
        'එමෙන්',
    ],
    'sequence': [
        'ඉන් පසු',
        'ඉන් අනතුරුව',
        'පළමුව',
        'දෙවනුව',
        'අවසාන වශයෙන්',
        'මුලින්ම',
        'ඉන්පසු',
        'අනතුරුව',
        'ක්‍රමයෙන්',
    ],
    'example': [
        'උදාහරණයක් ලෙස',
        'එනම්',
        'නිදසුනක් ලෙස',
        'නිදර්ශනයක් ලෙස',
        'විශේෂයෙන්',
    ],
}

# ─────────────────────────────────────────────────────────────────────────────
# Informal words - penalised in D3 vocabulary scoring
# ─────────────────────────────────────────────────────────────────────────────
INFORMAL_WORDS = [
    'හොඳ',
    'දෙනවා',
    'ගන්නවා',
    'කරනවා',
    'යනවා',
    'එනවා',
    'කිව්වා',
    'ගියා',
    'ආවා',
    'කළා',
    'හිටියා',
    'තිබුණා',
]

# ─────────────────────────────────────────────────────────────────────────────
# Structural signal words
# Used by feature_extractor to detect intro / thesis / conclusion
# ─────────────────────────────────────────────────────────────────────────────
INTRO_SIGNALS = [
    'පිළිබඳ',
    'සම්බන්ධ',
    'ඉතිහාස',
    'යන',
    'ලෙස',
    'රචනාව',
    'ඉදිරිපත්',
    'ශ්‍රී ලංකා',
    'කෙරේ',
    'සාකච්ඡා',
    'මෙම',
    'අරමුණ',
]

THESIS_SIGNALS = [
    'විය',
    'බව',
    'ලෙස සැලකිය',
    'කෙරේ',
    'ඇතැයි',
    'තර්කය',
    'ප්‍රධාන',
    'අරමුණ',
    'හේතුව',
    'ඉලක්කය',
]

CONCLUSION_SIGNALS = [
    'සාරාංශ',
    'නිගමන',
    'අවසාන',
    'මෙලෙස',
    'ඉහත',
    'සිදු කළ',
    'අවසාන වශයෙන්',
    'නිමා',
    'ප්‍රතිඵල',
    'විග්‍රහ',
    'කෙළවර',
]

# ─────────────────────────────────────────────────────────────────────────────
# Named entity markers
# Used by process_kings_data.py to extract king/place names
# ─────────────────────────────────────────────────────────────────────────────
KING_MARKERS = [
    'රජ',
    'රජු',
    'රජතුමා',
    'රජුන්',
    'කුමාරු',
    'හිමි',
    'දේව',
    'අභය',
    'නිලමේ',
    'මහරජ',
]

PLACE_MARKERS = [
    'නුවර',
    'පුර',
    'රාජධානිය',
    'විහාරය',
    'දාගැබ',
    'ගිරිය',
    'ලංකා',
    'පුරය',
    'දිස්ත්‍රික්කය',
    'ගම',
]

# ─────────────────────────────────────────────────────────────────────────────
# MATTR (Moving Average Type-Token Ratio) settings
# ─────────────────────────────────────────────────────────────────────────────
MATTR_WINDOW = 50   # sliding window size in tokens

# Normalisation thresholds
MATTR_PERFECT    = 0.70   # MATTR >= 0.70  → perfect vocabulary variety
ACADEMIC_PERFECT = 0.15   # density >= 15% → perfect academic vocab usage

# ─────────────────────────────────────────────────────────────────────────────
# SinBERT model settings (Phase 2 - after collecting annotated essays)
# ─────────────────────────────────────────────────────────────────────────────
SINBERT_MODEL_ID  = 'sinhala-nlp/sinbert-large-si'
SINBERT_MAX_LEN   = 512
SINBERT_DROPOUT   = 0.3
SINBERT_LR        = 2e-4
SINBERT_EPOCHS    = 15
SINBERT_BATCH     = 8

# QWK target per dimension
QWK_TARGET = 0.65

# ─────────────────────────────────────────────────────────────────────────────
# Sanity check - run directly to verify all paths
# Usage:  python config.py
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    print("=" * 65)
    print("  Insight Module 1 - Configuration Check")
    print("=" * 65)
    print(f"\n  BASE_DIR      : {BASE_DIR}")
    print(f"  DATA_DIR      : {DATA_DIR}")
    print(f"  PROCESSED_DIR : {PROCESSED_DIR}")
    print(f"\n  File status:")

    files = [
        ('Kings raw text',    KINGS_RAW_FILE,       True),
        ('Academic vocab',    ACADEMIC_VOCAB_FILE,   False),
        ('Named entities',    NAMED_ENTITIES_FILE,   False),
        ('Fact database',     FACT_DATABASE_FILE,    False),
        ('RAG passages',      RAG_PASSAGES_FILE,     False),
        ('NSina vocab',       NSINA_VOCAB_FILE,      False),
        ('Essays fixed',      ESSAYS_FIXED_FILE,     False),
        ('Annotated essays',  ANNOTATED_ESSAYS_FILE, False),
        ('SinBERT model',     SINBERT_SAVE_PATH,     False),
    ]

    missing_required = []
    for label, path, required in files:
        exists  = os.path.exists(path)
        status  = '✅' if exists else ('❌ REQUIRED' if required else '○  not yet')
        size    = f"({os.path.getsize(path):,} bytes)" if exists else ''
        print(f"    {label:20s} {status}  {size}")
        print(f"    {'':20s} {path}")
        if required and not exists:
            missing_required.append(label)

    print()
    if not missing_required:
        print("  ✅ Config OK. Run: python data/process_kings_data.py")
    else:
        print(f"  ❌ Missing required files: {missing_required}")
        print(f"     Make sure the kings .txt file is in: {DATA_DIR}")
    print("=" * 65)
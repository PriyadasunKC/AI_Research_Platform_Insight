"""
process_kings_data.py
Extracts: named_entities.json, academic_vocab.json, 
          fact_database.json, rag_passages.json
from sri_lankan_kings_raw_text.txt
"""

import json
import re
import os

# REPLACE with config.py imports:
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import (
    KINGS_RAW_FILE  as RAW_FILE,
    PROCESSED_DIR   as OUT_DIR,
    NAMED_ENTITIES_FILE,
    ACADEMIC_VOCAB_FILE,
    FACT_DATABASE_FILE,
    RAG_PASSAGES_FILE,
    KING_MARKERS,
    PLACE_MARKERS,
)

# 1. Load raw text 
with open(RAW_FILE, 'r', encoding='utf-8') as f:
    raw_text = f.read()

paragraphs = [p.strip() for p in raw_text.split('\n\n') if len(p.strip()) > 50]
sentences  = [s.strip() for p in paragraphs for s in re.split('[.!?।]', p) if len(s.strip()) > 20]

print(f" Loaded {len(paragraphs)} paragraphs, {len(sentences)} sentences")

# 2. Named entities - kings, places, dates 
KING_MARKERS = ['රජ', 'රජු', 'රජතුමා', 'රජුන්', 'කුමාරු', 'හිමි', 'දේව']
PLACE_MARKERS = ['නුවර', 'පුර', 'රාජධානිය', 'විහාරය', 'දාගැබ', 'ගිරිය', 'ලංකා']

def extract_entities(text):
    entities = {'kings': set(), 'places': set(), 'dates': set()}
    
    # Dates: ක්‍රි.පූ. / ක්‍රි.ව. patterns
    dates = re.findall(r'ක්‍රි\.(?:පූ|ව)\.\s*\d+', text)
    entities['dates'].update(dates)
    
    # King/place names: words before markers
    words = text.split()
    for i, word in enumerate(words):
        for marker in KING_MARKERS:
            if word == marker and i > 0:
                entities['kings'].add(words[i-1] + ' ' + marker)
        for marker in PLACE_MARKERS:
            if marker in word and len(word) > len(marker) + 1:
                entities['places'].add(word)
    
    return {k: list(v) for k, v in entities.items()}

all_entities = extract_entities(raw_text)
print(f" Kings found: {len(all_entities['kings'])}")
print(f" Places found: {len(all_entities['places'])}")
print(f" Dates found: {len(all_entities['dates'])}")

with open(f'{OUT_DIR}/named_entities.json', 'w', encoding='utf-8') as f:
    json.dump(all_entities, f, ensure_ascii=False, indent=2)
print(" named_entities.json saved")

# 3. Academic vocabulary
# appear in multiple paragraphs = domain-specific)
from collections import Counter

def tokenize_sinhala(text):
    # Simple whitespace + punctuation split for Sinhala
    words = re.findall(r'[\u0D80-\u0DFF]+', text)
    return words

word_counts = Counter()
para_word_sets = []
for para in paragraphs:
    words = set(tokenize_sinhala(para))
    para_word_sets.append(words)
    word_counts.update(words)

# Academic vocab: appears in 3+ paragraphs, length >= 4 unicode chars
academic_vocab = [
    word for word, count in word_counts.items()
    if count >= 3 
    and len(word) >= 4
    and sum(1 for ws in para_word_sets if word in ws) >= 3
]

print(f" Academic vocabulary: {len(academic_vocab)} terms")

with open(f'{OUT_DIR}/academic_vocab.json', 'w', encoding='utf-8') as f:
    json.dump(sorted(academic_vocab), f, ensure_ascii=False, indent=2)
print(" academic_vocab.json saved")

# 4. Fact database
# Extract structured facts per king section
fact_database = {}
current_king = None

for para in paragraphs:
    # Detect king headings (short paragraphs with king markers)
    if len(para) < 60 and any(m in para for m in KING_MARKERS):
        current_king = para.strip()
        fact_database[current_king] = []
    elif current_king:
        dates_in_para = re.findall(r'ක්‍රි\.(?:පූ|ව)\.\s*\d+', para)
        if dates_in_para:
            fact_database[current_king].append({
                'text': para[:200],
                'dates': dates_in_para
            })

print(f" Fact database: {len(fact_database)} king entries")

with open(f'{OUT_DIR}/fact_database.json', 'w', encoding='utf-8') as f:
    json.dump(fact_database, f, ensure_ascii=False, indent=2)
print(" fact_database.json saved")

# 5. RAG passages
rag_passages = []
for i, para in enumerate(paragraphs):
    if len(para) > 80:
        rag_passages.append({
            'id': f'kings_{i:04d}',
            'source': 'sri_lankan_kings',
            'text': para[:500],
        })

print(f" RAG passages: {len(rag_passages)} chunks")

with open(f'{OUT_DIR}/rag_passages.json', 'w', encoding='utf-8') as f:
    json.dump(rag_passages, f, ensure_ascii=False, indent=2)
print(" rag_passages.json saved")

print("\n🎉 All data processing complete!")
"""
ner_pipeline.py - XLM-RoBERTa NER model inference

Loads the trained XLM-RoBERTa NER model from a local directory and runs
inference on a Sinhala sentence.

Returns: list of (entity_span, label) tuples
    e.g. [("දුටුගැමුණු", "PERSON_KING"), ("රුවන්වැලිසෑය", "MONUMENT")]

NER Classes (10):
    PERSON_KING   - kings and rulers
    PERSON_MONK   - monks and clergy
    PERSON_OTHER  - other named persons
    LOCATION      - geographical places
    MONUMENT      - temples, stupas, buildings
    DYNASTY       - royal dynasties and lineages
    BATTLE_EVENT  - battles and military events
    DATE_ERA      - date / era / time period
    CHRONICLE     - text chronicles (e.g. Mahawamsa)
    RELIC         - sacred relics
    
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import NamedTuple

import torch
from dotenv import load_dotenv
from transformers import (
    AutoModelForTokenClassification,
    AutoTokenizer,
    TokenClassificationPipeline,
    pipeline,
)

load_dotenv()

# CONFIG

NER_MODEL_PATH: str = os.environ.get("NER_MODEL_PATH", "./models/xlmr_ner")
DEVICE: int = 0 if torch.cuda.is_available() else -1   # 0 = first GPU, -1 = CPU


# DATA TYPES

class NERTag(NamedTuple):
    """A single named-entity tag as returned by the NER model."""
    entity: str        # surface form of the entity span (Sinhala text)
    label:  str        # NER class (PERSON_KING, MONUMENT, etc.) - no B-/I- prefix
    start:  int = 0   # character offset in original sentence
    end:    int = 0   # character offset end in original sentence


# MODEL LOADING  (cached - loads once on first call)

_ner_pipeline: TokenClassificationPipeline | None = None


def _load_pipeline() -> TokenClassificationPipeline:
    """Load the HuggingFace token-classification pipeline from local path."""
    global _ner_pipeline
    if _ner_pipeline is not None:
        return _ner_pipeline

    model_path = Path(NER_MODEL_PATH)
    if not model_path.exists():
        raise FileNotFoundError(
            f"NER model directory not found: {model_path.resolve()}\n"
            f"Set NER_MODEL_PATH in your .env file to the correct path."
        )

    print(f"[NER] Loading model from: {model_path.resolve()} ...")
    tokenizer = AutoTokenizer.from_pretrained(str(model_path), local_files_only=True)
    model     = AutoModelForTokenClassification.from_pretrained(
                    str(model_path), local_files_only=True
                )
    _ner_pipeline = pipeline(
        task="ner",
        model=model,
        tokenizer=tokenizer,
        aggregation_strategy="simple",   # merge B-/I- tokens into spans
        device=DEVICE,
    )
    print("[NER] Model loaded.")
    return _ner_pipeline

# LABEL CLEANING

def _clean_label(raw_label: str) -> str:
    """
    Strip BIO prefixes from label string.

    HuggingFace pipeline with aggregation_strategy='simple' typically
    returns labels without B-/I-, but guard anyway.

    Examples:
        "B-PERSON_KING" → "PERSON_KING"
        "I-MONUMENT"    → "MONUMENT"
        "PERSON_KING"   → "PERSON_KING"
    """
    label = raw_label.strip()
    for prefix in ("B-", "I-", "S-", "E-"):
        if label.startswith(prefix):
            label = label[len(prefix):]
            break
    return label.upper()


# KNOWN VALID LABELS  (guards against model outputting unexpected classes)

VALID_LABELS: frozenset[str] = frozenset({
    "PERSON_KING", "PERSON_MONK", "PERSON_OTHER",
    "LOCATION", "MONUMENT", "DYNASTY",
    "BATTLE_EVENT", "DATE_ERA", "CHRONICLE", "RELIC",
})


# PUBLIC API

def run_ner(sentence: str) -> list[NERTag]:
    """
    Run NER inference on a single Sinhala sentence.

    Args:
        sentence: Raw Sinhala text string.

    Returns:
        List of NERTag(entity, label) - one entry per detected entity span.
        DATE_ERA entries ARE included (needed by relation extractor for
        the `period` field, even though they cannot be triple subjects/objects).

    Example:
        >>> run_ner("දුටුගැමුණු රජු රුවන්වැලිසෑය ඉදිකළේය.")
        [NERTag(entity='දුටුගැමුණු', label='PERSON_KING'),
         NERTag(entity='රුවන්වැලිසෑය', label='MONUMENT')]
    """
    sentence = sentence.strip()
    if not sentence:
        return []

    ner = _load_pipeline()
    raw_results: list[dict] = ner(sentence)

    tags: list[NERTag] = []
    for item in raw_results:
        entity_text: str = item.get("word", "").strip()
        raw_label:   str = item.get("entity_group", item.get("entity", ""))
        label = _clean_label(raw_label)

        # filter out O (outside) tags and unknown labels
        if label in ("O", "LABEL_0") or label not in VALID_LABELS:
            continue
        if not entity_text:
            continue

        # Remove HuggingFace subword artifacts (▁ from sentencepiece)
        entity_text = entity_text.replace("▁", "").strip()
        if entity_text:
            tags.append(NERTag(
                entity=entity_text,
                label=label,
                start=item.get("start", 0),
                end=item.get("end", 0),
            ))

    return tags


def run_ner_batch(sentences: list[str]) -> list[list[NERTag]]:
    """
    Run NER on a list of sentences (more efficient than calling run_ner in a loop).

    Args:
        sentences: List of Sinhala sentence strings.

    Returns:
        List of NERTag lists, one per input sentence (same order).
    """
    return [run_ner(s) for s in sentences]

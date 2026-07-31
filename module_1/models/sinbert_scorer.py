"""
models/sinbert_scorer.py
========================
Stage 2 scorer using fine-tuned SinBERT + custom scoring head.
QWK achieved: D2=0.883, D3=0.977, D4=0.830, Avg=0.897

Falls back to rule_based_scorer if sinbert_scorer.pt not found.
"""

import os
import sys
import time
import torch
import torch.nn as nn

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BASE_DIR   = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL_PATH = os.path.join(BASE_DIR, 'models', 'saved', 'sinbert_scorer.pt')
DEVICE     = 'cuda' if torch.cuda.is_available() else 'cpu'


class SinBERTScoringHead(nn.Module):
    def __init__(self, hidden_dim=768, n_dims=3, dropout=0.3):
        super().__init__()
        self.dropout1 = nn.Dropout(dropout)
        self.fc1      = nn.Linear(hidden_dim, 256)
        self.relu     = nn.ReLU()
        self.dropout2 = nn.Dropout(0.2)
        self.fc2      = nn.Linear(256, n_dims)
        self.sigmoid  = nn.Sigmoid()

    def forward(self, x):
        x = self.dropout1(x)
        x = self.fc1(x)
        x = self.relu(x)
        x = self.dropout2(x)
        x = self.fc2(x)
        return self.sigmoid(x) * 4.0 + 1.0


_sinbert   = None
_head      = None
_tokenizer = None
_loaded    = False
_load_err  = None


def _load_model() -> bool:
    global _sinbert, _head, _tokenizer, _loaded, _load_err

    if _loaded:
        return True
    if _load_err:
        return False

    if not os.path.exists(MODEL_PATH):
        _load_err = f"Model file not found: {MODEL_PATH}"
        print(f"⚠️  {_load_err}")
        print(f"   Falling back to rule-based scorer.")
        return False

    try:
        from transformers import AutoTokenizer, AutoModel
        import numpy  # needed for safe_globals fix

        MODEL_ID   = 'NLPC-UOM/SinBERT-large'
        print(f"⏳ Loading SinBERT from {MODEL_ID}...")

        _tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)
        _sinbert   = AutoModel.from_pretrained(MODEL_ID)

        for p in _sinbert.parameters():
            p.requires_grad = False

        hidden_dim = _sinbert.config.hidden_size
        _head      = SinBERTScoringHead(hidden_dim=hidden_dim, n_dims=3)

        # ── Fix for PyTorch 2.6 weights_only=True default ────────────────
        # The .pt file was saved with numpy arrays inside.
        # We add numpy scalar to safe globals so weights_only=True works.
        try:
            import numpy._core.multiarray
            with torch.serialization.safe_globals([numpy._core.multiarray.scalar]):
                checkpoint = torch.load(MODEL_PATH, map_location=DEVICE,
                                        weights_only=True)
        except Exception:
            # Final fallback: weights_only=False (trusted local file)
            checkpoint = torch.load(MODEL_PATH, map_location=DEVICE,
                                    weights_only=False)

        _head.load_state_dict(checkpoint['scoring_head'])

        _sinbert.to(DEVICE).eval()
        _head.to(DEVICE).eval()

        _loaded  = True
        best_qwk = checkpoint.get('best_avg_qwk', 'N/A')
        print(f"✅ SinBERT scorer loaded | QWK={best_qwk} | device={DEVICE}")
        return True

    except Exception as e:
        _load_err = str(e)
        print(f"❌ Failed to load SinBERT scorer: {e}")
        print(f"   Falling back to rule-based scorer.")
        return False


def _predict_sinbert(essay_text: str) -> dict:
    encoding = _tokenizer(
        essay_text,
        max_length     = 512,
        padding        = 'max_length',
        truncation     = True,
        return_tensors = 'pt',
    )
    input_ids = encoding['input_ids'].to(DEVICE)
    attn_mask = encoding['attention_mask'].to(DEVICE)

    with torch.no_grad():
        outputs   = _sinbert(input_ids=input_ids, attention_mask=attn_mask)
        cls_embed = outputs.last_hidden_state[:, 0, :]
        preds     = _head(cls_embed).squeeze(0)

    return {
        'D2'    : max(1, min(5, round(preds[0].item()))),
        'D3'    : max(1, min(5, round(preds[1].item()))),
        'D4'    : max(1, min(5, round(preds[2].item()))),
        'source': 'sinbert_finetuned',
    }


def score_essay_sinbert(essay_text: str, d1_score: int = None) -> dict:
    """
    Full scoring pipeline. Same output structure as rule_based_scorer.
    """
    if not essay_text or not essay_text.strip():
        raise ValueError('Essay text cannot be empty.')

    start = time.time()

    # Always run rule-based for features + structured notes
    from models.rule_based_scorer import score_essay as rule_score
    rule_result = rule_score(essay_text, d1_score=d1_score)

    # Get SinBERT scores (or fall back to rule-based scores)
    if _load_model():
        sinbert_scores = _predict_sinbert(essay_text)
        model_type     = 'sinbert_finetuned'
    else:
        sinbert_scores = {
            'D2'    : rule_result['scores']['D2'],
            'D3'    : rule_result['scores']['D3'],
            'D4'    : rule_result['scores']['D4'],
            'source': 'rule_based_fallback',
        }
        model_type = 'rule_based_fallback'

    # Override scores with SinBERT predictions
    rule_result['scores']['D2'] = sinbert_scores['D2']
    rule_result['scores']['D3'] = sinbert_scores['D3']
    rule_result['scores']['D4'] = sinbert_scores['D4']

    # Update notes scores
    notes = rule_result.get('notes', {})
    if 'D2_note' in notes: notes['D2_note']['score'] = sinbert_scores['D2']
    if 'D3_note' in notes: notes['D3_note']['score'] = sinbert_scores['D3']
    if 'D4_note' in notes: notes['D4_note']['score'] = sinbert_scores['D4']

    # Update dimensions scores
    dims = rule_result.get('dimensions', {})
    if 'D2_coherence'  in dims: dims['D2_coherence']['score']  = sinbert_scores['D2']
    if 'D3_vocabulary' in dims: dims['D3_vocabulary']['score'] = sinbert_scores['D3']
    if 'D4_structure'  in dims: dims['D4_structure']['score']  = sinbert_scores['D4']

    # Recalculate average
    valid = [v for v in rule_result['scores'].values() if v is not None]
    rule_result['average_score'] = round(sum(valid) / len(valid), 2)
    rule_result['model_type']    = model_type
    rule_result['elapsed_sec']   = round(time.time() - start, 3)

    return rule_result
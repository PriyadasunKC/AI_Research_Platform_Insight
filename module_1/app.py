"""
app.py
======
Insight Module 1 — Flask Web Application

Routes:
  GET  /                       → essay submission UI
  POST /score                  → scores essay, returns JSON (now also
                                  generates a Module-3 handoff file)
  GET  /download/<filename>    → download a generated export file
  GET  /health                 → health check
"""

import os
import sys
import traceback
import uuid

from flask import Flask, render_template, request, jsonify, send_from_directory

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.export_module3 import save_export_files, EXPORT_DIR

# ── Load best available scorer ────────────────────────────────────────────
# Tries SinBERT fine-tuned first, falls back to rule-based
_scorer_type = 'unknown'

try:
    from models.sinbert_scorer import score_essay_sinbert as _score_fn
    _scorer_type = 'sinbert_finetuned'
    print("✅ Using SinBERT scorer (QWK=0.897)")
except Exception as e:
    try:
        from models.rule_based_scorer import score_essay as _base_fn
        _scorer_type = 'rule_based'
        print(f"⚠️  SinBERT not available ({e}), using rule-based scorer")

        def _score_fn(essay_text, d1_score=None):
            return _base_fn(essay_text, d1_score=d1_score)
    except Exception as e2:
        print(f"❌ No scorer available: {e2}")
        _score_fn = None


def score_essay_unified(essay_text: str, d1_score=None) -> dict:
    """
    Unified scoring function.
    Always returns the same dict structure regardless of which
    underlying scorer is used.
    """
    if _score_fn is None:
        raise RuntimeError("No scorer loaded. Check models/ folder.")

    result = _score_fn(essay_text, d1_score=d1_score)

    # ── Normalise to unified response format ──────────────────────────────
    scores = result.get('scores', {})
    notes  = result.get('notes', {})
    dims   = result.get('dimensions', {})

    # Build hints dict (short Sinhala notes per dimension)
    hints = {
        'D2': notes.get('D2_note', {}).get('short_note_si',
               dims.get('D2_coherence',  {}).get('hint_si', '')),
        'D3': notes.get('D3_note', {}).get('short_note_si',
               dims.get('D3_vocabulary', {}).get('hint_si', '')),
        'D4': notes.get('D4_note', {}).get('short_note_si',
               dims.get('D4_structure',  {}).get('hint_si', '')),
    }

    # Build features dict for UI display
    features = {
        'total_words'          : result.get('word_count', len(essay_text.split())),
        'named_entity_count'   : len(notes.get('D2_note', {})
                                       .get('found_markers', {}).get('cause_effect', [])),
        'discourse_marker_count': dims.get('D2_coherence', {}).get('type_count', 0),
        'ttr'                  : round(result.get('essay_length', 0) /
                                       max(result.get('word_count', 1), 1), 3),
        'sentence_count'       : 0,  # feature extractor value if needed
    }

    return {
        'scores'       : {k: v for k, v in scores.items() if v is not None},
        'hints'        : hints,
        'notes'        : notes,           # structured notes for Module 3
        'average_score': result.get('average_score', 0),
        'summary_si'   : result.get('summary_si', ''),
        'features'     : features,
        'model_type'   : result.get('model_type', _scorer_type),
        'word_count'   : result.get('word_count', len(essay_text.split())),
    }


# ── Flask app ─────────────────────────────────────────────────────────────
app = Flask(__name__)

# Set this to your deployed base URL so download links work off-device too
# (e.g. "https://insight-module1.onrender.com"). Falls back to localhost.
BASE_URL = os.environ.get('INSIGHT_BASE_URL', 'http://127.0.0.1:5000')


@app.route('/')
def home():
    return render_template('index.html')


@app.route('/health')
def health():
    return jsonify({'status': 'ok', 'scorer': _scorer_type})


@app.route('/download/<path:filename>')
def download(filename):
    """Serves a generated Module-3 export file (.json or .txt)."""
    return send_from_directory(EXPORT_DIR, filename, as_attachment=True)


@app.route('/score', methods=['POST'])
def score():
    try:
        essay_text = ''
        essay_id = request.form.get('essay_id') or (
            request.get_json(silent=True) or {}
        ).get('essay_id') if request.is_json else request.form.get('essay_id')
        essay_id = essay_id or f"essay-{uuid.uuid4().hex[:8]}"

        # Check uploaded file
        if 'essay_file' in request.files:
            file = request.files['essay_file']
            if file.filename != '':
                essay_text = file.read().decode('utf-8')

        # Check typed/JSON text
        if not essay_text:
            # Support both form data and JSON body
            if request.is_json:
                data       = request.get_json(silent=True) or {}
                essay_text = data.get('essay', '').strip()
                d1_score   = data.get('d1_score', None)
            else:
                essay_text = request.form.get('essay_text', '').strip()
                d1_score   = request.form.get('d1_score', None)
        else:
            d1_score = request.form.get('d1_score', None)

        # Parse d1_score
        if d1_score is not None:
            try:
                d1_score = int(d1_score)
                if not (1 <= d1_score <= 5):
                    d1_score = None
            except (ValueError, TypeError):
                d1_score = None

        # Validate essay
        if not essay_text:
            return jsonify({
                'error': 'රචනයක් ඇතුළත් කරන්න හෝ ගොනුවක් උඩුගත කරන්න.'
            }), 400

        if len(essay_text.split()) < 10:
            return jsonify({
                'error': 'රචනය ඉතා කෙටිය. අවම වශයෙන් වචන 10ක් ලියන්න.'
            }), 400

        # Score
        result  = score_essay_unified(essay_text, d1_score=d1_score)
        scores  = result['scores']
        weakest = min(
            {k: v for k, v in scores.items() if k != 'D1' and v},
            key=lambda k: scores[k],
            default='D2'
        )
        total = round(sum(v for v in scores.values() if v), 1)

        # ── Generate the Module-3 handoff file ─────────────────────────────
        # Until Module 1 → Module 3 is wired together directly, this writes
        # the exact payload Module 3 expects (see docs §10.2) to disk, plus
        # a readable .txt version. You share the files yourself afterward.
        export_info = save_export_files(
            essay_text=essay_text,
            scores={**scores, 'D1': d1_score},
            notes=result['notes'],
            essay_id=essay_id,
            average_score=result['average_score'],
            summary_si=result['summary_si'],
            weakest=weakest,
        )

        return jsonify({
            'essay_id'     : essay_id,
            'scores'       : scores,
            'hints'        : result['hints'],
            'notes'        : result['notes'],        # for Module 3
            'weakest'      : weakest,
            'total'        : total,
            'average_score': result['average_score'],
            'summary_si'   : result['summary_si'],
            'word_count'   : result['word_count'],
            'model_type'   : result['model_type'],
            'features'     : result['features'],
            'module3_export': {
                'json_download_url': f"{BASE_URL}/download/{export_info['json_filename']}",
                'txt_download_url' : f"{BASE_URL}/download/{export_info['txt_filename']}",
            },
        })

    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    app.run(debug=True)
"""
app.py
======
Insight Module 1 — Flask Web Application

Routes:
  GET  /                       → essay submission UI
  POST /score                  → scores essay, calls Module 2 live for D1,
                                  returns combined JSON (also generates a
                                  Module-3 handoff file)
  POST /score-offline          → same, but takes an uploaded Module 2
                                  result JSON instead of calling Module 2
                                  live — for when only one module's backend
                                  is running on this machine at a time
  GET  /download/<filename>    → download a generated export file
  GET  /health                 → health check
"""

import json
import os
import sys
import traceback
import uuid

# Windows' default console codepage (cp1252) can't encode the emoji used in
# the scorer-fallback log messages below, which previously crashed the
# whole app at import time with UnicodeEncodeError before Flask even
# started — this has nothing to do with which scorer loads, just stdout.
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except AttributeError:
        pass  # Python < 3.7 fallback — not expected on this project

from flask import Flask, render_template, request, jsonify, send_from_directory
from flask_cors import CORS

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.export_module3 import save_export_files, EXPORT_DIR
from utils import module2_client
from utils import mongo_store

# Maps essay_id -> latest module3_exports/*.json filename, so Module 3 can
# GET /api/v1/module3/<essay_id> without needing to know the exact
# timestamped filename save_export_files() generated. Persisted to disk
# (not just in-memory) so it survives a Flask restart between requests.
MODULE3_INDEX_FILE = os.path.join(EXPORT_DIR, "_index.json")


def _load_module3_index() -> dict:
    if not os.path.exists(MODULE3_INDEX_FILE):
        return {}
    try:
        with open(MODULE3_INDEX_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def _save_module3_index(index: dict) -> None:
    with open(MODULE3_INDEX_FILE, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)


def _record_module3_export(essay_id: str, json_filename: str) -> None:
    index = _load_module3_index()
    index[essay_id] = json_filename
    index["_latest"] = json_filename
    _save_module3_index(index)

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


def score_essay_unified(essay_text: str, submitted_by=None, manual_d1_score=None, module2_call=None) -> dict:
    """
    Unified scoring function.
    Always returns the same dict structure regardless of which
    underlying scorer is used.

    D1 (historical accuracy) normally comes from calling Module 2's
    external API server-side (utils/module2_client) — Module 1 is the
    single source of the combined 4-dimension result in that case.

    `module2_call`, if passed, SKIPS that live HTTP call entirely and uses
    this pre-built result instead — shaped exactly like
    module2_client.check_historical_accuracy()'s return value:
    {"ok": True, "raw": <Module 2 API response dict>} or
    {"ok": False, "error": "..."}. This is how /score-offline lets Module 1
    run on a machine where Module 2 isn't running at all (see that route),
    using a Module 2 result JSON the caller already has (e.g. downloaded
    from Module 2's own standalone frontend page earlier).

    `manual_d1_score` (an already-1-5 integer) is used ONLY as a fallback
    when neither of the above produces a usable result (e.g. the live
    Module 2 call fails), so manual testing without Module 2 up still
    works the way it did before this integration.
    """
    if _score_fn is None:
        raise RuntimeError("No scorer loaded. Check models/ folder.")

    if module2_call is None:
        module2_call = module2_client.check_historical_accuracy(essay_text, submitted_by=submitted_by)
    if module2_call.get('ok'):
        d1_score = module2_client.accuracy_to_d1(module2_call['raw'].get('accuracy_score'))
    else:
        d1_score = manual_d1_score

    result = _score_fn(essay_text, d1_score=d1_score)

    # ── Normalise to unified response format ──────────────────────────────
    scores = result.get('scores', {})
    notes  = dict(result.get('notes', {}))  # copy — about to add D1_note
    dims   = result.get('dimensions', {})

    notes['D1_note'] = module2_client.build_d1_note(module2_call)

    # Build hints dict (short Sinhala notes per dimension)
    hints = {
        'D1': notes['D1_note'].get('short_note_si', ''),
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
        'scores'         : {k: v for k, v in scores.items() if v is not None},
        'd1_score'       : d1_score,        # resolved D1 (int 1-5 or None) — kept even when None,
                                             # since it's filtered out of 'scores' above but the
                                             # Module-3 export needs the key present either way
        'hints'          : hints,
        'notes'          : notes,           # structured notes for Module 3, now incl. D1_note
        'average_score'  : result.get('average_score', 0),
        'summary_si'     : result.get('summary_si', ''),
        'features'       : features,
        'model_type'     : result.get('model_type', _scorer_type),
        'word_count'     : result.get('word_count', len(essay_text.split())),
        'module2_result' : module2_call,    # raw Module 2 response (or {"ok": False, "error": ...})
    }


# ── Flask app ─────────────────────────────────────────────────────────────
app = Flask(__name__)

# Internal, trusted multi-module project (Module 1 backend, Module 2 backend,
# the Next.js frontend, Module 3) — permissive CORS, matching Module 2's own
# api_server.py. Tighten allow_origins to specific URLs if ever exposed
# outside this project.
CORS(app)

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


def _finalize_and_respond(essay_text: str, essay_id: str, result: dict):
    """Shared tail end of both /score and /score-offline: builds the
    weakest-area/total summary, writes the Module-3 export file, saves to
    MongoDB, and returns the JSON response. The only difference between the
    two routes is how `result` (from score_essay_unified) got its D1 data —
    this part is identical either way, so it lives in one place."""
    scores   = result['scores']
    d1_score = result['d1_score']
    weakest = min(
        {k: v for k, v in scores.items() if k != 'D1' and v},
        key=lambda k: scores[k],
        default='D2'
    )
    total = round(sum(v for v in scores.values() if v), 1)

    # ── Generate the Module-3 handoff file ──────────────────────────────
    # Writes the exact combined payload Module 3 expects (see docs §10.2)
    # to disk, plus a readable .txt version, and records it in the
    # essay_id -> filename index so GET /api/v1/module3/<essay_id> (and
    # /api/v1/module3/latest) can serve it back as JSON directly.
    export_info = save_export_files(
        essay_text=essay_text,
        scores={**scores, 'D1': d1_score},
        notes=result['notes'],
        essay_id=essay_id,
        average_score=result['average_score'],
        summary_si=result['summary_si'],
        weakest=weakest,
    )
    _record_module3_export(essay_id, export_info['json_filename'])

    module3_export = {
        'json_download_url': f"{BASE_URL}/download/{export_info['json_filename']}",
        'txt_download_url' : f"{BASE_URL}/download/{export_info['txt_filename']}",
        'api_url'          : f"{BASE_URL}/api/v1/module3/{essay_id}",
    }

    # ── Save to MongoDB — same database Module 2 uses, dedicated
    # collection (module1_combined_results). Best-effort: if MongoDB
    # is unreachable, mongo_id is just None and the response/file
    # export above are unaffected — see utils/mongo_store.py.
    mongo_id = mongo_store.save_combined_result(
        essay_id=essay_id,
        essay_text=essay_text,
        scores={**scores, 'D1': d1_score},
        notes=result['notes'],
        weakest=weakest,
        average_score=result['average_score'],
        summary_si=result['summary_si'],
        module2_result=result['module2_result'],
        module3_export=module3_export,
    )

    return jsonify({
        'essay_id'     : essay_id,
        'mongo_id'     : mongo_id,
        'scores'       : {**scores, 'D1': d1_score},
        'hints'        : result['hints'],
        'notes'        : result['notes'],        # for Module 3, includes D1_note
        'weakest'      : weakest,
        'total'        : total,
        'average_score': result['average_score'],
        'summary_si'   : result['summary_si'],
        'word_count'   : result['word_count'],
        'model_type'   : result['model_type'],
        'features'     : result['features'],
        'module2_result': result['module2_result'],  # raw Module 2 response, for transparency
        'module3_export': module3_export,
    })


def _extract_essay_and_id():
    """Shared essay_text/essay_id extraction for /score and /score-offline
    — both accept either an uploaded 'essay_file' or an 'essay'/'essay_text'
    form or JSON field."""
    essay_text = ''
    essay_id = request.form.get('essay_id') or (
        request.get_json(silent=True) or {}
    ).get('essay_id') if request.is_json else request.form.get('essay_id')
    essay_id = essay_id or f"essay-{uuid.uuid4().hex[:8]}"

    if 'essay_file' in request.files:
        file = request.files['essay_file']
        if file.filename != '':
            essay_text = file.read().decode('utf-8')

    if not essay_text:
        if request.is_json:
            data = request.get_json(silent=True) or {}
            essay_text = (data.get('essay') or data.get('essay_text') or '').strip()
        else:
            essay_text = (request.form.get('essay_text') or request.form.get('essay') or '').strip()

    return essay_text, essay_id


@app.route('/score', methods=['POST'])
def score():
    try:
        essay_text, essay_id = _extract_essay_and_id()

        if request.is_json:
            manual_d1_score = (request.get_json(silent=True) or {}).get('d1_score', None)
        else:
            manual_d1_score = request.form.get('d1_score', None)

        # Parse manual_d1_score — only used as a fallback if the live call to
        # Module 2 (inside score_essay_unified) fails; see module2_client.py.
        if manual_d1_score is not None:
            try:
                manual_d1_score = int(manual_d1_score)
                if not (1 <= manual_d1_score <= 5):
                    manual_d1_score = None
            except (ValueError, TypeError):
                manual_d1_score = None

        # Validate essay
        if not essay_text:
            return jsonify({
                'error': 'රචනයක් ඇතුළත් කරන්න හෝ ගොනුවක් උඩුගත කරන්න.'
            }), 400

        if len(essay_text.split()) < 10:
            return jsonify({
                'error': 'රචනය ඉතා කෙටිය. අවම වශයෙන් වචන 10ක් ලියන්න.'
            }), 400

        # Score — this internally calls Module 2's API to get D1
        # (historical accuracy), so this single call already produces the
        # combined D1-D4 result; see score_essay_unified() / module2_client.py.
        result = score_essay_unified(essay_text, submitted_by=essay_id, manual_d1_score=manual_d1_score)
        return _finalize_and_respond(essay_text, essay_id, result)

    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/score-offline', methods=['POST'])
def score_offline():
    """Same as /score, but for when Module 2 ISN'T running on this machine
    (see docs/HOW_TO_RUN_AND_TEST.md — running both modules together can
    exhaust RAM on limited hardware). Instead of calling Module 2's API,
    accepts a Module 2 result JSON the caller already has — e.g. downloaded
    earlier from Module 2's own standalone frontend page while Module 2 WAS
    running. Module 1 still scores D2-D4 itself and merges everything into
    the identical combined output /score produces.

    Accepts multipart/form-data:
      essay_file OR essay_text — the essay, same as /score
      module2_file OR module2_json — the uploaded Module 2 result: either
        an uploaded .json file, or the JSON as a raw text form field. This
        must be the exact response shape from Module 2's
        POST /api/v1/essay/check (accuracy_score, claims, etc.) — the same
        thing /score would have received from calling Module 2 live.
      essay_id — optional
    """
    try:
        essay_text, essay_id = _extract_essay_and_id()

        module2_json_text = None
        if 'module2_file' in request.files and request.files['module2_file'].filename:
            module2_json_text = request.files['module2_file'].read().decode('utf-8')
        elif request.form.get('module2_json'):
            module2_json_text = request.form.get('module2_json')
        elif request.is_json:
            body = request.get_json(silent=True) or {}
            module2_json_text = body.get('module2_json')
            if isinstance(module2_json_text, dict):
                module2_json_text = json.dumps(module2_json_text)

        if not essay_text:
            return jsonify({'error': 'රචනයක් ඇතුළත් කරන්න හෝ ගොනුවක් උඩුගත කරන්න.'}), 400
        if len(essay_text.split()) < 10:
            return jsonify({'error': 'රචනය ඉතා කෙටිය. අවම වශයෙන් වචන 10ක් ලියන්න.'}), 400
        if not module2_json_text:
            return jsonify({'error': 'Module 2 result JSON is required (module2_file or module2_json).'}), 400

        try:
            module2_raw = json.loads(module2_json_text)
        except json.JSONDecodeError as exc:
            return jsonify({'error': f'Module 2 JSON is not valid: {exc}'}), 400

        if not isinstance(module2_raw, dict) or 'accuracy_score' not in module2_raw:
            return jsonify({
                'error': "Uploaded JSON doesn't look like a Module 2 result "
                         "(expected the response shape from Module 2's "
                         "POST /api/v1/essay/check, with an accuracy_score field)."
            }), 400

        module2_call = {'ok': True, 'raw': module2_raw}
        result = score_essay_unified(essay_text, submitted_by=essay_id, module2_call=module2_call)
        return _finalize_and_respond(essay_text, essay_id, result)

    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/v1/module3/latest')
def module3_latest():
    """Returns the most recently generated combined (D1-D4) result as JSON
    — a convenience for Module 3 when it doesn't have a specific essay_id
    to ask for. See /api/v1/module3/<essay_id> for a specific one."""
    index = _load_module3_index()
    filename = index.get('_latest')
    if not filename:
        return jsonify({'error': 'No essay has been scored yet.'}), 404
    return _serve_module3_json(filename)


@app.route('/api/v1/module3/<essay_id>')
def module3_by_essay_id(essay_id):
    """Module-3-facing API: returns the combined D1-D4 payload for a
    specific essay_id (the same shape written to module3_exports/*.json)
    directly as a JSON response body — not a file download — so Module 3
    can call this like a normal REST endpoint."""
    index = _load_module3_index()
    filename = index.get(essay_id)
    if not filename:
        return jsonify({'error': f'No scored result found for essay_id {essay_id!r}.'}), 404
    return _serve_module3_json(filename)


def _serve_module3_json(filename: str):
    path = os.path.join(EXPORT_DIR, filename)
    if not os.path.exists(path):
        return jsonify({'error': f'Export file {filename!r} is missing on disk.'}), 404
    with open(path, 'r', encoding='utf-8') as f:
        return jsonify(json.load(f))


@app.route('/api/v1/module1/history')
def module1_history():
    """Recent combined-scoring runs read back from MongoDB, newest first.
    Query param ?limit=N (default 20). Returns [] if MongoDB is unreachable
    — not an error, since Mongo is best-effort storage (see mongo_store.py),
    not the source of truth for a single essay_id (that's the file-backed
    /api/v1/module3/<essay_id> endpoint above)."""
    limit = request.args.get('limit', default=20, type=int)
    return jsonify(mongo_store.get_recent_combined_results(limit=limit))


@app.route('/api/v1/module1/history/<essay_id>')
def module1_history_by_id(essay_id):
    """One combined-scoring run read back from MongoDB by essay_id."""
    doc = mongo_store.get_combined_result(essay_id)
    if doc is None:
        return jsonify({'error': f'No MongoDB record found for essay_id {essay_id!r} (or MongoDB is unreachable).'}), 404
    return jsonify(doc)


if __name__ == '__main__':
    app.run(debug=True)
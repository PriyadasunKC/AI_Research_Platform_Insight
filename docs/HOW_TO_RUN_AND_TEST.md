# How to run and test — Module 1 + Module 2 + Frontend

Three processes, three terminals. Start them in this order (Module 2 first,
since Module 1 calls it on every `/score` request).

## 1. Start Module 2 (FastAPI, port 8010)

```
cd AI_Research_Platform_Insight/module_2
venv\Scripts\uvicorn api_server:app --host 127.0.0.1 --port 8010
```

Verify: open http://127.0.0.1:8010/api/v1/health — should return
`{"status":"ok","anthropic_key_configured":true,"api_keys_configured":4}`.
If `api_keys_configured` is less than 4, check `module_2/.env`'s
`ESSAY_API_KEYS` still has all four `key:CallerName` pairs
(`LocalTestClient`, `Module3`, `Module1`, `Frontend`).

## 2. Start Module 1 (Flask, port 5000)

First time only — Module 1 needs its own Python environment:

```
cd AI_Research_Platform_Insight/module_1
python -m venv venv
venv\Scripts\pip install -r requirements.txt
```

The SinBERT scorer (`torch`/`transformers`/`scikit-learn`) is commented
out in `requirements.txt` by default — **leave it that way** unless you
specifically have trained SinBERT weights and enough free RAM to run it
alongside Module 2's own ~1.1GB NER model. Installing it anyway has caused
Module 2 to crash silently (no error, no traceback — the OS kills the
process on out-of-memory) when both modules run at once on a machine with
limited RAM. Without it, Module 1 automatically uses the rule-based D2-D4
scorer, which produces the exact same response shape and needs no ML
dependencies at all.

Then, every time:

```
cd AI_Research_Platform_Insight/module_1
venv\Scripts\python app.py
```

Verify: open http://127.0.0.1:5000/health — should return
`{"status":"ok","scorer":"rule_based"}` (or `"sinbert_finetuned"` if torch
is installed).

## 3. Start the frontend (Next.js, port 3000)

First time only:

```
cd AI_Research_Platform_Insight/frontend
npm install
```

Then, every time:

```
cd AI_Research_Platform_Insight/frontend
npm run dev
```

Open http://localhost:3000 — type or upload an essay, click
**"Get Feedback for Essay"**. Nothing shows before you click; after
clicking, the Module 1 and Module 2 panels appear as each finishes,
followed by Recommendations and the Combined Output (with Copy/Download).

---

## Testing the APIs directly with Postman

Import `docs/postman_collection.json` into Postman. It has 4 folders:

- **0. Health checks** — confirms both backends are up before anything else.
- **Full Flow** — run requests 1 through 7 top to bottom. Request 1
  (`Module 1 — Score essay`) automatically saves its `essay_id` into a
  collection variable, so requests 2, 3, 4, 5 (which need that `essay_id`)
  work without you copy-pasting anything. Likewise request 6 saves
  `run_id` for request 7.
- **File uploads** — the same two "check an essay" endpoints, but via a
  `.txt` file instead of pasted text. You'll need to manually pick a file
  in the `essay_file` / `file` form field (Postman can't attach a file
  from a collection JSON automatically).

Collection variables you may want to check/change (top-left "..." on the
collection → Edit → Variables): `module1_base_url`, `module2_base_url`
(defaults match the ports above), `module2_api_key` (defaults to
`test-local-key`, already configured in `module_2/.env`), `essay_text`.

### What each Full Flow request actually proves

| # | Request | Proves |
|---|---|---|
| 1 | `POST /score` (Module 1) | Module 1 scores D2-D4, calls Module 2 server-side for D1, merges everything, saves a file export AND a MongoDB doc (`mongo_id` in the response). |
| 2 | `GET /api/v1/module3/<essay_id>` | The exact API Module 3 will call — combined `essay_text/scores/notes/weakest_area/rag_context` JSON, `D1` now a real number. |
| 3 | `GET /api/v1/module3/latest` | Same, without needing to know the `essay_id`. |
| 4 | `GET /api/v1/module1/history` | The combined result was actually persisted to MongoDB (same database Module 2 uses, collection `module1_combined_results`). |
| 5 | `GET /api/v1/module1/history/<essay_id>` | Same, filtered to one specific essay. |
| 6 | `POST /api/v1/essay/check` (Module 2) | Module 2 works standalone — this is exactly what Module 1 calls internally, and what the frontend also calls directly in parallel. |
| 7 | `GET /api/v1/essay/<run_id>` | Re-fetching a past Module 2 result by ID. |

### Common issues

- **Request 1 returns `"module2_result": {"ok": false, ...}` and
  `D1: null`** — Module 2 isn't reachable from Module 1. Check Module 2 is
  actually running on port 8010 (step 1) before Module 1 (step 2) tries to
  call it. Module 1 still returns D2-D4 successfully in this case; only D1
  is missing, with the specific error in `notes.D1_note.what_wrong`.
- **`api_keys_configured: 0` or 401 on request 6/7** — `module_2/.env`'s
  `ESSAY_API_KEYS` is missing or malformed; each entry needs the exact
  `key:CallerName` format, comma-separated, no spaces around the colon.
- **Garbled/question-mark Sinhala text in a terminal** — cosmetic only
  (Windows console codepage); the actual data returned in JSON is correct
  UTF-8 regardless of how the terminal displays it.
- **Module 2's terminal just stops — no error, no 502, process exits back
  to the shell prompt, right around a `[NER] Loading model from: ...`
  line** — out-of-memory. This happens if Module 1's SinBERT dependencies
  (`torch`/`transformers`/`scikit-learn`) got installed after all — check
  `module_1/requirements.txt` still has them commented out, and if not,
  `venv\Scripts\pip uninstall torch transformers scikit-learn` (stop
  Module 1 first — Windows locks the files while it's running). Check
  free RAM with Task Manager before reporting this as a bug; loading
  Module 2's ~1.1GB NER model needs a few GB headroom.
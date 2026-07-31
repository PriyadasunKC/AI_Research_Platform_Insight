# auto_score.py
# Run from project root: python auto_score.py
# ─────────────────────────────────────────────

import sys, json, os
from collections import Counter

# ── Path setup ────────────────────────────────
BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
os.chdir(BASE)

# ── Clear cached imports ──────────────────────
for mod in list(sys.modules.keys()):
    if any(x in mod for x in ['models', 'features', 'config']):
        del sys.modules[mod]

# ── Import scorer ─────────────────────────────
print("Loading scorer...")
from models.rule_based_scorer import score_essay
print("✅ Scorer loaded\n")

# ── File paths ────────────────────────────────
IN_FILE = os.path.join(BASE, 'data', 'essays_raw_fixed.json')
OUT_FILE = os.path.join(BASE, 'data', 'annotated_essays.json')

# ── Load essays ───────────────────────────────
if not os.path.exists(IN_FILE):
    print(f"❌ File not found: {IN_FILE}")
    print("   Place essays_raw.json in the data/ folder")
    sys.exit(1)

with open(IN_FILE, encoding='utf-8') as f:
    essays = json.load(f)

print(f"✅ Loaded {len(essays)} essays")
print(f"{'─'*65}")

# ── Score each essay ──────────────────────────
annotated = []
failed    = []

for i, essay in enumerate(essays):
    essay_id   = essay.get('id',    f'essay_{i+1:03d}')
    essay_text = essay.get('text',  '').strip()
    topic      = essay.get('topic', '')

    if len(essay_text) < 30:
        print(f"  ⚠️  Skipping {essay_id} — too short")
        failed.append(essay_id)
        continue

    try:
        result = score_essay(essay_text)
        d2 = result['dimensions']['D2_coherence']['score']
        d3 = result['dimensions']['D3_vocabulary']['score']
        d4 = result['dimensions']['D4_structure']['score']

        annotated.append({
            "id"                : essay_id,
            "topic"             : topic,
            "text"              : essay_text,
            "scores"            : {"D2": d2, "D3": d3, "D4": d4},
            "auto_scored"       : True,
            "lecturer_reviewed" : False,
            "annotator"         : "auto",
            "notes"             : ""
        })

        b = lambda s: "█"*s + "░"*(5-s)
        print(f"  {essay_id}  "
              f"D2:{d2}[{b(d2)}]  "
              f"D3:{d3}[{b(d3)}]  "
              f"D4:{d4}[{b(d4)}]  "
              f"{topic[:40]}...")

    except Exception as e:
        print(f"  ❌ {essay_id} — Error: {e}")
        failed.append(essay_id)

# ── Save output ───────────────────────────────
os.makedirs(os.path.dirname(OUT_FILE), exist_ok=True)
with open(OUT_FILE, 'w', encoding='utf-8') as f:
    json.dump(annotated, f, ensure_ascii=False, indent=2)

print(f"\n{'='*65}")
print(f"  ✅ Auto-scored : {len(annotated)} essays")
print(f"  ❌ Failed      : {len(failed)}  {failed if failed else ''}")
print(f"  📁 Saved to    : {OUT_FILE}")

# ── Score distribution ────────────────────────
print(f"\n  Score distribution:")
for dim in ['D2', 'D3', 'D4']:
    dist = dict(sorted(Counter(
        e['scores'][dim] for e in annotated
    ).items()))
    bars = '  '.join(f"{k}:{'█'*v}({v})" for k, v in dist.items())
    print(f"    {dim}: {bars}")

print(f"{'='*65}")
print(f"\n  Next: Upload annotated_essays.json to Google Drive")
print(f"        Path: MyDrive/insight_module1/data/annotated_essays.json")
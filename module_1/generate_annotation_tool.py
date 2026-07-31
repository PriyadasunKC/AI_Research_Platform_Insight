# generate_annotation_tool.py
# Run: python generate_annotation_tool.py
# Opens a browser tool for lecturers to review scores

import json, os

BASE        = os.path.dirname(os.path.abspath(__file__))
ESSAYS_FILE = os.path.join(BASE, 'data', 'annotated_essays.json')
HTML_OUT    = os.path.join(BASE, 'data', 'annotation_tool.html')

with open(ESSAYS_FILE, encoding='utf-8') as f:
    essays = json.load(f)

count     = len(essays)
essays_js = json.dumps(essays, ensure_ascii=False)

html = f"""<!DOCTYPE html>
<html lang="si">
<head>
<meta charset="UTF-8"/>
<title>Insight — Annotation Tool</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:sans-serif;background:#f0f2f5;color:#1a1a2e;min-height:100vh}}
header{{background:linear-gradient(135deg,#8B0000,#c0392b);color:white;
        padding:16px 28px;display:flex;justify-content:space-between;align-items:center}}
header h1{{font-size:1.2rem;font-weight:700}}
header span{{font-size:.85rem;opacity:.8}}
.wrap{{max-width:920px;margin:28px auto;padding:0 16px 60px}}
.prog-card{{background:white;border-radius:10px;padding:18px 22px;
            margin-bottom:20px;box-shadow:0 2px 8px rgba(0,0,0,.07)}}
.prog-bar-bg{{background:#eee;border-radius:6px;height:10px;margin-bottom:8px}}
.prog-bar{{background:#8B0000;height:100%;border-radius:6px;transition:width .4s}}
.prog-row{{display:flex;justify-content:space-between;align-items:center}}
.prog-txt{{font-size:.83rem;color:#555}}
.jump-row{{display:flex;gap:8px;align-items:center;margin-top:12px}}
.jump-row label{{font-size:.83rem;color:#555}}
.jump-row input{{width:68px;padding:6px 8px;border:1px solid #ccc;
                 border-radius:6px;font-size:.88rem}}
.card{{background:white;border-radius:12px;padding:26px;
       box-shadow:0 2px 8px rgba(0,0,0,.07);margin-bottom:20px}}
.meta{{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin-bottom:8px}}
.badge{{padding:3px 12px;border-radius:20px;font-size:.78rem;font-weight:600}}
.b-id{{background:#8B0000;color:white}}
.b-auto{{background:#fff3cd;color:#856404;border:1px solid #ffc107}}
.b-done{{background:#d4edda;color:#155724;border:1px solid #28a745}}
.topic{{font-size:.83rem;color:#666;font-style:italic;margin-bottom:10px}}
.essay-box{{background:#f8f8f8;border:1px solid #e0e0e0;border-radius:8px;
            padding:14px;font-size:.93rem;line-height:1.8;
            max-height:220px;overflow-y:auto;white-space:pre-wrap;margin-bottom:20px}}
.section-title{{font-weight:700;color:#8B0000;font-size:.95rem;margin-bottom:3px}}
.section-desc{{font-size:.78rem;color:#777;margin-bottom:10px}}
.btn-row{{display:flex;gap:8px;margin-bottom:6px}}
.sb{{width:52px;height:52px;border:2px solid #ddd;border-radius:8px;
     background:white;font-size:1.1rem;font-weight:700;cursor:pointer;
     transition:all .15s;color:#333}}
.sb:hover{{border-color:#8B0000;color:#8B0000}}
.sb.sel{{background:#8B0000;color:white;border-color:#8B0000}}
.meaning{{font-size:.78rem;color:#888;min-height:16px;margin-bottom:18px}}
.score-chips{{display:flex;gap:8px;margin-bottom:18px}}
.chip{{padding:4px 14px;border-radius:20px;font-size:.82rem;
       background:#f0f0f0;color:#555;font-weight:600}}
.chip.set{{background:#8B0000;color:white}}
.notes-lbl{{font-size:.83rem;color:#555;margin-bottom:5px;display:block}}
textarea{{width:100%;padding:10px 12px;border:1px solid #ddd;border-radius:8px;
          font-size:.88rem;resize:vertical;min-height:60px;font-family:inherit}}
.nav-row{{display:flex;gap:10px;margin-top:16px;flex-wrap:wrap;align-items:center}}
.btn{{padding:10px 22px;border:none;border-radius:8px;font-size:.9rem;
      font-weight:600;cursor:pointer;transition:background .15s}}
.btn-p{{background:#8B0000;color:white}}
.btn-p:hover{{background:#6B0000}}
.btn-s{{background:#e0e0e0;color:#333}}
.btn-s:hover{{background:#ccc}}
.btn-g{{background:#28a745;color:white}}
.btn-g:hover{{background:#218838}}
.saved-msg{{color:#28a745;font-size:.83rem;display:none;margin-left:6px}}
.dl-card{{background:white;border-radius:12px;padding:22px;text-align:center;
           box-shadow:0 2px 8px rgba(0,0,0,.07)}}
.dl-card h3{{color:#8B0000;margin-bottom:8px}}
.dl-card p{{font-size:.83rem;color:#777;margin-bottom:14px;line-height:1.6}}
.rubric-table{{width:100%;border-collapse:collapse;font-size:.8rem;margin-bottom:20px}}
.rubric-table th{{background:#8B0000;color:white;padding:8px 10px;text-align:left}}
.rubric-table td{{padding:7px 10px;border-bottom:1px solid #eee;vertical-align:top}}
.rubric-table tr:nth-child(even){{background:#fafafa}}
details{{margin-bottom:16px}}
summary{{cursor:pointer;font-weight:600;color:#8B0000;font-size:.88rem;
          padding:8px 0;user-select:none}}
</style>
</head>
<body>
<header>
  <h1>📝 Insight — Essay Annotation Tool</h1>
  <span id="hdr-count">1 / {count}</span>
</header>

<div class="wrap">

  <!-- Progress -->
  <div class="prog-card">
    <div class="prog-bar-bg">
      <div class="prog-bar" id="prog-bar" style="width:0%"></div>
    </div>
    <div class="prog-row">
      <span class="prog-txt" id="prog-txt">0 / {count} reviewed</span>
      <span class="prog-txt" id="prog-pct">0%</span>
    </div>
    <div class="jump-row">
      <label>Jump to essay:</label>
      <input type="number" id="jump-in" min="1" max="{count}" value="1"/>
      <button class="btn btn-s" onclick="jumpTo()">Go</button>
    </div>
  </div>

  <!-- Scoring rubric (collapsible) -->
  <div class="card">
    <details>
      <summary>📋 Scoring Rubric — Click to expand</summary>
      <br/>
      <table class="rubric-table">
        <tr><th>Score</th><th>D2 — සම්බන්ධිතතාව</th><th>D3 — වචන සම්පත</th><th>D4 — ව්‍යූහය</th></tr>
        <tr><td><strong>5</strong></td>
            <td>සම්බන්ධක 4+ වර්ග (හේතු, විරෝධ, එකතු, අනුක්‍රම, උදාහරණ)</td>
            <td>ශාස්ත්‍රීය වචන බහුල, නැවත නොයෙදේ, විධිමත්</td>
            <td>හැඳින්වීම + thesis + ශරීරය 3+ + නිගමනය සම්පූර්ණ</td></tr>
        <tr><td><strong>4</strong></td>
            <td>සම්බන්ධක 3 වර්ග</td>
            <td>හොඳ විවිධත්වය, බොහෝ දුරට විධිමත්</td>
            <td>හොඳ ව්‍යූහය, කුඩා දෝෂ</td></tr>
        <tr><td><strong>3</strong></td>
            <td>සම්බන්ධක 2 වර්ග</td>
            <td>යම් නැවත යෙදීම, ලිවිමත් / අලිවිමත් මිශ්‍ර</td>
            <td>හැඳින්වීම + නිගමනය ඇත, ශරීරය දුර්වල</td></tr>
        <tr><td><strong>2</strong></td>
            <td>සම්බන්ධක 1 වර්ගයක් පමණි</td>
            <td>ඉතා නැවත යෙදේ, අවිධිමත් වචන</td>
            <td>ව්‍යූහය හඳුනා ගැනීමට අපහසු</td></tr>
        <tr><td><strong>1</strong></td>
            <td>සම්බන්ධක නැත</td>
            <td>එකම වචන 10ක් නැවත නැවත</td>
            <td>ව්‍යූහයක් නැත</td></tr>
      </table>
    </details>
  </div>

  <!-- Main essay card -->
  <div class="card">
    <div class="meta">
      <span class="badge b-id" id="b-id">-</span>
      <span class="badge" id="b-status">-</span>
    </div>
    <div class="topic" id="topic-txt"></div>
    <div class="essay-box" id="essay-txt">Loading...</div>

    <!-- Current scores summary -->
    <div class="score-chips" id="chips"></div>

    <!-- D2 -->
    <div class="section-title">D2 — සම්බන්ධිතතාව හා අදහස් ප්‍රවාහය</div>
    <div class="section-desc">
      "එබැවින්", "නමුත්", "ඉන් පසු", "එසේම", "උදාහරණයක් ලෙස" — කී වර්ගයක් භාවිත කර ඇත්ද?
    </div>
    <div class="btn-row" id="btns-d2"></div>
    <div class="meaning"  id="mean-d2"></div>

    <!-- D3 -->
    <div class="section-title">D3 — වචන සම්පත</div>
    <div class="section-desc">
      ශාස්ත්‍රීය / ඉතිහාස වචන, නැවත නැවත නොයෙදීම, විධිමත් භාෂාව.
    </div>
    <div class="btn-row" id="btns-d3"></div>
    <div class="meaning"  id="mean-d3"></div>

    <!-- D4 -->
    <div class="section-title">D4 — රචනා ව්‍යූහය</div>
    <div class="section-desc">
      හැඳින්වීම + ප්‍රධාන තර්කය + ශරීරය (ඡේද 3+) + නිගමනය.
    </div>
    <div class="btn-row" id="btns-d4"></div>
    <div class="meaning"  id="mean-d4"></div>

    <!-- Notes -->
    <label class="notes-lbl">📌 සටහන් — ලකුණු ලබා දීමේ හේතු:</label>
    <textarea id="notes" placeholder="ඔබේ ඇගයීමේ හේතු ලියන්න..."></textarea>

    <div class="nav-row">
      <button class="btn btn-s" onclick="nav(-1)">← Back</button>
      <button class="btn btn-p" onclick="saveNext()">Save & Next →</button>
      <button class="btn btn-g" onclick="markReviewed()">✅ Mark Reviewed</button>
      <span class="saved-msg" id="saved-msg">✅ Saved!</span>
    </div>
  </div>

  <!-- Download -->
  <div class="dl-card">
    <h3>📥 Download Reviewed File</h3>
    <p>
      Review කළ essays ගොනුව බාගන්න.<br/>
      ඉන් පසු <strong>annotated_essays.json</strong> ගොනුව<br/>
      <code>insight_module1/data/</code> folder එකට copy කරන්න.
    </p>
    <button class="btn btn-g" onclick="dlJSON()">⬇️ Download annotated_essays.json</button>
    <p style="margin-top:10px;font-size:.75rem;color:#aaa">
      Auto-saves in browser. Download often to avoid losing work.
    </p>
  </div>

</div>

<script>
const ESSAYS = {essays_js};
const MEANINGS = {{
  1:"1 — ඉතාම දුර්වලය",
  2:"2 — දුර්වලය",
  3:"3 — සාමාන්‍යය",
  4:"4 — හොඳය",
  5:"5 — ඉතාම හොඳය"
}};

let cur  = 0;
let data = JSON.parse(JSON.stringify(ESSAYS));

function render(idx) {{
  const e = data[idx];
  document.getElementById('hdr-count').textContent = `${{idx+1}} / ${{data.length}}`;
  document.getElementById('b-id').textContent      = e.id;
  document.getElementById('topic-txt').textContent = e.topic || '';
  document.getElementById('essay-txt').textContent = e.text.trim();
  document.getElementById('notes').value           = e.notes || '';

  const st = document.getElementById('b-status');
  if (e.lecturer_reviewed) {{
    st.textContent = '✅ Reviewed by ' + (e.annotator || '?');
    st.className   = 'badge b-done';
  }} else {{
    st.textContent = 'Auto-scored — needs review';
    st.className   = 'badge b-auto';
  }}

  ['d2','d3','d4'].forEach(d => renderBtns(d, e.scores[d.toUpperCase()]));
  updateChips();
  updateProgress();
  document.getElementById('saved-msg').style.display = 'none';
}}

function renderBtns(dim, selected) {{
  const c = document.getElementById('btns-' + dim);
  c.innerHTML = '';
  for (let s = 1; s <= 5; s++) {{
    const b = document.createElement('button');
    b.className  = 'sb' + (s === selected ? ' sel' : '');
    b.textContent = s;
    b.onclick    = () => setScore(dim, s);
    c.appendChild(b);
  }}
  document.getElementById('mean-' + dim).textContent =
    selected ? MEANINGS[selected] : 'ලකුණු තෝරන්න';
}}

function setScore(dim, s) {{
  data[cur].scores[dim.toUpperCase()] = s;
  renderBtns(dim, s);
  updateChips();
}}

function updateChips() {{
  const sc = data[cur].scores;
  document.getElementById('chips').innerHTML =
    ['D2','D3','D4'].map(d =>
      `<span class="chip ${{sc[d] ? 'set' : ''}}">${{d}}: ${{sc[d] || '?'}}/5</span>`
    ).join('');
}}

function saveCurrent() {{
  data[cur].notes = document.getElementById('notes').value;
  try {{ localStorage.setItem('insight_ann', JSON.stringify(data)); }} catch(e) {{}}
}}

function saveNext() {{
  saveCurrent();
  if (cur < data.length - 1) {{
    cur++;
    render(cur);
    window.scrollTo(0, 0);
  }} else {{
    alert('සියලු රචනා ඇගයීම සම්පූර්ණ!\\nJSON ගොනුව බාගන්න.');
    dlJSON();
  }}
}}

function nav(dir) {{
  saveCurrent();
  cur = Math.max(0, Math.min(data.length - 1, cur + dir));
  render(cur);
  window.scrollTo(0, 0);
}}

function jumpTo() {{
  saveCurrent();
  const n = parseInt(document.getElementById('jump-in').value) - 1;
  if (n >= 0 && n < data.length) {{ cur = n; render(cur); window.scrollTo(0,0); }}
}}

function markReviewed() {{
  saveCurrent();
  const name = prompt('ඔබේ නම / ID:', 'lecturer_1') || 'lecturer_1';
  data[cur].lecturer_reviewed = true;
  data[cur].annotator         = name;
  render(cur);
  const msg = document.getElementById('saved-msg');
  msg.style.display = 'inline';
  setTimeout(() => msg.style.display = 'none', 2000);
}}

function updateProgress() {{
  const reviewed = data.filter(e => e.lecturer_reviewed).length;
  const pct      = Math.round(reviewed / data.length * 100);
  document.getElementById('prog-bar').style.width = pct + '%';
  document.getElementById('prog-txt').textContent  = `${{reviewed}} / ${{data.length}} reviewed`;
  document.getElementById('prog-pct').textContent  = pct + '%';
}}

function dlJSON() {{
  saveCurrent();
  const blob = new Blob(
    [JSON.stringify(data, null, 2)],
    {{ type: 'application/json' }}
  );
  const a    = document.createElement('a');
  a.href     = URL.createObjectURL(blob);
  a.download = 'annotated_essays.json';
  a.click();
  URL.revokeObjectURL(a.href);
}}

// Restore from localStorage if available
try {{
  const saved = localStorage.getItem('insight_ann');
  if (saved) {{
    const parsed = JSON.parse(saved);
    if (parsed.length === data.length) {{
      if (confirm('Previously saved annotations found. Restore them?')) {{
        data = parsed;
      }}
    }}
  }}
}} catch(e) {{}}

render(0);
</script>
</body>
</html>"""

with open(HTML_OUT, 'w', encoding='utf-8') as f:
    f.write(html)

print(f"✅ Annotation tool created!")
print(f"   File : {HTML_OUT}")
print(f"   Essays: {count}")
print(f"\n   Open annotation_tool.html in Chrome or Firefox")
print(f"   Give a copy to each lecturer")
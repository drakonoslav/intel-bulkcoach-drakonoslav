from fastapi import APIRouter
from fastapi.responses import HTMLResponse, FileResponse
from pathlib import Path

router = APIRouter(tags=["webui"])

CSV_PATH = Path(__file__).parent.parent.parent / "data" / "daily_log.csv"


@router.get("/log/export", include_in_schema=False)
def export_csv():
    if not CSV_PATH.exists():
        from fastapi.responses import PlainTextResponse
        return PlainTextResponse("No logs yet.", status_code=404)
    return FileResponse(
        path=str(CSV_PATH),
        media_type="text/csv",
        filename="arcforge_daily_log.csv",
    )

_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<title>ArcForge — Daily Log</title>
<style>
*{box-sizing:border-box;margin:0;padding:0;-webkit-tap-highlight-color:transparent}
:root{
  --bg:#0a0a0a;--card:#141414;--border:#222;--accent:#f97316;
  --green:#4ade80;--yellow:#facc15;--red:#f87171;--teal:#2dd4bf;
  --text:#e5e5e5;--muted:#666;--input:#1c1c1c;--radius:12px
}
html,body{background:var(--bg);color:var(--text);font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;min-height:100vh}
body{padding:0 0 80px 0}

/* HEADER */
.header{background:var(--card);border-bottom:1px solid var(--border);padding:16px 20px;position:sticky;top:0;z-index:100}
.header h1{font-size:1.1rem;font-weight:700;color:var(--accent)}
.header .date-row{display:flex;align-items:center;gap:10px;margin-top:6px}
.header input[type=date]{background:var(--input);border:1px solid var(--border);border-radius:8px;color:var(--text);font-size:.85rem;padding:6px 10px;flex:1}

/* SECTIONS */
.section{margin:16px 12px 0;background:var(--card);border-radius:var(--radius);border:1px solid var(--border);overflow:hidden}
.section-title{padding:14px 16px 10px;font-size:.65rem;text-transform:uppercase;letter-spacing:1.5px;color:var(--muted);border-bottom:1px solid var(--border)}

/* ROWS */
.row{display:flex;align-items:center;padding:12px 16px;border-bottom:1px solid #1a1a1a;gap:12px}
.row:last-child{border-bottom:none}
.row label{font-size:.88rem;color:var(--text);flex:1;line-height:1.3}
.row .hint{font-size:.72rem;color:var(--muted);margin-top:2px}
.row .right{display:flex;align-items:center;gap:8px;flex-shrink:0}
.row input[type=number],.row input[type=time],.row input[type=text]{
  background:var(--input);border:1px solid var(--border);border-radius:8px;
  color:var(--text);font-size:.95rem;padding:8px 10px;
  width:100px;text-align:right;-moz-appearance:textfield
}
.row input[type=time]{width:110px;text-align:center}
.row input:focus{outline:none;border-color:var(--accent)}
.row input::-webkit-outer-spin-button,.row input::-webkit-inner-spin-button{-webkit-appearance:none}
.unit{font-size:.75rem;color:var(--muted);width:28px}

/* SCORE BUTTONS */
.score-row{display:flex;align-items:center;padding:12px 16px;border-bottom:1px solid #1a1a1a;gap:8px;flex-wrap:wrap}
.score-row:last-child{border-bottom:none}
.score-label{font-size:.88rem;color:var(--text);flex:1 1 100%;margin-bottom:8px}
.score-btn{flex:1;padding:9px 4px;background:var(--input);border:1px solid var(--border);border-radius:8px;color:var(--muted);font-size:.9rem;font-weight:600;cursor:pointer;text-align:center;transition:all .15s}
.score-btn.active{background:var(--accent);border-color:var(--accent);color:#000}
.score-btn:hover{border-color:var(--accent);color:var(--text)}

/* SUBMIT */
.submit-wrap{padding:20px 12px}
.submit-btn{width:100%;padding:16px;background:var(--accent);border:none;border-radius:var(--radius);color:#000;font-size:1rem;font-weight:700;cursor:pointer;letter-spacing:.5px}
.submit-btn:active{opacity:.85}
.submit-btn:disabled{opacity:.4;cursor:not-allowed}

/* RESULTS */
#results{margin:0 12px 16px;display:none}
.result-card{background:var(--card);border:1px solid var(--border);border-radius:var(--radius);padding:16px;margin-bottom:12px}
.result-card h3{font-size:.65rem;text-transform:uppercase;letter-spacing:1.5px;color:var(--muted);margin-bottom:12px}
.score-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:8px}
.score-box{background:var(--input);border-radius:10px;padding:12px 8px;text-align:center}
.score-box .val{font-size:1.4rem;font-weight:700;line-height:1}
.score-box .lbl{font-size:.65rem;color:var(--muted);margin-top:4px}
.green{color:var(--green)}.yellow{color:var(--yellow)}.red{color:var(--red)}.grey{color:var(--muted)}
.notice{display:flex;gap:10px;padding:10px 0;border-bottom:1px solid #1a1a1a;align-items:flex-start}
.notice:last-child{border-bottom:none}
.notice .dot{width:8px;height:8px;border-radius:50%;flex-shrink:0;margin-top:5px}
.dot-stop{background:var(--red)}.dot-warn{background:var(--yellow)}.dot-info{background:var(--teal)}
.notice .msg{font-size:.85rem;line-height:1.4;color:var(--text)}
.sleep-grid{display:grid;grid-template-columns:1fr 1fr;gap:8px}
.sleep-item{background:var(--input);border-radius:8px;padding:10px}
.sleep-item .val{font-size:1rem;font-weight:600}
.sleep-item .lbl{font-size:.65rem;color:var(--muted);margin-top:2px}
.meal-row{display:flex;align-items:center;padding:8px 0;border-bottom:1px solid #1a1a1a;gap:8px}
.meal-row:last-child{border-bottom:none}
.meal-lbl{font-size:.82rem;color:var(--muted);width:90px;flex-shrink:0}
.macro-chip{background:var(--input);border-radius:6px;padding:4px 8px;font-size:.78rem;font-weight:600}
.chip-p{color:#60a5fa}.chip-c{color:#facc15}.chip-f{color:#fb923c}
.insight{font-size:.82rem;color:var(--muted);padding:6px 0;border-bottom:1px solid #1a1a1a;line-height:1.4}
.insight:last-child{border-bottom:none}
.reco-row{display:flex;justify-content:space-between;align-items:center;padding:8px 0;border-bottom:1px solid #1a1a1a;font-size:.88rem}
.reco-row:last-child{border-bottom:none}
.reco-row .lbl{color:var(--muted)}
.reco-row .val{font-weight:600;color:var(--accent)}
.toast{position:fixed;bottom:30px;left:50%;transform:translateX(-50%);background:#1a1a1a;border:1px solid var(--border);border-radius:10px;padding:12px 20px;font-size:.85rem;color:var(--text);z-index:999;display:none;white-space:nowrap}
.uuid-row{padding:10px 16px;font-size:.7rem;color:var(--muted);display:flex;align-items:center;gap:8px;border-top:1px solid var(--border)}
.uuid-row input{background:transparent;border:none;color:var(--muted);font-size:.7rem;font-family:monospace;flex:1;min-width:0}
.csv-btn{background:transparent;border:1px solid var(--border);border-radius:8px;color:var(--muted);font-size:.75rem;padding:5px 10px;text-decoration:none;white-space:nowrap}
.csv-btn:hover{border-color:var(--accent);color:var(--accent)}
</style>
</head>
<body>

<div class="header">
  <div style="display:flex;align-items:center;justify-content:space-between">
    <h1>⚡ ArcForge Daily Log</h1>
    <a href="/log/export" download="arcforge_daily_log.csv" class="csv-btn">↓ CSV</a>
  </div>
  <div class="date-row">
    <input type="date" id="log-date">
  </div>
</div>

<!-- RESULTS (shown after submit) -->
<div id="results">
  <div class="result-card" id="r-scores" style="display:none">
    <h3>Oscillator Scores</h3>
    <div class="score-grid" id="score-grid"></div>
  </div>
  <div class="result-card" id="r-reco" style="display:none">
    <h3>Today's Plan</h3>
    <div id="reco-body"></div>
  </div>
  <div class="result-card" id="r-notices" style="display:none">
    <h3>Notices</h3>
    <div id="notices-body"></div>
  </div>
  <div class="result-card" id="r-sleep" style="display:none">
    <h3>Sleep Summary</h3>
    <div class="sleep-grid" id="sleep-grid"></div>
  </div>
  <div class="result-card" id="r-meals" style="display:none">
    <h3>Meal Timing Targets</h3>
    <div id="meals-body"></div>
  </div>
  <div class="result-card" id="r-insights" style="display:none">
    <h3>Insights</h3>
    <div id="insights-body"></div>
  </div>
</div>

<!-- SLEEP -->
<div class="section">
  <div class="section-title">Sleep</div>

  <div class="row">
    <div><label>Sleep Onset<div class="hint">Time you fell asleep (military)</div></label></div>
    <div class="right">
      <input type="time" id="sleep_onset" placeholder="23:20">
    </div>
  </div>

  <div class="row">
    <div><label>Wake Time<div class="hint">Time you woke up (military)</div></label></div>
    <div class="right">
      <input type="time" id="sleep_wake" placeholder="06:30">
    </div>
  </div>

  <div class="row">
    <div><label>REM<div class="hint">e.g. 01:34 = 1h 34m</div></label></div>
    <div class="right">
      <input type="time" id="rem" placeholder="01:30">
      <span class="unit">h:m</span>
    </div>
  </div>

  <div class="row">
    <div><label>Core Sleep<div class="hint">e.g. 03:10 = 3h 10m</div></label></div>
    <div class="right">
      <input type="time" id="core" placeholder="03:00">
      <span class="unit">h:m</span>
    </div>
  </div>

  <div class="row">
    <div><label>Deep Sleep<div class="hint">e.g. 01:20 = 1h 20m</div></label></div>
    <div class="right">
      <input type="time" id="deep" placeholder="01:00">
      <span class="unit">h:m</span>
    </div>
  </div>

  <div class="row">
    <div><label>Awake in Bed<div class="hint">e.g. 00:15 = 15 min</div></label></div>
    <div class="right">
      <input type="time" id="awake" placeholder="00:10">
      <span class="unit">h:m</span>
    </div>
  </div>
</div>

<!-- BIOMETRICS -->
<div class="section">
  <div class="section-title">Morning Biometrics</div>

  <div class="row">
    <label>HRV</label>
    <div class="right"><input type="number" id="hrv" placeholder="55" step="0.1"><span class="unit">ms</span></div>
  </div>

  <div class="row">
    <label>Resting HR</label>
    <div class="right"><input type="number" id="rhr" placeholder="58" step="0.1"><span class="unit">bpm</span></div>
  </div>

  <div class="row">
    <label>Morning Temp</label>
    <div class="right"><input type="number" id="temp_f" placeholder="97.4" step="0.1"><span class="unit">°F</span></div>
  </div>

  <div class="row">
    <label>Body Weight</label>
    <div class="right"><input type="number" id="weight" placeholder="160" step="0.1"><span class="unit">lb</span></div>
  </div>
</div>

<!-- BODY COMP -->
<div class="section">
  <div class="section-title">Body Composition <span style="color:var(--muted);font-size:.6rem">(weekly)</span></div>

  <div class="row">
    <div><label>Body Fat %<div class="hint">e.g. 14.5</div></label></div>
    <div class="right"><input type="number" id="bf_pct" placeholder="14.5" step="0.1"><span class="unit">%</span></div>
  </div>

  <div class="row">
    <div><label>Skeletal Muscle %<div class="hint">from InBody / scale</div></label></div>
    <div class="right"><input type="number" id="sm_pct" placeholder="42.0" step="0.1"><span class="unit">%</span></div>
  </div>

  <div class="row">
    <div><label>Waist at Navel<div class="hint">weekly tape measure</div></label></div>
    <div class="right"><input type="number" id="waist" placeholder="34.0" step="0.1"><span class="unit">in</span></div>
  </div>
</div>

<!-- SUBJECTIVE -->
<div class="section">
  <div class="section-title">Subjective Scores — tap to rate</div>

  <div class="score-row" id="sr-libido">
    <div class="score-label">Libido <span style="color:var(--muted);font-size:.75rem">(1–5)</span></div>
    <button class="score-btn" data-field="libido" data-val="1">1</button>
    <button class="score-btn" data-field="libido" data-val="2">2</button>
    <button class="score-btn" data-field="libido" data-val="3">3</button>
    <button class="score-btn" data-field="libido" data-val="4">4</button>
    <button class="score-btn" data-field="libido" data-val="5">5</button>
  </div>

  <div class="score-row" id="sr-erection">
    <div class="score-label">Morning Erection <span style="color:var(--muted);font-size:.75rem">(0–3)</span></div>
    <button class="score-btn" data-field="erection" data-val="0">0</button>
    <button class="score-btn" data-field="erection" data-val="1">1</button>
    <button class="score-btn" data-field="erection" data-val="2">2</button>
    <button class="score-btn" data-field="erection" data-val="3">3</button>
  </div>

  <div class="score-row" id="sr-mood">
    <div class="score-label">Mood <span style="color:var(--muted);font-size:.75rem">(1–5)</span></div>
    <button class="score-btn" data-field="mood" data-val="1">1</button>
    <button class="score-btn" data-field="mood" data-val="2">2</button>
    <button class="score-btn" data-field="mood" data-val="3">3</button>
    <button class="score-btn" data-field="mood" data-val="4">4</button>
    <button class="score-btn" data-field="mood" data-val="5">5</button>
  </div>

  <div class="score-row" id="sr-drive">
    <div class="score-label">Mental Drive <span style="color:var(--muted);font-size:.75rem">(1–5)</span></div>
    <button class="score-btn" data-field="drive" data-val="1">1</button>
    <button class="score-btn" data-field="drive" data-val="2">2</button>
    <button class="score-btn" data-field="drive" data-val="3">3</button>
    <button class="score-btn" data-field="drive" data-val="4">4</button>
    <button class="score-btn" data-field="drive" data-val="5">5</button>
  </div>

  <div class="score-row" id="sr-soreness">
    <div class="score-label">Soreness <span style="color:var(--muted);font-size:.75rem">(1=none, 5=wrecked)</span></div>
    <button class="score-btn" data-field="soreness" data-val="1">1</button>
    <button class="score-btn" data-field="soreness" data-val="2">2</button>
    <button class="score-btn" data-field="soreness" data-val="3">3</button>
    <button class="score-btn" data-field="soreness" data-val="4">4</button>
    <button class="score-btn" data-field="soreness" data-val="5">5</button>
  </div>

  <div class="score-row" id="sr-joints">
    <div class="score-label">Joint Friction <span style="color:var(--muted);font-size:.75rem">(1=smooth, 5=grinding)</span></div>
    <button class="score-btn" data-field="joints" data-val="1">1</button>
    <button class="score-btn" data-field="joints" data-val="2">2</button>
    <button class="score-btn" data-field="joints" data-val="3">3</button>
    <button class="score-btn" data-field="joints" data-val="4">4</button>
    <button class="score-btn" data-field="joints" data-val="5">5</button>
  </div>

  <div class="score-row" id="sr-stress">
    <div class="score-label">Stress Load <span style="color:var(--muted);font-size:.75rem">(1=calm, 5=maxed)</span></div>
    <button class="score-btn" data-field="stress" data-val="1">1</button>
    <button class="score-btn" data-field="stress" data-val="2">2</button>
    <button class="score-btn" data-field="stress" data-val="3">3</button>
    <button class="score-btn" data-field="stress" data-val="4">4</button>
    <button class="score-btn" data-field="stress" data-val="5">5</button>
  </div>
</div>

<!-- NUTRITION (actual eaten today) -->
<div class="section">
  <div class="section-title">Nutrition — Actual Today</div>

  <div class="row">
    <label>Calories</label>
    <div class="right"><input type="number" id="kcal" placeholder="2600" step="1"><span class="unit">kcal</span></div>
  </div>

  <div class="row">
    <label>Protein</label>
    <div class="right"><input type="number" id="protein" placeholder="175" step="1"><span class="unit">g</span></div>
  </div>

  <div class="row">
    <label>Carbs</label>
    <div class="right"><input type="number" id="carbs" placeholder="250" step="1"><span class="unit">g</span></div>
  </div>

  <div class="row">
    <label>Fat</label>
    <div class="right"><input type="number" id="fat" placeholder="90" step="1"><span class="unit">g</span></div>
  </div>
</div>

<!-- SUBMIT -->
<div class="submit-wrap">
  <button class="submit-btn" id="submit-btn" onclick="submitLog()">Submit Daily Log</button>
</div>

<!-- UUID row -->
<div class="uuid-row">
  <span>Your ID:</span>
  <input type="text" id="uuid-display" readonly>
</div>

<div class="toast" id="toast"></div>

<script>
// ── UUID management ──────────────────────────────────────────────────────────
function genUUID(){
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g,c=>{
    const r=Math.random()*16|0;return(c==='x'?r:(r&0x3|0x8)).toString(16);
  });
}
let USER_ID = localStorage.getItem('arcforge_uid');
if(!USER_ID){ USER_ID=genUUID(); localStorage.setItem('arcforge_uid',USER_ID); }
document.getElementById('uuid-display').value = USER_ID;

// Ensure user exists in brain
fetch('/users/ensure',{method:'POST',headers:{'Content-Type':'application/json'},
  body:JSON.stringify({expo_user_id:USER_ID})}).catch(()=>{});

// ── Date default ─────────────────────────────────────────────────────────────
const dateEl = document.getElementById('log-date');
const today = new Date();
const pad = n=>String(n).padStart(2,'0');
dateEl.value = `${today.getFullYear()}-${pad(today.getMonth()+1)}-${pad(today.getDate())}`;

// ── Score buttons ─────────────────────────────────────────────────────────────
const scores = {};
document.querySelectorAll('.score-btn').forEach(btn=>{
  btn.addEventListener('click',()=>{
    const f=btn.dataset.field;
    document.querySelectorAll(`[data-field="${f}"]`).forEach(b=>b.classList.remove('active'));
    btn.classList.add('active');
    scores[f]=parseInt(btn.dataset.val);
  });
});

// ── Time helpers ──────────────────────────────────────────────────────────────
// HH:MM → "HH:MM" string for onset/wake (brain accepts this directly)
function timeToHHMM(val){ return val||null; }

// HH:MM → H.MM decimal for stage durations (brain normalises 1.34 → 94min)
function timeToDecimal(val){
  if(!val) return null;
  const [h,m]=val.split(':').map(Number);
  if(isNaN(h)||isNaN(m)) return null;
  // encode as H.MM — brain reads frac*100 as minutes when 01-59
  return parseFloat(`${h}.${String(m).padStart(2,'0')}`);
}

// ── Submit ────────────────────────────────────────────────────────────────────
async function submitLog(){
  const btn = document.getElementById('submit-btn');
  btn.disabled = true;
  btn.textContent = 'Saving…';

  const num = id => { const v=document.getElementById(id).value; return v===''?null:parseFloat(v); };

  const body = {
    expo_user_id: USER_ID,
    date: dateEl.value,

    // sleep times
    sleep_onset_hhmm: timeToHHMM(document.getElementById('sleep_onset').value),
    sleep_wake_hhmm:  timeToHHMM(document.getElementById('sleep_wake').value),

    // sleep stages — HH:MM → H.MM decimal
    sleep_rem_min:   timeToDecimal(document.getElementById('rem').value),
    sleep_core_min:  timeToDecimal(document.getElementById('core').value),
    sleep_deep_min:  timeToDecimal(document.getElementById('deep').value),
    sleep_awake_min: timeToDecimal(document.getElementById('awake').value),

    // biometrics
    hrv_ms:          num('hrv'),
    resting_hr_bpm:  num('rhr'),
    morning_temp_f:  num('temp_f'),
    body_weight_lb:  num('weight'),

    // body comp
    body_fat_pct:       num('bf_pct'),
    skeletal_muscle_pct: num('sm_pct'),
    waist_at_navel_in:  num('waist'),

    // subjective
    libido_score:        scores['libido']   ?? null,
    morning_erection_score: scores['erection'] ?? null,
    mood_stability_score: scores['mood']    ?? null,
    mental_drive_score:  scores['drive']    ?? null,
    soreness_score:      scores['soreness'] ?? null,
    joint_friction_score: scores['joints']  ?? null,
    stress_load_score:   scores['stress']   ?? null,

    // nutrition
    kcal_actual:      num('kcal'),
    protein_g_actual: num('protein'),
    carbs_g_actual:   num('carbs'),
    fat_g_actual:     num('fat'),
  };

  // strip nulls
  Object.keys(body).forEach(k=>{ if(body[k]===null||body[k]===undefined) delete body[k]; });

  try {
    const res = await fetch('/vitals/daily-log',{
      method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)
    });
    const json = await res.json();
    if(!res.ok){ showToast('Error: '+(json.detail||res.status)); return; }
    renderResults(json);
    showToast('Logged ✓');
    // scroll to results
    document.getElementById('results').scrollIntoView({behavior:'smooth'});
  } catch(e){
    showToast('Network error — check connection');
  } finally {
    btn.disabled=false;
    btn.textContent='Submit Daily Log';
  }
}

// ── Render results ────────────────────────────────────────────────────────────
function renderResults(json){
  const ds = json.displaySpec;
  const rec = json.recommendation;
  document.getElementById('results').style.display='block';

  // Score cards
  if(ds.scoreCards?.length){
    const grid = document.getElementById('score-grid');
    grid.innerHTML = ds.scoreCards.map(c=>`
      <div class="score-box">
        <div class="val ${c.color}">${Math.round(c.score)}</div>
        <div class="lbl">${c.label.replace(' ','\n')}</div>
      </div>`).join('');
    document.getElementById('r-scores').style.display='block';
  }

  // Recommendation
  if(rec){
    document.getElementById('reco-body').innerHTML = `
      <div class="reco-row"><span class="lbl">Lift</span><span class="val">${fmt(rec.recommendedLiftMode)}</span></div>
      <div class="reco-row"><span class="lbl">Cardio</span><span class="val">${fmt(rec.recommendedCardioMode)}</span></div>
      <div class="reco-row"><span class="lbl">Macro Day</span><span class="val">${fmt(rec.recommendedMacroDayType)}</span></div>
      ${rec.macroTargets ? `
      <div class="reco-row"><span class="lbl">Calories</span><span class="val">${rec.macroTargets.kcalTarget ?? '—'} kcal</span></div>
      <div class="reco-row"><span class="lbl">Protein</span><span class="val">${rec.macroTargets.proteinG ?? '—'} g</span></div>
      <div class="reco-row"><span class="lbl">Carbs</span><span class="val">${rec.macroTargets.carbsG ?? '—'} g</span></div>
      <div class="reco-row"><span class="lbl">Fat</span><span class="val">${rec.macroTargets.fatG ?? '—'} g</span></div>` : ''}
    `;
    document.getElementById('r-reco').style.display='block';
  }

  // Notices
  if(ds.notices?.length){
    document.getElementById('notices-body').innerHTML = ds.notices.map(n=>`
      <div class="notice">
        <div class="dot dot-${n.type}"></div>
        <div class="msg">${n.message}</div>
      </div>`).join('');
    document.getElementById('r-notices').style.display='block';
  }

  // Sleep summary
  const sl = ds.sleepSummary;
  if(sl){
    const items = [
      sl.duration, sl.efficiency, sl.midpoint, sl.timeInBed,
      sl.stages?.rem, sl.stages?.core, sl.stages?.deep, sl.stages?.awake
    ].filter(x=>x?.display);
    if(items.length){
      document.getElementById('sleep-grid').innerHTML = items.map(i=>`
        <div class="sleep-item"><div class="val">${i.display}</div><div class="lbl">${i.label}</div></div>`).join('');
      document.getElementById('r-sleep').style.display='block';
    }
  }

  // Meal timing
  const meals = ds.mealTiming?.sections?.filter(m=>m.proteinG||m.carbsG||m.fatG);
  if(meals?.length){
    document.getElementById('meals-body').innerHTML = meals.map(m=>`
      <div class="meal-row">
        <span class="meal-lbl">${m.label}</span>
        ${m.proteinG ? `<span class="macro-chip chip-p">${m.proteinG}g P</span>` : ''}
        ${m.carbsG   ? `<span class="macro-chip chip-c">${m.carbsG}g C</span>`   : ''}
        ${m.fatG     ? `<span class="macro-chip chip-f">${m.fatG}g F</span>`     : ''}
      </div>`).join('');
    document.getElementById('r-meals').style.display='block';
  }

  // Insights
  if(ds.insights?.length){
    document.getElementById('insights-body').innerHTML = ds.insights.map(i=>`
      <div class="insight">• ${i}</div>`).join('');
    document.getElementById('r-insights').style.display='block';
  }
}

function fmt(s){ return s ? s.replace(/_/g,' ').replace(/\b\w/g,c=>c.toUpperCase()) : '—'; }
function showToast(msg){
  const t=document.getElementById('toast');
  t.textContent=msg; t.style.display='block';
  clearTimeout(t._timer);
  t._timer=setTimeout(()=>t.style.display='none',3000);
}
</script>
</body>
</html>"""


@router.get("/log", response_class=HTMLResponse, include_in_schema=False)
def daily_log_page():
    return _HTML

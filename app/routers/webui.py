from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import desc
from pathlib import Path
from typing import Optional
import datetime

from app.database import get_db
from app.vitals_models import (
    VitalsDailyLog, VitalsCardioSession, VitalsLiftSession, LiftExerciseEntry
)

router = APIRouter(tags=["webui"])

CSV_PATH = Path(__file__).parent.parent.parent / "data" / "daily_log.csv"

# ── Shared design constants ────────────────────────────────────────────────────
_EXPO_USER_ID = "beeb9b83-58d3-4a22-a1a7-a252fd86a0e0"

_CSS_VARS = """
*{box-sizing:border-box;margin:0;padding:0;-webkit-tap-highlight-color:transparent}
:root{
  --bg:#0a0a0a;--card:#141414;--border:#222;--accent:#f97316;
  --green:#4ade80;--yellow:#facc15;--red:#f87171;--teal:#2dd4bf;
  --blue:#60a5fa;--purple:#a78bfa;
  --text:#e5e5e5;--muted:#666;--input:#1c1c1c;--radius:12px
}
html,body{background:var(--bg);color:var(--text);font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;min-height:100vh}
body{padding:0 0 88px 0}
.header{background:var(--card);border-bottom:1px solid var(--border);padding:16px 20px;position:sticky;top:0;z-index:100}
.header-top{display:flex;align-items:center;justify-content:space-between}
.header h1{font-size:1.1rem;font-weight:700;color:var(--accent)}
.date-row{display:flex;align-items:center;gap:10px;margin-top:10px}
.date-row input[type=date]{background:var(--input);border:1px solid var(--border);border-radius:8px;color:var(--text);font-size:.95rem;padding:8px 12px;flex:1;text-align:center}
.date-nav{background:var(--input);border:1px solid var(--border);border-radius:8px;color:var(--text);font-size:1rem;padding:7px 14px;cursor:pointer;flex-shrink:0}
.date-nav:active{background:var(--border)}
.section{margin:16px 12px 0;background:var(--card);border-radius:var(--radius);border:1px solid var(--border);overflow:hidden}
.section-title{padding:14px 16px 10px;font-size:.65rem;text-transform:uppercase;letter-spacing:1.5px;color:var(--muted);border-bottom:1px solid var(--border)}
.row{display:flex;align-items:center;padding:12px 16px;border-bottom:1px solid #1a1a1a;gap:12px}
.row:last-child{border-bottom:none}
.row label{font-size:.88rem;color:var(--text);flex:1;line-height:1.3}
.row .hint{font-size:.72rem;color:var(--muted);margin-top:2px}
.row .right{display:flex;align-items:center;gap:8px;flex-shrink:0}
.row input[type=number],.row input[type=time],.row input[type=text],.row select{
  background:var(--input);border:1px solid var(--border);border-radius:8px;
  color:var(--text);font-size:.95rem;padding:8px 10px;
  width:100px;text-align:right;-moz-appearance:textfield
}
.row select{width:auto;text-align:left;padding-right:28px}
.row input[type=time]{width:110px;text-align:center}
.row input:focus,.row select:focus{outline:none;border-color:var(--accent)}
.row input::-webkit-outer-spin-button,.row input::-webkit-inner-spin-button{-webkit-appearance:none}
.unit{font-size:.75rem;color:var(--muted);width:28px}
.score-btn{flex:1;padding:9px 4px;background:var(--input);border:1px solid var(--border);border-radius:8px;color:var(--muted);font-size:.9rem;font-weight:600;cursor:pointer;text-align:center;transition:all .15s}
.score-btn.active{background:var(--accent);border-color:var(--accent);color:#000}
.score-row{display:flex;align-items:center;padding:12px 16px;border-bottom:1px solid #1a1a1a;gap:8px;flex-wrap:wrap}
.score-row:last-child{border-bottom:none}
.score-label{font-size:.88rem;color:var(--text);flex:1 1 100%;margin-bottom:8px}
.submit-wrap{padding:20px 12px}
.submit-btn{width:100%;padding:16px;background:var(--accent);border:none;border-radius:var(--radius);color:#000;font-size:1rem;font-weight:700;cursor:pointer;letter-spacing:.5px}
.submit-btn:active{opacity:.85}
.submit-btn:disabled{opacity:.4;cursor:not-allowed}
.toast{position:fixed;bottom:96px;left:50%;transform:translateX(-50%);background:#1a1a1a;border:1px solid var(--border);border-radius:10px;padding:12px 20px;font-size:.85rem;color:var(--text);z-index:999;display:none;white-space:nowrap}
/* ── Bottom nav ── */
.bottom-nav{position:fixed;bottom:0;left:0;right:0;background:var(--card);border-top:1px solid var(--border);display:flex;padding:8px 0 max(8px,env(safe-area-inset-bottom));z-index:200}
.nav-item{flex:1;display:flex;flex-direction:column;align-items:center;gap:3px;padding:4px 0;text-decoration:none;color:var(--muted);font-size:.6rem;letter-spacing:.5px;text-transform:uppercase;transition:color .15s}
.nav-item.active,.nav-item:active{color:var(--accent)}
.nav-icon{font-size:1.35rem;line-height:1}
/* ── Cards / history ── */
.hist-card{background:var(--card);border:1px solid var(--border);border-radius:var(--radius);padding:14px 16px;margin:12px 12px 0}
.hist-card h3{font-size:.65rem;text-transform:uppercase;letter-spacing:1.5px;color:var(--muted);margin-bottom:10px}
.hist-row{display:flex;justify-content:space-between;align-items:center;padding:7px 0;border-bottom:1px solid #1a1a1a;font-size:.85rem}
.hist-row:last-child{border-bottom:none}
.hist-lbl{color:var(--muted)}
.hist-val{font-weight:600}
.chip{display:inline-block;font-size:.68rem;padding:2px 8px;border-radius:6px;font-weight:600}
.chip-build{background:#1a2a1a;color:var(--green)}
.chip-surge{background:#2a1a0a;color:var(--accent)}
.chip-reset{background:#1a1a2a;color:var(--blue)}
.chip-resensitize{background:#2a1a2a;color:var(--purple)}
.chip-zone2{background:#0a2a2a;color:var(--teal)}
.chip-zone3{background:#2a1a0a;color:var(--yellow)}
.chip-recovery{background:#1a1a1a;color:var(--muted)}
.stat-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin:12px 12px 0}
.stat-box{background:var(--card);border:1px solid var(--border);border-radius:var(--radius);padding:14px 10px;text-align:center}
.stat-val{font-size:1.5rem;font-weight:700;line-height:1;color:var(--accent)}
.stat-lbl{font-size:.62rem;color:var(--muted);margin-top:4px;text-transform:uppercase;letter-spacing:.5px}
.sys-section{margin:12px 12px 0;background:var(--card);border-radius:var(--radius);border:1px solid var(--border);overflow:hidden}
.sys-section-title{padding:12px 16px 8px;font-size:.62rem;text-transform:uppercase;letter-spacing:1.5px;color:var(--muted);border-bottom:1px solid var(--border)}
.spark-row{display:flex;align-items:flex-end;gap:3px;padding:12px 16px;height:60px}
.spark-bar{flex:1;background:var(--accent);border-radius:3px 3px 0 0;min-height:3px;opacity:.8}
.spark-bar.dim{opacity:.3}
"""

_NAV_HTML = lambda active: f"""
<nav class="bottom-nav">
  <a href="/log"    class="nav-item {'active' if active=='log' else ''}"><span class="nav-icon">📋</span>Log</a>
  <a href="/cardio" class="nav-item {'active' if active=='cardio' else ''}"><span class="nav-icon">🏃</span>Cardio</a>
  <a href="/lift"   class="nav-item {'active' if active=='lift' else ''}"><span class="nav-icon">🏋️</span>Lift</a>
  <a href="/system" class="nav-item {'active' if active=='system' else ''}"><span class="nav-icon">⚡</span>System</a>
</nav>"""

_TOAST_JS = """
function showToast(msg,type){
  const t=document.getElementById('toast');
  t.textContent=msg;
  t.style.borderColor=type==='err'?'var(--red)':type==='ok'?'var(--green)':'var(--border)';
  t.style.display='block';
  clearTimeout(t._timer);t._timer=setTimeout(()=>t.style.display='none',3000);
}
"""


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


@router.get("/log/meal-plan", include_in_schema=False)
def get_meal_plan_for_day(day_type: str = "build"):
    """Return the food plan for a given macro day type.
    kcal / P / C / F are computed live from INGREDIENT_MACROS × amounts —
    the hardcoded plan values are only used as labels, never as the source of truth
    for caloric math.
    """
    from app.meal_plan import get_meal_plan, INGREDIENT_MACROS
    plan = get_meal_plan(day_type)
    out = {}
    for win, data in plan.items():
        p = c = f = kcal = 0.0
        for food in data.get("foods", []):
            m = INGREDIENT_MACROS.get(food["name"])
            if m:
                amt = food["amount"]
                p    += round(m["p"]    * amt, 4)
                c    += round(m["c"]    * amt, 4)
                f    += round(m["f"]    * amt, 4)
                kcal += round(m["kcal"] * amt, 4)
        out[win] = {
            **data,
            "P":    round(p,    1),
            "C":    round(c,    1),
            "F":    round(f,    1),
            "kcal": round(kcal, 1),
        }
    return {"dayType": day_type, "plan": out}


@router.get("/log/data", include_in_schema=False)
def get_log_data(expo_user_id: str, date: str, db: Session = Depends(get_db)):
    """Return stored values for a given user+date so the form can pre-fill."""
    row = db.query(VitalsDailyLog).filter(
        VitalsDailyLog.expo_user_id == expo_user_id,
        VitalsDailyLog.date == date,
    ).first()

    if not row:
        return {"found": False}

    def f(v):
        return float(v) if v is not None else None

    def i(v):
        return int(v) if v is not None else None

    # Convert stored stage minutes back to HH:MM for the time input
    def min_to_hhmm(v):
        if v is None:
            return None
        total = int(float(v))
        return f"{total // 60:02d}:{total % 60:02d}"

    return {
        "found": True,
        "sleep_onset_hhmm":    row.sleep_onset_hhmm,
        "sleep_wake_hhmm":     row.sleep_wake_hhmm,
        "sleep_rem_hhmm":      min_to_hhmm(row.sleep_rem_min),
        "sleep_core_hhmm":     min_to_hhmm(row.sleep_core_min),
        "sleep_deep_hhmm":     min_to_hhmm(row.sleep_deep_min),
        "sleep_awake_hhmm":    min_to_hhmm(row.sleep_awake_min),
        "hrv_ms":              f(row.hrv_ms),
        "resting_hr_bpm":      f(row.resting_hr_bpm),
        "morning_temp_f":      f(row.morning_temp_f),
        "body_weight_lb":      f(row.body_weight_lb),
        "body_fat_pct":        f(row.body_fat_pct),
        "skeletal_muscle_pct": f(row.skeletal_muscle_pct),
        "fat_free_mass_lb":    f(row.fat_free_mass_lb),
        "libido_score":        i(row.libido_score),
        "morning_erection_score": i(row.morning_erection_score),
        "mood_stability_score":   i(row.mood_stability_score),
        "mental_drive_score":     i(row.mental_drive_score),
        "soreness_score":         i(row.soreness_score),
        "joint_friction_score":   i(row.joint_friction_score),
        "stress_load_score":      i(row.stress_load_score),
        "waist_at_navel_in":   f(row.waist_at_navel_in),
        "neck_in":             f(row.neck_in),
        "chest_in":            f(row.chest_in),
        "hip_in":              f(row.hip_in),
        "bicep_l_in":          f(row.bicep_l_in),
        "bicep_r_in":          f(row.bicep_r_in),
        "forearm_l_in":        f(row.forearm_l_in),
        "forearm_r_in":        f(row.forearm_r_in),
        "wrist_l_in":          f(row.wrist_l_in),
        "wrist_r_in":          f(row.wrist_r_in),
        "thigh_l_in":          f(row.thigh_l_in),
        "thigh_r_in":          f(row.thigh_r_in),
        "calf_l_in":           f(row.calf_l_in),
        "calf_r_in":           f(row.calf_r_in),
        "ankle_l_in":          f(row.ankle_l_in),
        "ankle_r_in":          f(row.ankle_r_in),
        "kcal_actual":         f(row.kcal_actual),
        "protein_g_actual":    f(row.protein_g_actual),
        "carbs_g_actual":      f(row.carbs_g_actual),
        "fat_g_actual":        f(row.fat_g_actual),
        "meal_actuals_json":      row.meal_actuals_json,
        "meal_adherence_json":    row.meal_adherence_json,
        "recommended_macro_day":  row.recommended_macro_day,
    }


@router.post("/log/meal-actuals", include_in_schema=False)
async def save_meal_actuals(payload: dict, db: Session = Depends(get_db)):
    """Save per-window actual intake JSON and update aggregate CSV columns."""
    import datetime, json as _json
    from app.csv_log import _read_all, _write_all, COLUMNS

    expo_user_id = payload.get("expo_user_id")
    date_str     = payload.get("date")
    actuals_json = payload.get("meal_actuals_json", {})

    if not expo_user_id or not date_str:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="expo_user_id and date required")

    # Upsert into DB
    row = db.query(VitalsDailyLog).filter(
        VitalsDailyLog.expo_user_id == expo_user_id,
        VitalsDailyLog.date == date_str,
    ).first()

    if not row:
        row = VitalsDailyLog(expo_user_id=expo_user_id, date=date_str)
        db.add(row)

    row.meal_actuals_json = actuals_json
    totals = actuals_json.get("totals", {})
    actual_t = totals.get("actual", {})

    # Mirror into whole-day nutrition fields if actuals are present
    if actual_t.get("kcal"):
        row.kcal_actual     = actual_t.get("kcal")
        row.protein_g_actual = actual_t.get("p")
        row.carbs_g_actual   = actual_t.get("c")
        row.fat_g_actual     = actual_t.get("f")

    db.commit()

    # Update CSV aggregate columns for this (user, date)
    logged_at = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    planned_t = totals.get("planned", {})
    delta_t   = totals.get("delta", {})

    extra = {
        "meal_actuals_logged_at":    logged_at,
        "day_kcal_planned":          planned_t.get("kcal", ""),
        "day_kcal_actual_windows":   actual_t.get("kcal", ""),
        "day_kcal_delta":            delta_t.get("kcal", ""),
        "day_p_planned":             planned_t.get("p", ""),
        "day_p_actual":              actual_t.get("p", ""),
        "day_p_delta":               delta_t.get("p", ""),
        "day_c_planned":             planned_t.get("c", ""),
        "day_c_actual":              actual_t.get("c", ""),
        "day_c_delta":               delta_t.get("c", ""),
        "day_f_planned":             planned_t.get("f", ""),
        "day_f_actual":              actual_t.get("f", ""),
        "day_f_delta":               delta_t.get("f", ""),
    }

    existing = _read_all()
    updated = []
    found = False
    for r in existing:
        if r.get("expo_user_id") == expo_user_id and r.get("date") == date_str:
            r.update(extra)
            updated.append(r)
            found = True
        else:
            updated.append(r)
    if not found:
        new_row = {"expo_user_id": expo_user_id, "date": date_str}
        new_row.update(extra)
        updated.append(new_row)
    _write_all(updated)

    return {"ok": True, "totals": totals}


@router.post("/log/meal-adherence", include_in_schema=False)
async def save_meal_adherence(payload: dict, db: Session = Depends(get_db)):
    """Save per-window meal adherence (base/adj/skip) and tally day kcal."""
    import datetime
    from app.csv_log import _read_all, _write_all

    expo_user_id = payload.get("expo_user_id")
    date_str     = payload.get("date")
    adherence    = payload.get("adherence", {})   # {window: {status, base_kcal, adj_kcal, logged_kcal}}
    day_type     = payload.get("day_type", "build")
    total_kcal   = payload.get("total_kcal", 0)
    target_kcal  = payload.get("target_kcal", 0)
    kcal_delta   = payload.get("kcal_delta", 0)

    if not expo_user_id or not date_str:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="expo_user_id and date required")

    row = db.query(VitalsDailyLog).filter(
        VitalsDailyLog.expo_user_id == expo_user_id,
        VitalsDailyLog.date == date_str,
    ).first()
    if not row:
        row = VitalsDailyLog(expo_user_id=expo_user_id, date=date_str)
        db.add(row)

    adherence_doc = dict(adherence)
    adherence_doc["day_type"]    = day_type
    adherence_doc["total_kcal"]  = total_kcal
    adherence_doc["target_kcal"] = target_kcal
    adherence_doc["kcal_delta"]  = kcal_delta

    row.meal_adherence_json = adherence_doc
    # Mirror total into kcal_actual so the brain can read carry-over
    if total_kcal:
        row.kcal_actual = total_kcal

    db.commit()

    # Update CSV
    logged_at = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    extra = {
        "adherence_logged_at":   logged_at,
        "adherence_day_type":    day_type,
        "adherence_kcal_total":  total_kcal,
        "adherence_kcal_target": target_kcal,
        "adherence_kcal_delta":  kcal_delta,
    }
    existing = _read_all()
    updated = []
    found = False
    for r in existing:
        if r.get("expo_user_id") == expo_user_id and r.get("date") == date_str:
            r.update(extra)
            updated.append(r)
            found = True
        else:
            updated.append(r)
    if not found:
        new_row = {"expo_user_id": expo_user_id, "date": date_str}
        new_row.update(extra)
        updated.append(new_row)
    _write_all(updated)

    return {
        "ok": True,
        "total_kcal":  total_kcal,
        "target_kcal": target_kcal,
        "kcal_delta":  kcal_delta,
    }


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
body{padding:0 0 88px 0}

.header{background:var(--card);border-bottom:1px solid var(--border);padding:16px 20px;position:sticky;top:0;z-index:100}
.header-top{display:flex;align-items:center;justify-content:space-between}
.header h1{font-size:1.1rem;font-weight:700;color:var(--accent)}
.date-row{display:flex;align-items:center;gap:10px;margin-top:10px}
.date-row input[type=date]{background:var(--input);border:1px solid var(--border);border-radius:8px;color:var(--text);font-size:.95rem;padding:8px 12px;flex:1;text-align:center}
.date-nav{background:var(--input);border:1px solid var(--border);border-radius:8px;color:var(--text);font-size:1rem;padding:7px 14px;cursor:pointer;flex-shrink:0}
.date-nav:active{background:var(--border)}

.section{margin:16px 12px 0;background:var(--card);border-radius:var(--radius);border:1px solid var(--border);overflow:hidden}
.section-title{padding:14px 16px 10px;font-size:.65rem;text-transform:uppercase;letter-spacing:1.5px;color:var(--muted);border-bottom:1px solid var(--border)}

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

.score-row{display:flex;align-items:center;padding:12px 16px;border-bottom:1px solid #1a1a1a;gap:8px;flex-wrap:wrap}
.score-row:last-child{border-bottom:none}
.score-label{font-size:.88rem;color:var(--text);flex:1 1 100%;margin-bottom:8px}
.score-btn{flex:1;padding:9px 4px;background:var(--input);border:1px solid var(--border);border-radius:8px;color:var(--muted);font-size:.9rem;font-weight:600;cursor:pointer;text-align:center;transition:all .15s}
.score-btn.active{background:var(--accent);border-color:var(--accent);color:#000}

.submit-wrap{padding:20px 12px}
.submit-btn{width:100%;padding:16px;background:var(--accent);border:none;border-radius:var(--radius);color:#000;font-size:1rem;font-weight:700;cursor:pointer;letter-spacing:.5px}
.submit-btn:active{opacity:.85}
.submit-btn:disabled{opacity:.4;cursor:not-allowed}

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

.day-status{display:inline-block;font-size:.7rem;padding:3px 8px;border-radius:6px;margin-left:8px;vertical-align:middle}
.status-saved{background:#1a2e1a;color:var(--green)}
.status-blank{background:#1a1a1a;color:var(--muted)}

.toast{position:fixed;bottom:96px;left:50%;transform:translateX(-50%);background:#1a1a1a;border:1px solid var(--border);border-radius:10px;padding:12px 20px;font-size:.85rem;color:var(--text);z-index:999;display:none;white-space:nowrap}
.bottom-nav{position:fixed;bottom:0;left:0;right:0;background:var(--card);border-top:1px solid var(--border);display:flex;padding:8px 0 max(8px,env(safe-area-inset-bottom));z-index:200}
.nav-item{flex:1;display:flex;flex-direction:column;align-items:center;gap:3px;padding:4px 0;text-decoration:none;color:var(--muted);font-size:.6rem;letter-spacing:.5px;text-transform:uppercase;transition:color .15s}
.nav-item.active{color:var(--accent)}
.nav-icon{font-size:1.35rem;line-height:1}
.uuid-row{padding:10px 16px;font-size:.7rem;color:var(--muted);display:flex;align-items:center;gap:8px;border-top:1px solid var(--border)}
.uuid-row input{background:transparent;border:none;color:var(--muted);font-size:.7rem;font-family:monospace;flex:1;min-width:0}
.csv-btn{background:transparent;border:1px solid var(--border);border-radius:8px;color:var(--muted);font-size:.75rem;padding:5px 10px;text-decoration:none;white-space:nowrap}
.csv-btn:hover{border-color:var(--accent);color:var(--accent)}
.prep-window{margin-bottom:18px;border:1px solid #1e1e1e;border-radius:10px;overflow:hidden}
.prep-window:last-child{margin-bottom:0}
.prep-header{display:flex;justify-content:space-between;align-items:center;padding:8px 12px;background:#111;border-bottom:1px solid #1e1e1e}
.prep-win-name{font-size:.82rem;font-weight:700;color:var(--accent)}
.prep-win-time{font-size:.72rem;color:var(--muted);font-variant-numeric:tabular-nums}
.prep-planned-row{font-size:.68rem;padding:5px 12px;background:#0f0f0f;color:var(--muted);border-bottom:1px solid #1a1a1a;letter-spacing:.3px}
.prep-ingredient{display:grid;grid-template-columns:1fr auto auto auto;align-items:center;gap:8px;padding:8px 12px;border-bottom:1px solid #141414}
.prep-ingredient:last-of-type{border-bottom:none}
.ing-name{font-size:.85rem;color:var(--text)}
.ing-planned-qty{font-size:.78rem;color:var(--muted);text-align:right;white-space:nowrap}
.ing-actual-input{width:64px;background:#1c1c1c;border:1px solid #2a2a2a;border-radius:6px;color:var(--text);font-size:.88rem;font-weight:600;padding:4px 6px;text-align:center;-moz-appearance:textfield}
.ing-actual-input::-webkit-inner-spin-button,.ing-actual-input::-webkit-outer-spin-button{-webkit-appearance:none}
.ing-actual-input:focus{outline:none;border-color:var(--accent)}
.ing-actual-input.changed{border-color:#facc15;color:#facc15}
.ing-unit{font-size:.72rem;color:var(--muted);white-space:nowrap}
.window-delta{padding:6px 12px;background:#0d0d0d;font-size:.72rem;display:flex;gap:10px;flex-wrap:wrap;align-items:center}
.window-delta .dv{font-weight:600}
.dv-zero{color:#333}
.dv-pos{color:#4ade80}
.dv-neg{color:#f87171}
.delta-label{color:#333;font-size:.65rem;text-transform:uppercase;letter-spacing:.5px}
.prep-intel-note{padding:10px 12px;font-size:.78rem;color:var(--muted);font-style:italic;border-top:1px dashed #1a1a1a}
.prep-intel-row{display:flex;align-items:center;justify-content:space-between;padding:8px 12px}
.day-totals-bar{background:#111;border:1px solid #1e1e1e;border-radius:10px;padding:12px;margin-top:16px}
.day-totals-bar h4{font-size:.72rem;color:var(--muted);text-transform:uppercase;letter-spacing:.5px;margin-bottom:10px}
.day-totals-row{display:grid;grid-template-columns:80px repeat(3,1fr);gap:4px;margin-bottom:4px;font-size:.75rem}
.day-totals-row:last-child{margin-bottom:0}
.dt-lbl{color:var(--muted)}
.dt-val{text-align:right;font-variant-numeric:tabular-nums;font-weight:600}
.log-actuals-btn{width:100%;margin-top:16px;padding:14px;background:var(--accent);color:#fff;border:none;border-radius:10px;font-size:.95rem;font-weight:700;letter-spacing:.5px;cursor:pointer}
.log-actuals-btn:active{opacity:.8}
.log-actuals-btn:disabled{background:#333;color:#666;cursor:not-allowed}
.meas-bilateral{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:2px}
.meas-side{background:var(--input);border-radius:8px;padding:8px 10px;display:flex;align-items:center;gap:8px}
.meas-side-lbl{font-size:.68rem;font-weight:700;color:var(--muted);width:12px;flex-shrink:0}
.meas-side input{background:transparent;border:none;color:var(--text);font-size:.95rem;width:100%;min-width:0;font-weight:600}
.meas-side input:focus{outline:none}
.meas-side input::placeholder{color:#333;font-weight:400}
.meas-group-lbl{font-size:.68rem;color:var(--muted);text-transform:uppercase;letter-spacing:.6px;padding:10px 0 4px;margin:0}
/* ── Meal Prep & Adherence ── */
.adh-badge{font-size:.7rem;font-weight:600;background:#1c1c1c;color:var(--accent);padding:2px 8px;border-radius:20px;margin-left:8px;vertical-align:middle;text-transform:capitalize}
.adh-row{padding:14px 0;border-bottom:1px solid var(--border)}
.adh-row:last-child{border-bottom:none}
.adh-win-label{display:flex;align-items:baseline;gap:8px;margin-bottom:10px}
.adh-win-name{font-size:.95rem;font-weight:700;color:var(--text)}
.adh-win-time{font-size:.75rem;color:var(--muted);font-variant-numeric:tabular-nums}
.adh-intel-note{font-size:.65rem;color:var(--muted);margin-left:4px}
/* ingredient prep card */
.adh-foods{display:flex;gap:1px;margin-bottom:10px;border-radius:10px;overflow:hidden;border:1px solid #222}
.adh-foods-col{flex:1;background:#111;padding:10px 11px}
.adh-foods-col+.adh-foods-col{border-left:1px solid #222}
.adh-foods-hdr{font-size:.62rem;font-weight:800;text-transform:uppercase;letter-spacing:.9px;margin-bottom:8px;padding-bottom:6px;border-bottom:1px solid #222}
.adh-hdr-base{color:var(--green)}
.adh-hdr-adj{color:var(--accent)}
.adh-food-row{display:flex;justify-content:space-between;align-items:baseline;padding:4px 0;border-bottom:1px solid #1a1a1a}
.adh-food-row:last-of-type{border-bottom:none}
.adh-food-name{font-size:.8rem;color:#aaa;flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.adh-food-amt{font-size:.95rem;font-weight:800;color:var(--text);margin-left:6px;white-space:nowrap;font-variant-numeric:tabular-nums}
.adh-foods-kcal{font-size:.7rem;color:var(--muted);text-align:right;margin-top:7px;padding-top:6px;border-top:1px solid #1f1f1f}
/* tap buttons */
.adh-btns{display:flex;gap:6px}
.adh-btn{flex:1;padding:10px 4px;border-radius:9px;border:1.5px solid #2a2a2a;background:#111;color:var(--muted);font-size:.78rem;font-weight:700;cursor:pointer;text-align:center;transition:background .12s,border-color .12s,color .12s;-webkit-tap-highlight-color:transparent;letter-spacing:.2px}
.adh-btn:active{opacity:.7}
.adh-kcal{display:block;font-size:.66rem;font-weight:400;margin-top:2px;color:inherit;opacity:.75}
.adh-btn.adh-base.active{background:#052e16;border-color:#16a34a;color:var(--green)}
.adh-btn.adh-adj.active{background:#431407;border-color:var(--accent);color:var(--accent)}
.adh-btn.adh-skip.active{background:#450a0a;border-color:var(--red);color:var(--red)}
.adh-tally-row{display:flex;justify-content:space-between;align-items:center;padding:14px 0 10px;border-top:1px solid var(--border);margin-top:4px}
.adh-tally-label{font-size:.78rem;font-weight:700;color:var(--muted);text-transform:uppercase;letter-spacing:.5px}
.adh-save-btn{width:100%;padding:14px;background:#111;border:1.5px solid var(--accent);border-radius:var(--radius);color:var(--accent);font-size:1rem;font-weight:700;cursor:pointer;letter-spacing:.4px;margin-top:4px}
.adh-save-btn:active{opacity:.8}
.adh-save-btn:disabled{opacity:.4;cursor:not-allowed}
.adh-carryover{margin-top:14px;background:#071a07;border:1px solid #1a3d1a;border-radius:10px;padding:13px 14px;display:flex;flex-direction:column;gap:5px}
.adh-carry-label{font-size:.68rem;font-weight:700;color:var(--muted);text-transform:uppercase;letter-spacing:.6px;margin-bottom:2px}
</style>
</head>
<body>

<div class="header">
  <div class="header-top">
    <h1>⚡ ArcForge Daily Log</h1>
    <a href="/log/export" download="arcforge_daily_log.csv" class="csv-btn">↓ CSV</a>
  </div>
  <div class="date-row">
    <button class="date-nav" onclick="shiftDate(-1)">‹</button>
    <input type="date" id="log-date" onchange="loadDate()">
    <button class="date-nav" onclick="shiftDate(1)">›</button>
  </div>
</div>

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
  <div class="result-card" id="r-foodplan" style="display:none">
    <h3>Prep Card — What &amp; How Much</h3>
    <div id="foodplan-body"></div>
    <div id="day-totals-bar" style="display:none"></div>
    <button class="log-actuals-btn" id="log-actuals-btn" onclick="logActuals()" style="display:none">Log Actuals</button>
  </div>
</div>

<!-- SLEEP -->
<div class="section">
  <div class="section-title">Sleep</div>
  <div class="row">
    <div><label>Sleep Onset<div class="hint">Time you fell asleep</div></label></div>
    <div class="right"><input type="time" id="sleep_onset"></div>
  </div>
  <div class="row">
    <div><label>Wake Time<div class="hint">Time you woke up</div></label></div>
    <div class="right"><input type="time" id="sleep_wake"></div>
  </div>
  <div class="row">
    <div><label>REM<div class="hint">e.g. 01:34 = 1h 34m</div></label></div>
    <div class="right"><input type="time" id="rem"><span class="unit">h:m</span></div>
  </div>
  <div class="row">
    <div><label>Core Sleep<div class="hint">e.g. 03:10 = 3h 10m</div></label></div>
    <div class="right"><input type="time" id="core"><span class="unit">h:m</span></div>
  </div>
  <div class="row">
    <div><label>Deep Sleep<div class="hint">e.g. 01:20 = 1h 20m</div></label></div>
    <div class="right"><input type="time" id="deep"><span class="unit">h:m</span></div>
  </div>
  <div class="row">
    <div><label>Awake in Bed<div class="hint">e.g. 00:15 = 15 min</div></label></div>
    <div class="right"><input type="time" id="awake"><span class="unit">h:m</span></div>
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
    <div class="right"><input type="number" id="weight" placeholder="160" step="0.1" oninput="autoFfm()"><span class="unit">lb</span></div>
  </div>
</div>

<!-- BODY COMP -->
<div class="section">
  <div class="section-title">Body Composition <span style="color:var(--muted);font-size:.6rem">(weekly)</span></div>
  <div class="row">
    <div><label>Body Fat %<div class="hint">e.g. 14.5 — from scale or DEXA</div></label></div>
    <div class="right"><input type="number" id="bf_pct" placeholder="14.5" step="0.1" oninput="autoFfm()"><span class="unit">%</span></div>
  </div>
  <div class="row">
    <div><label>Skeletal Muscle %</label></div>
    <div class="right"><input type="number" id="sm_pct" placeholder="42.0" step="0.1"><span class="unit">%</span></div>
  </div>
  <div class="row">
    <div><label>Fat Free Mass<div class="hint">lb — DEXA/InBody preferred. Auto-filled from weight × (1−BF%) if blank.</div></label></div>
    <div class="right"><input type="number" id="ffm_lb" placeholder="165.0" step="0.1"><span class="unit">lb</span></div>
  </div>
</div>

<!-- BODY MEASUREMENTS -->
<div class="section">
  <div class="section-title">Body Measurements <span style="color:var(--muted);font-size:.6rem">(inches · decimal ok · e.g. 31.25 = 31¼")</span></div>

  <div class="row">
    <label>Neck</label>
    <div class="right"><input type="number" id="neck_in" placeholder="15.5" step="0.25"><span class="unit">in</span></div>
  </div>
  <div class="row">
    <label>Chest</label>
    <div class="right"><input type="number" id="chest_in" placeholder="38.0" step="0.25"><span class="unit">in</span></div>
  </div>
  <div class="row">
    <label>Waist <span style="color:var(--muted);font-size:.75rem">(at navel)</span></label>
    <div class="right"><input type="number" id="waist" placeholder="31.0" step="0.25"><span class="unit">in</span></div>
  </div>
  <div class="row">
    <label>Hips</label>
    <div class="right"><input type="number" id="hip_in" placeholder="36.0" step="0.25"><span class="unit">in</span></div>
  </div>

  <p class="meas-group-lbl">Bicep</p>
  <div class="meas-bilateral">
    <div class="meas-side"><span class="meas-side-lbl">L</span><input type="number" id="bicep_l_in" placeholder="14.0" step="0.25"></div>
    <div class="meas-side"><span class="meas-side-lbl">R</span><input type="number" id="bicep_r_in" placeholder="14.0" step="0.25"></div>
  </div>

  <p class="meas-group-lbl">Forearm</p>
  <div class="meas-bilateral">
    <div class="meas-side"><span class="meas-side-lbl">L</span><input type="number" id="forearm_l_in" placeholder="11.5" step="0.25"></div>
    <div class="meas-side"><span class="meas-side-lbl">R</span><input type="number" id="forearm_r_in" placeholder="11.5" step="0.25"></div>
  </div>

  <p class="meas-group-lbl">Wrist</p>
  <div class="meas-bilateral">
    <div class="meas-side"><span class="meas-side-lbl">L</span><input type="number" id="wrist_l_in" placeholder="6.5" step="0.25"></div>
    <div class="meas-side"><span class="meas-side-lbl">R</span><input type="number" id="wrist_r_in" placeholder="6.5" step="0.25"></div>
  </div>

  <p class="meas-group-lbl">Thigh</p>
  <div class="meas-bilateral">
    <div class="meas-side"><span class="meas-side-lbl">L</span><input type="number" id="thigh_l_in" placeholder="22.0" step="0.25"></div>
    <div class="meas-side"><span class="meas-side-lbl">R</span><input type="number" id="thigh_r_in" placeholder="22.0" step="0.25"></div>
  </div>

  <p class="meas-group-lbl">Calf</p>
  <div class="meas-bilateral">
    <div class="meas-side"><span class="meas-side-lbl">L</span><input type="number" id="calf_l_in" placeholder="14.0" step="0.25"></div>
    <div class="meas-side"><span class="meas-side-lbl">R</span><input type="number" id="calf_r_in" placeholder="14.0" step="0.25"></div>
  </div>

  <p class="meas-group-lbl">Ankle</p>
  <div class="meas-bilateral">
    <div class="meas-side"><span class="meas-side-lbl">L</span><input type="number" id="ankle_l_in" placeholder="8.5" step="0.25"></div>
    <div class="meas-side"><span class="meas-side-lbl">R</span><input type="number" id="ankle_r_in" placeholder="8.5" step="0.25"></div>
  </div>
</div>

<!-- SUBJECTIVE -->
<div class="section">
  <div class="section-title">Subjective Scores</div>
  <div class="score-row">
    <div class="score-label">Libido <span style="color:var(--muted);font-size:.75rem">(1–5)</span></div>
    <button class="score-btn" data-field="libido" data-val="1">1</button>
    <button class="score-btn" data-field="libido" data-val="2">2</button>
    <button class="score-btn" data-field="libido" data-val="3">3</button>
    <button class="score-btn" data-field="libido" data-val="4">4</button>
    <button class="score-btn" data-field="libido" data-val="5">5</button>
  </div>
  <div class="score-row">
    <div class="score-label">Morning Erection <span style="color:var(--muted);font-size:.75rem">(0–3)</span></div>
    <button class="score-btn" data-field="erection" data-val="0">0</button>
    <button class="score-btn" data-field="erection" data-val="1">1</button>
    <button class="score-btn" data-field="erection" data-val="2">2</button>
    <button class="score-btn" data-field="erection" data-val="3">3</button>
  </div>
  <div class="score-row">
    <div class="score-label">Mood <span style="color:var(--muted);font-size:.75rem">(1–5)</span></div>
    <button class="score-btn" data-field="mood" data-val="1">1</button>
    <button class="score-btn" data-field="mood" data-val="2">2</button>
    <button class="score-btn" data-field="mood" data-val="3">3</button>
    <button class="score-btn" data-field="mood" data-val="4">4</button>
    <button class="score-btn" data-field="mood" data-val="5">5</button>
  </div>
  <div class="score-row">
    <div class="score-label">Mental Drive <span style="color:var(--muted);font-size:.75rem">(1–5)</span></div>
    <button class="score-btn" data-field="drive" data-val="1">1</button>
    <button class="score-btn" data-field="drive" data-val="2">2</button>
    <button class="score-btn" data-field="drive" data-val="3">3</button>
    <button class="score-btn" data-field="drive" data-val="4">4</button>
    <button class="score-btn" data-field="drive" data-val="5">5</button>
  </div>
  <div class="score-row">
    <div class="score-label">Soreness <span style="color:var(--muted);font-size:.75rem">(1=none, 5=wrecked)</span></div>
    <button class="score-btn" data-field="soreness" data-val="1">1</button>
    <button class="score-btn" data-field="soreness" data-val="2">2</button>
    <button class="score-btn" data-field="soreness" data-val="3">3</button>
    <button class="score-btn" data-field="soreness" data-val="4">4</button>
    <button class="score-btn" data-field="soreness" data-val="5">5</button>
  </div>
  <div class="score-row">
    <div class="score-label">Joint Friction <span style="color:var(--muted);font-size:.75rem">(1=smooth, 5=grinding)</span></div>
    <button class="score-btn" data-field="joints" data-val="1">1</button>
    <button class="score-btn" data-field="joints" data-val="2">2</button>
    <button class="score-btn" data-field="joints" data-val="3">3</button>
    <button class="score-btn" data-field="joints" data-val="4">4</button>
    <button class="score-btn" data-field="joints" data-val="5">5</button>
  </div>
  <div class="score-row">
    <div class="score-label">Stress Load <span style="color:var(--muted);font-size:.75rem">(1=calm, 5=maxed)</span></div>
    <button class="score-btn" data-field="stress" data-val="1">1</button>
    <button class="score-btn" data-field="stress" data-val="2">2</button>
    <button class="score-btn" data-field="stress" data-val="3">3</button>
    <button class="score-btn" data-field="stress" data-val="4">4</button>
    <button class="score-btn" data-field="stress" data-val="5">5</button>
  </div>
</div>

<!-- NUTRITION -->
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

<!-- MEAL PREP & ADHERENCE -->
<div class="section">
  <div class="section-title">Meal Prep &amp; Adherence <span id="adh-day-badge" class="adh-badge">Build Day</span></div>
  <div id="adh-windows"><!-- populated by JS --></div>
  <div class="adh-tally-row">
    <span class="adh-tally-label">Day Total</span>
    <span id="adh-tally" style="color:var(--muted);font-size:.9rem">Tap meals above</span>
  </div>
  <button class="adh-save-btn" id="adh-save-btn" onclick="saveAdherence()">Save Adherence</button>
  <div id="adh-carryover" class="adh-carryover" style="display:none"></div>
</div>

<div class="submit-wrap">
  <button class="submit-btn" id="submit-btn" onclick="submitLog()">Submit Daily Log</button>
</div>

<div class="uuid-row">
  <span>Your ID:</span>
  <input type="text" id="uuid-display" readonly>
</div>

<div class="toast" id="toast"></div>

<script>
// ── UUID ──────────────────────────────────────────────────────────────────────
function genUUID(){
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g,c=>{
    const r=Math.random()*16|0;return(c==='x'?r:(r&0x3|0x8)).toString(16);
  });
}
let USER_ID = localStorage.getItem('arcforge_uid');
if(!USER_ID){ USER_ID=genUUID(); localStorage.setItem('arcforge_uid',USER_ID); }
document.getElementById('uuid-display').value = USER_ID;
fetch('/users/ensure',{method:'POST',headers:{'Content-Type':'application/json'},
  body:JSON.stringify({expo_user_id:USER_ID})}).catch(()=>{});

// ── Date helpers ──────────────────────────────────────────────────────────────
const dateEl = document.getElementById('log-date');
function todayStr(){
  // toLocaleDateString('en-CA') returns YYYY-MM-DD using the device's local timezone
  return new Date().toLocaleDateString('en-CA');
}
dateEl.value = todayStr();

function shiftDate(delta){
  const d = new Date(dateEl.value + 'T12:00:00');
  d.setDate(d.getDate() + delta);
  const pad=n=>String(n).padStart(2,'0');
  dateEl.value = `${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())}`;
  loadDate();
}

// ── Score state ───────────────────────────────────────────────────────────────
const scores = {};
document.querySelectorAll('.score-btn').forEach(btn=>{
  btn.addEventListener('click',()=>{
    const f=btn.dataset.field;
    document.querySelectorAll(`[data-field="${f}"]`).forEach(b=>b.classList.remove('active'));
    btn.classList.add('active');
    scores[f]=parseInt(btn.dataset.val);
  });
});

function setScore(field, val){
  if(val===null||val===undefined) return;
  scores[field]=val;
  document.querySelectorAll(`[data-field="${field}"]`).forEach(b=>{
    b.classList.toggle('active', parseInt(b.dataset.val)===val);
  });
}

function clearScores(){
  ['libido','erection','mood','drive','soreness','joints','stress'].forEach(f=>{
    delete scores[f];
    document.querySelectorAll(`[data-field="${f}"]`).forEach(b=>b.classList.remove('active'));
  });
}

// ── Load existing data for a date ─────────────────────────────────────────────
async function loadDate(){
  clearForm();
  hideResults();
  const date = dateEl.value;
  try {
    const res = await fetch(`/log/data?expo_user_id=${USER_ID}&date=${date}`);
    const d = await res.json();
    if(!d.found){
      resetAdherence();
      loadAdherencePlan("build");
      return;
    }

    // sleep
    setTime('sleep_onset', d.sleep_onset_hhmm);
    setTime('sleep_wake',  d.sleep_wake_hhmm);
    setTime('rem',  d.sleep_rem_hhmm);
    setTime('core', d.sleep_core_hhmm);
    setTime('deep', d.sleep_deep_hhmm);
    setTime('awake',d.sleep_awake_hhmm);

    // biometrics
    setNum('hrv',    d.hrv_ms);
    setNum('rhr',    d.resting_hr_bpm);
    setNum('temp_f', d.morning_temp_f);
    setNum('weight', d.body_weight_lb);

    // body comp
    setNum('bf_pct', d.body_fat_pct);
    setNum('sm_pct', d.skeletal_muscle_pct);
    setNum('ffm_lb', d.fat_free_mass_lb);

    // body measurements
    setNum('waist',       d.waist_at_navel_in);
    setNum('neck_in',     d.neck_in);
    setNum('chest_in',    d.chest_in);
    setNum('hip_in',      d.hip_in);
    setNum('bicep_l_in',  d.bicep_l_in);
    setNum('bicep_r_in',  d.bicep_r_in);
    setNum('forearm_l_in',d.forearm_l_in);
    setNum('forearm_r_in',d.forearm_r_in);
    setNum('wrist_l_in',  d.wrist_l_in);
    setNum('wrist_r_in',  d.wrist_r_in);
    setNum('thigh_l_in',  d.thigh_l_in);
    setNum('thigh_r_in',  d.thigh_r_in);
    setNum('calf_l_in',   d.calf_l_in);
    setNum('calf_r_in',   d.calf_r_in);
    setNum('ankle_l_in',  d.ankle_l_in);
    setNum('ankle_r_in',  d.ankle_r_in);

    // subjective
    setScore('libido',   d.libido_score);
    setScore('erection', d.morning_erection_score);
    setScore('mood',     d.mood_stability_score);
    setScore('drive',    d.mental_drive_score);
    setScore('soreness', d.soreness_score);
    setScore('joints',   d.joint_friction_score);
    setScore('stress',   d.stress_load_score);

    // nutrition
    setNum('kcal',    d.kcal_actual);
    setNum('protein', d.protein_g_actual);
    setNum('carbs',   d.carbs_g_actual);
    setNum('fat',     d.fat_g_actual);

    // meal adherence — restore saved state and re-fetch kcal plan for that day type
    resetAdherence();
    if(d.meal_adherence_json) {
      loadSavedAdherence(d.meal_adherence_json, d.recommended_macro_day || "build");
    } else {
      loadAdherencePlan(d.recommended_macro_day || "build");
    }

  } catch(e){ /* no data for this date, form stays blank */ }
}

function setTime(id, val){
  if(val) document.getElementById(id).value = val;
}
function setNum(id, val){
  if(val!==null && val!==undefined) document.getElementById(id).value = val;
}

function autoFfm(){
  // Auto-compute FFM only if the field is currently blank (don't overwrite a manual DEXA entry)
  const ffmEl = document.getElementById('ffm_lb');
  if(ffmEl && ffmEl.value !== '') return;  // user has a value already, leave it alone
  const wt = parseFloat(document.getElementById('weight')?.value);
  const bf = parseFloat(document.getElementById('bf_pct')?.value);
  if(wt > 0 && bf > 0 && bf < 100){
    ffmEl.value = Math.round((wt * (1 - bf/100)) * 10) / 10;
  }
}

function clearForm(){
  ['sleep_onset','sleep_wake','rem','core','deep','awake'].forEach(id=>{
    document.getElementById(id).value='';
  });
  ['hrv','rhr','temp_f','weight','bf_pct','sm_pct','ffm_lb',
   'waist','neck_in','chest_in','hip_in',
   'bicep_l_in','bicep_r_in','forearm_l_in','forearm_r_in','wrist_l_in','wrist_r_in',
   'thigh_l_in','thigh_r_in','calf_l_in','calf_r_in','ankle_l_in','ankle_r_in',
   'kcal','protein','carbs','fat'].forEach(id=>{
    document.getElementById(id).value='';
  });
  clearScores();
}

function hideResults(){
  document.getElementById('results').style.display='none';
  ['r-scores','r-reco','r-notices','r-sleep','r-meals','r-insights','r-foodplan'].forEach(id=>{
    document.getElementById(id).style.display='none';
  });
}

// ── Time conversion ───────────────────────────────────────────────────────────
function timeToHHMM(val){ return val||null; }
function timeToDecimal(val){
  if(!val) return null;
  const [h,m]=val.split(':').map(Number);
  if(isNaN(h)||isNaN(m)) return null;
  return parseFloat(`${h}.${String(m).padStart(2,'0')}`);
}

// ── Submit ────────────────────────────────────────────────────────────────────
async function submitLog(){
  const btn = document.getElementById('submit-btn');
  btn.disabled=true; btn.textContent='Saving…';

  const num = id=>{const v=document.getElementById(id).value;return v===''?null:parseFloat(v);};

  const body={
    expo_user_id: USER_ID,
    date: dateEl.value,
    sleep_onset_hhmm: timeToHHMM(document.getElementById('sleep_onset').value),
    sleep_wake_hhmm:  timeToHHMM(document.getElementById('sleep_wake').value),
    sleep_rem_min:   timeToDecimal(document.getElementById('rem').value),
    sleep_core_min:  timeToDecimal(document.getElementById('core').value),
    sleep_deep_min:  timeToDecimal(document.getElementById('deep').value),
    sleep_awake_min: timeToDecimal(document.getElementById('awake').value),
    hrv_ms:          num('hrv'),
    resting_hr_bpm:  num('rhr'),
    morning_temp_f:  num('temp_f'),
    body_weight_lb:  num('weight'),
    body_fat_pct:        num('bf_pct'),
    skeletal_muscle_pct: num('sm_pct'),
    fat_free_mass_lb:    num('ffm_lb'),
    waist_at_navel_in:   num('waist'),
    neck_in:         num('neck_in'),
    chest_in:        num('chest_in'),
    hip_in:          num('hip_in'),
    bicep_l_in:      num('bicep_l_in'),
    bicep_r_in:      num('bicep_r_in'),
    forearm_l_in:    num('forearm_l_in'),
    forearm_r_in:    num('forearm_r_in'),
    wrist_l_in:      num('wrist_l_in'),
    wrist_r_in:      num('wrist_r_in'),
    thigh_l_in:      num('thigh_l_in'),
    thigh_r_in:      num('thigh_r_in'),
    calf_l_in:       num('calf_l_in'),
    calf_r_in:       num('calf_r_in'),
    ankle_l_in:      num('ankle_l_in'),
    ankle_r_in:      num('ankle_r_in'),
    libido_score:        scores['libido']   ??null,
    morning_erection_score: scores['erection']??null,
    mood_stability_score: scores['mood']    ??null,
    mental_drive_score:  scores['drive']    ??null,
    soreness_score:      scores['soreness'] ??null,
    joint_friction_score: scores['joints']  ??null,
    stress_load_score:   scores['stress']   ??null,
    kcal_actual:      num('kcal'),
    protein_g_actual: num('protein'),
    carbs_g_actual:   num('carbs'),
    fat_g_actual:     num('fat'),
  };
  Object.keys(body).forEach(k=>{if(body[k]===null||body[k]===undefined)delete body[k];});

  try{
    const res=await fetch('/vitals/daily-log',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
    const json=await res.json();
    if(!res.ok){showToast('Error: '+(json.detail||res.status));return;}
    renderResults(json);
    showToast('Saved ✓');
    document.getElementById('results').scrollIntoView({behavior:'smooth'});
  }catch(e){showToast('Network error');}
  finally{btn.disabled=false;btn.textContent='Submit Daily Log';}
}

// ── Render results ────────────────────────────────────────────────────────────
function renderResults(json){
  const ds=json.displaySpec; const rec=json.recommendation;
  document.getElementById('results').style.display='block';

  if(ds.scoreCards?.length){
    document.getElementById('score-grid').innerHTML=ds.scoreCards.map(c=>`
      <div class="score-box"><div class="val ${c.color}">${Math.round(c.score)}</div><div class="lbl">${c.label}</div></div>`).join('');
    document.getElementById('r-scores').style.display='block';
  }

  if(rec){
    document.getElementById('reco-body').innerHTML=`
      <div class="reco-row"><span class="lbl">Lift</span><span class="val">${fmt(rec.recommendedLiftMode)}</span></div>
      <div class="reco-row"><span class="lbl">Cardio</span><span class="val">${fmt(rec.recommendedCardioMode)}</span></div>
      <div class="reco-row"><span class="lbl">Macro Day</span><span class="val">${fmt(rec.recommendedMacroDayType)}</span></div>
      ${rec.macroTargets?`
      <div class="reco-row"><span class="lbl">Calories</span><span class="val">${rec.macroTargets.kcalTarget??'—'} kcal</span></div>
      <div class="reco-row"><span class="lbl">Protein</span><span class="val">${rec.macroTargets.proteinG??'—'} g</span></div>
      <div class="reco-row"><span class="lbl">Carbs</span><span class="val">${rec.macroTargets.carbsG??'—'} g</span></div>
      <div class="reco-row"><span class="lbl">Fat</span><span class="val">${rec.macroTargets.fatG??'—'} g</span></div>`:''}`;
    document.getElementById('r-reco').style.display='block';
  }

  if(ds.notices?.length){
    document.getElementById('notices-body').innerHTML=ds.notices.map(n=>`
      <div class="notice"><div class="dot dot-${n.type}"></div><div class="msg">${n.message}</div></div>`).join('');
    document.getElementById('r-notices').style.display='block';
  }

  const sl=ds.sleepSummary;
  if(sl){
    const items=[sl.duration,sl.efficiency,sl.midpoint,sl.timeInBed,
      sl.stages?.rem,sl.stages?.core,sl.stages?.deep,sl.stages?.awake].filter(x=>x?.display);
    if(items.length){
      document.getElementById('sleep-grid').innerHTML=items.map(i=>`
        <div class="sleep-item"><div class="val">${i.display}</div><div class="lbl">${i.label}</div></div>`).join('');
      document.getElementById('r-sleep').style.display='block';
    }
  }

  const meals=ds.mealTiming?.sections?.filter(m=>m.proteinG||m.carbsG||m.fatG);
  if(meals?.length){
    document.getElementById('meals-body').innerHTML=meals.map(m=>`
      <div class="meal-row"><span class="meal-lbl">${m.label}</span>
      ${m.proteinG?`<span class="macro-chip chip-p">${m.proteinG}g P</span>`:''}
      ${m.carbsG?`<span class="macro-chip chip-c">${m.carbsG}g C</span>`:''}
      ${m.fatG?`<span class="macro-chip chip-f">${m.fatG}g F</span>`:''}</div>`).join('');
    document.getElementById('r-meals').style.display='block';
  }

  if(ds.insights?.length){
    document.getElementById('insights-body').innerHTML=ds.insights.map(i=>`
      <div class="insight">• ${i}</div>`).join('');
    document.getElementById('r-insights').style.display='block';
  }

  // Food plan — fetch and render prep card
  const dayType = rec?.recommendedMacroDayType;
  if(dayType) {
    renderFoodPlan(dayType);
    loadAdherencePlan(dayType);
  }
}

// ── Meal Prep & Adherence ─────────────────────────────────────────────────────
const ADH_WINDOWS = [
  {name:"Pre-Cardio",      time:"05:30", intel:false},
  {name:"Post-Cardio",     time:"06:45", intel:false},
  {name:"Mid-Morning",     time:"11:30", intel:false},
  {name:"Pre-Lift",        time:"15:45", intel:false},
  {name:"Post-Lift",       time:"18:20", intel:false},
  {name:"Evening Meal",    time:"20:00", intel:false},
  {name:"Evening Protein", time:"21:30", intel:true},
];
let _adhState      = {};  // {windowName: "base"|"adj"|"skip"|null}
let _adhPlan       = {};  // {windowName: {base_kcal, adj_kcal, base_foods[], adj_foods[]}}
let _adhDayType    = "build";
let _adhTargetKcal = 2696;

function _fmtAmt(f){
  if(f.intel_managed) return "Intel fill";
  if(f.unit==="whole")  return f.amount+" whole";
  if(f.unit==="cup")    return f.amount+" cup";
  return f.amount+"g";
}

function _foodsColHtml(foods, kcal, hdrLabel, hdrClass){
  if(!foods||!foods.length) return "";
  const rows = foods.map(f=>
    `<div class="adh-food-row">
       <span class="adh-food-name">${f.name}</span>
       <span class="adh-food-amt">${_fmtAmt(f)}</span>
     </div>`
  ).join("");
  const hdr = hdrLabel
    ? `<div class="adh-foods-hdr ${hdrClass}">${hdrLabel}</div>` : "";
  const tot = kcal
    ? `<div class="adh-foods-kcal">${kcal} kcal</div>` : "";
  return `<div class="adh-foods-col">${hdr}${rows}${tot}</div>`;
}

function resetAdherence(){
  ADH_WINDOWS.forEach(w=>{
    _adhState[w.name]=null;
    _adhPlan[w.name]={base_kcal:0,adj_kcal:0,base_foods:[],adj_foods:[]};
  });
  const carry=document.getElementById("adh-carryover");
  if(carry) carry.style.display="none";
  renderAdherenceWindows();
  updateAdherenceTally();
}

function loadAdherencePlan(dayType, afterLoad){
  _adhDayType = dayType||"build";
  const badge=document.getElementById("adh-day-badge");
  const dtLabel=_adhDayType.charAt(0).toUpperCase()+_adhDayType.slice(1);
  if(badge) badge.textContent=dtLabel+" Day";
  Promise.all([
    fetch("/log/meal-plan?day_type=build").then(r=>r.json()),
    fetch(`/log/meal-plan?day_type=${_adhDayType}`).then(r=>r.json()),
  ]).then(([bp,ap])=>{
    const b=bp.plan||{}, a=ap.plan||{};
    let tot=0;
    ADH_WINDOWS.forEach(w=>{
      _adhPlan[w.name]={
        base_kcal:  b[w.name]?.kcal??0,
        adj_kcal:   a[w.name]?.kcal??0,
        base_foods: b[w.name]?.foods??[],
        adj_foods:  a[w.name]?.foods??[],
      };
      tot+=b[w.name]?.kcal??0;
    });
    _adhTargetKcal=tot;
    renderAdherenceWindows();
    updateAdherenceTally();
    if(afterLoad) afterLoad();
  });
}

function renderAdherenceWindows(){
  const el=document.getElementById("adh-windows");
  if(!el) return;
  const isBuilt = _adhDayType==="build";
  const dtLabel = _adhDayType.charAt(0).toUpperCase()+_adhDayType.slice(1);

  el.innerHTML=ADH_WINDOWS.map(w=>{
    const pl  =_adhPlan[w.name]||{base_kcal:0,adj_kcal:0,base_foods:[],adj_foods:[]};
    const bk  =pl.base_kcal, ak=pl.adj_kcal;
    const bf  =pl.base_foods, af=pl.adj_foods;
    const st  =_adhState[w.name];
    const winId=w.name.replace(/\s+/g,'-');

    // Build the ingredient card
    let foodsHtml="";
    if(bf.length||af.length){
      if(isBuilt){
        // Single column — no header needed, just BASE
        const col=_foodsColHtml(bf, bk, "", "");
        foodsHtml=`<div class="adh-foods" style="display:block">${col}</div>`;
      } else {
        // Dual column: BASE (green) | ADJ day type (orange)
        const bCol=_foodsColHtml(bf, bk, "Base (Build)", "adh-hdr-base");
        const aCol=_foodsColHtml(af, ak, `Adj (${dtLabel})`, "adh-hdr-adj");
        foodsHtml=`<div class="adh-foods">${bCol}${aCol}</div>`;
      }
    } else if(w.intel){
      foodsHtml=`<div class="adh-foods" style="display:block"><div class="adh-foods-col"><div class="adh-food-row"><span class="adh-food-name">Whey protein</span><span class="adh-food-amt" style="color:var(--muted)">Intel fill</span></div></div></div>`;
    }

    const intelNote=w.intel?`<span class="adh-intel-note">· Intel-managed</span>`:"";

    return `<div class="adh-row" id="adh-row-${winId}">
  <div class="adh-win-label">
    <span class="adh-win-name">${w.name}</span>${intelNote}
    <span class="adh-win-time">${w.time}</span>
  </div>
  ${foodsHtml}
  <div class="adh-btns">
    <button class="adh-btn adh-base${st==='base'?' active':''}"
      onclick="tapAdherence('${w.name}','base')">
      Base${bk?`<span class="adh-kcal">${bk} kcal</span>`:""}
    </button>
    <button class="adh-btn adh-adj${st==='adj'?' active':''}"
      onclick="tapAdherence('${w.name}','adj')">
      Adj${ak?`<span class="adh-kcal">${ak} kcal</span>`:""}
    </button>
    <button class="adh-btn adh-skip${st==='skip'?' active':''}"
      onclick="tapAdherence('${w.name}','skip')">
      Skip
    </button>
  </div>
</div>`;
  }).join("");
}

function tapAdherence(winName, status){
  _adhState[winName]=(_adhState[winName]===status)?null:status;
  renderAdherenceWindows();
  updateAdherenceTally();
}

function updateAdherenceTally(){
  let total=0;
  ADH_WINDOWS.forEach(w=>{
    const st=_adhState[w.name], pl=_adhPlan[w.name]||{base_kcal:0,adj_kcal:0};
    if(st==='base') total+=pl.base_kcal||0;
    else if(st==='adj') total+=pl.adj_kcal||0;
  });
  const target=_adhTargetKcal||2696;
  const pct=target?Math.round(total/target*100):0;
  const el=document.getElementById("adh-tally");
  if(el) el.innerHTML=`<span style="color:var(--accent);font-weight:700">${total.toLocaleString()}</span>`+
    ` / ${target.toLocaleString()} kcal`+
    `<span style="color:var(--muted);font-size:.78rem;margin-left:6px">${pct}%</span>`;
}

async function saveAdherence(){
  const uid=USER_ID; const date=dateEl.value;
  if(!uid||!date){showToast("User ID not set","err");return;}
  let total=0;
  const windowsData={};
  ADH_WINDOWS.forEach(w=>{
    const st=_adhState[w.name], pl=_adhPlan[w.name]||{base_kcal:0,adj_kcal:0};
    const logged_kcal=st==='base'?(pl.base_kcal||0):st==='adj'?(pl.adj_kcal||0):0;
    total+=logged_kcal;
    windowsData[w.name]={status:st||"not_logged",base_kcal:pl.base_kcal||0,adj_kcal:pl.adj_kcal||0,logged_kcal};
  });
  const target=_adhTargetKcal||2696;
  const delta=total-target;
  const btn=document.getElementById("adh-save-btn");
  if(btn){btn.disabled=true;btn.textContent="Saving…";}
  const res=await fetch("/log/meal-adherence",{
    method:"POST",headers:{"Content-Type":"application/json"},
    body:JSON.stringify({expo_user_id:uid,date,day_type:_adhDayType,adherence:windowsData,total_kcal:total,target_kcal:target,kcal_delta:delta}),
  });
  if(btn){btn.disabled=false;btn.textContent="Save Adherence";}
  if(res.ok){
    showToast("Adherence saved ✓","ok");
    const carry=document.getElementById("adh-carryover");
    if(carry){
      const sign=delta>=0?"+":"";
      const col=delta>=0?"var(--green)":"var(--red)";
      carry.style.display="flex";
      carry.innerHTML=`<span class="adh-carry-label">Walking into tomorrow</span>`+
        `<span style="color:${col};font-weight:700;font-size:1rem">${sign}${Math.abs(delta).toLocaleString()} kcal ${delta>=0?'surplus':'deficit'}</span>`+
        `<span style="color:var(--muted);font-size:.75rem">${total.toLocaleString()} consumed · ${target.toLocaleString()} target</span>`;
    }
  } else { showToast("Save failed — try again","err"); }
}

function loadSavedAdherence(adherenceJson, dayType){
  if(!adherenceJson) return;
  // Apply saved tap states first
  ADH_WINDOWS.forEach(w=>{
    const saved=adherenceJson[w.name];
    _adhState[w.name]=(saved?.status&&saved.status!=="not_logged")?saved.status:null;
  });
  _adhTargetKcal=adherenceJson.target_kcal||2696;
  // Load full plan (fetches ingredient foods) then show carryover
  loadAdherencePlan(dayType||"build", ()=>{
    const total=adherenceJson.total_kcal||0;
    const target=adherenceJson.target_kcal||2696;
    const delta=adherenceJson.kcal_delta||0;
    const carry=document.getElementById("adh-carryover");
    if(carry&&total){
      const sign=delta>=0?"+":"";
      const col=delta>=0?"var(--green)":"var(--red)";
      carry.style.display="flex";
      carry.innerHTML=`<span class="adh-carry-label">Walking into tomorrow</span>`+
        `<span style="color:${col};font-weight:700;font-size:1rem">${sign}${Math.abs(delta).toLocaleString()} kcal ${delta>=0?'surplus':'deficit'}</span>`+
        `<span style="color:var(--muted);font-size:.75rem">${total.toLocaleString()} consumed · ${target.toLocaleString()} target</span>`;
    }
    renderAdherenceWindows();
    updateAdherenceTally();
  });
}

// ── Ingredient macro density — sourced from user's food tracking app, large-batch measurements.
// Per-gram values (g-unit foods) or per-unit values (whole/cup foods).
// Source batches: 10 bananas=1180g | 10 eggs=500g | 10 cups yogurt=2450g | all others per 100g | MCT per 200g.
const IMACRO = {
  "Banana":       {p:0.8700,  c:25.1200, f:0.3400, kcal:103.8000},  // per whole (118g): P:8.7 C:251.2 F:3.4 /1180g
  "Oats":         {p:0.1330,  c:0.6000,  f:0.0500, kcal:4.0000},    // per g: 100g→P:13.3 C:60.0 F:5.0 kcal:400
  "Whey":         {p:0.8780,  c:0.0310,  f:0.0000, kcal:3.7600},    // per g: 100g→P:87.8 C:3.1 F:0.0 kcal:376
  "MCT Powder":   {p:0.1000,  c:0.0000,  f:0.8000, kcal:7.0000},    // per g: 200g→P:20.0 C:0.0 F:160.0 kcal:1400
  "Dextrin":      {p:0.0000,  c:0.9730,  f:0.0000, kcal:3.8700},    // per g: 100g→P:0.0 C:97.3 F:0.0 kcal:387
  "Greek Yogurt": {p:25.2400, c:8.9100,  f:0.9100, kcal:149.5000},  // per cup (245g): 10c→P:252.4 C:89.1 F:9.1 /2450g
  "Flaxseed":     {p:0.3300,  c:0.0770,  f:0.1000, kcal:3.2400},    // per g: 100g→P:33.0 C:7.7 F:10.0 kcal:324
  "Eggs":         {p:6.2900,  c:0.5600,  f:5.3000, kcal:77.5000},   // per whole (50g): 10 large→P:62.9 C:5.6 F:53.0 /500g
};

let _currentPlan = null;
let _currentDayType = null;

function findIngInput(name, windowName){
  let found = null;
  document.querySelectorAll('.ing-actual-input').forEach(el=>{
    if(el.dataset.name === name && el.dataset.window === windowName) found = el;
  });
  return found;
}

function calcWindowActuals(foods){
  let p=0, c=0, f=0, kcal=0;
  foods.forEach(food=>{
    if(food.intel_managed) return;
    const m = IMACRO[food.name]; if(!m) return;
    const inputEl = findIngInput(food.name, food._windowName);
    const qty = inputEl ? (parseFloat(inputEl.value)||0) : food.amount;
    p    += m.p    * qty;
    c    += m.c    * qty;
    f    += m.f    * qty;
    kcal += m.kcal * qty;
  });
  return {p: Math.round(p*10)/10, c: Math.round(c*10)/10, f: Math.round(f*10)/10, kcal: Math.round(kcal)};
}

function dv(delta){
  const r = Math.round(delta*10)/10;
  const cls = Math.abs(r)<1 ? 'dv-zero' : r>0 ? 'dv-pos' : 'dv-neg';
  return `<span class="dv ${cls}">${r>0?'+':''}${r}</span>`;
}

function updateWindowDelta(windowName, foods, planned){
  const act = calcWindowActuals(foods.map(f=>({...f, _windowName:windowName})));
  const el  = document.getElementById(`wdelta-${windowName.replace(/\s/g,'-')}`);
  if(!el) return act;
  const dp = Math.round((act.p - planned.P)*10)/10;
  const dc = Math.round((act.c - planned.C)*10)/10;
  const df = Math.round((act.f - planned.F)*10)/10;
  const dk = Math.round(act.kcal - planned.kcal);
  const allZero = Math.abs(dp)<1 && Math.abs(dc)<1 && Math.abs(df)<1 && Math.abs(dk)<2;
  if(allZero){
    el.innerHTML = `<span class="dv-zero" style="font-size:.68rem">On plan ✓</span>`;
  } else {
    el.innerHTML = `<span class="delta-label">Δ</span> ${dv(dp)}P  ${dv(dc)}C  ${dv(df)}F  ${dv(dk)}kcal`;
  }
  return act;
}

function updateDayTotals(){
  if(!_currentPlan) return;
  let tp=0,tc=0,tf=0,tk=0, ap=0,ac=0,af=0,ak=0;
  Object.entries(_currentPlan).forEach(([wn,w])=>{
    if(w.intel_managed) return;
    tp+=w.P||0; tc+=w.C||0; tf+=w.F||0; tk+=w.kcal||0;
    const act = calcWindowActuals((w.foods||[]).map(f=>({...f,_windowName:wn})));
    ap+=act.p; ac+=act.c; af+=act.f; ak+=act.kcal;
  });
  // Intel whey
  const intelEl = document.querySelector('.ing-actual-input[data-window="Evening Protein"]');
  if(intelEl){
    const qty = parseFloat(intelEl.value)||0;
    const m = IMACRO["Whey"];
    ap += Math.round(m.p*qty*10)/10;
    ac += Math.round(m.c*qty*10)/10;
    af += Math.round(m.f*qty*10)/10;
    ak += Math.round(m.kcal*qty);
  }
  ap=Math.round(ap*10)/10; ac=Math.round(ac*10)/10;
  af=Math.round(af*10)/10; ak=Math.round(ak);
  const dp=Math.round((ap-tp)*10)/10, dc=Math.round((ac-tc)*10)/10,
        df=Math.round((af-tf)*10)/10, dk=Math.round(ak-tk);
  const bar = document.getElementById('day-totals-bar');
  if(!bar) return;
  bar.innerHTML = `<div class="day-totals-bar">
    <h4>Day Totals</h4>
    <div class="day-totals-row">
      <span class="dt-lbl"></span>
      <span class="dt-val" style="color:#60a5fa">Protein</span>
      <span class="dt-val" style="color:#facc15">Carbs</span>
      <span class="dt-val" style="color:#fb923c">Fat</span>
      <span class="dt-val" style="color:var(--muted)">kcal</span>
    </div>
    <div class="day-totals-row">
      <span class="dt-lbl" style="color:var(--muted)">Planned</span>
      <span class="dt-val">${tp}g</span><span class="dt-val">${tc}g</span>
      <span class="dt-val">${tf}g</span><span class="dt-val">${tk}</span>
    </div>
    <div class="day-totals-row">
      <span class="dt-lbl" style="color:var(--muted)">Actual</span>
      <span class="dt-val">${ap}g</span><span class="dt-val">${ac}g</span>
      <span class="dt-val">${af}g</span><span class="dt-val">${ak}</span>
    </div>
    <div class="day-totals-row" style="border-top:1px solid #1a1a1a;padding-top:4px;margin-top:4px">
      <span class="dt-lbl" style="color:var(--muted)">Delta</span>
      <span class="dt-val">${dv(dp)}</span><span class="dt-val">${dv(dc)}</span>
      <span class="dt-val">${dv(df)}</span><span class="dt-val">${dv(dk)}</span>
    </div>
  </div>`;
  bar.style.display = 'block';
}

function renderFoodPlan(dayType){
  _currentDayType = dayType;
  fetch(`/log/meal-plan?day_type=${dayType}`)
    .then(r=>r.json())
    .then(mp=>{
      const plan = mp.plan; if(!plan) return;
      _currentPlan = plan;

      const html = Object.entries(plan).map(([wn,w])=>{
        const wid = wn.replace(/\s/g,'-');
        const isIntel = w.intel_managed;

        // planned macro bar
        const plannedBar = isIntel ? 'Intel-managed · baseline 0g Whey'
          : [w.P?`${w.P}g P`:'', w.C?`${w.C}g C`:'', w.F?`${w.F}g F`:'', w.kcal?`${w.kcal} kcal`:'']
              .filter(Boolean).join(' · ');

        let ingredientRows = '';
        if(isIntel){
          ingredientRows = `
          <div class="prep-intel-row">
            <span class="ing-name" style="color:var(--muted);font-style:italic">Whey (Intel)</span>
            <span class="ing-planned-qty">0g planned</span>
            <input class="ing-actual-input" type="number" value="0" min="0" step="5"
              data-window="Evening Protein" data-name="Whey" data-planned="0"
              oninput="updateDayTotals()">
            <span class="ing-unit">g</span>
          </div>`;
        } else {
          ingredientRows = (w.foods||[]).filter(f=>!f.intel_managed).map(f=>{
            const step = f.unit==='whole'||f.unit==='cup' ? 0.5 : 1;
            return `<div class="prep-ingredient">
              <span class="ing-name">${f.name}</span>
              <span class="ing-planned-qty">${f.amount}${f.unit==='g'?'g':' '+f.unit} plan</span>
              <input class="ing-actual-input" type="number" value="${f.amount}" min="0" step="${step}"
                data-window="${wn}" data-name="${f.name}" data-planned="${f.amount}"
                oninput="onIngChange(this,'${wid}')">
              <span class="ing-unit">${f.unit}</span>
            </div>`;
          }).join('');
        }

        return `<div class="prep-window">
          <div class="prep-header">
            <span class="prep-win-name">${wn}</span>
            <span class="prep-win-time">${w.time||''}</span>
          </div>
          <div class="prep-planned-row">Plan: ${plannedBar}</div>
          ${ingredientRows}
          ${isIntel
            ? `<div class="prep-intel-note">Brain sets actual amount based on resource cycle. Enter what you consumed above to track the delta.</div>`
            : `<div class="window-delta" id="wdelta-${wid}"><span class="dv-zero" style="font-size:.68rem">On plan ✓</span></div>`}
        </div>`;
      }).join('');

      document.getElementById('foodplan-body').innerHTML = html;
      document.getElementById('r-foodplan').style.display = 'block';
      document.getElementById('log-actuals-btn').style.display = 'block';
      updateDayTotals();
    }).catch(()=>{});
}

function onIngChange(el, wid){
  const wn = el.dataset.window;
  const planned = parseFloat(el.dataset.planned)||0;
  el.classList.toggle('changed', (parseFloat(el.value)||0) !== planned);
  const w = _currentPlan?.[wn]; if(!w) return;
  updateWindowDelta(wn, (w.foods||[]).map(f=>({...f,_windowName:wn})), w);
  updateDayTotals();
}

async function logActuals(){
  const btn = document.getElementById('log-actuals-btn');
  btn.disabled = true; btn.textContent = 'Saving…';
  if(!_currentPlan){ btn.disabled=false; btn.textContent='Log Actuals'; return; }

  const windowActuals = {};
  let tp=0,tc=0,tf=0,tk=0, ap=0,ac=0,af=0,ak=0;

  Object.entries(_currentPlan).forEach(([wn,w])=>{
    if(w.intel_managed){
      // Evening Protein — Intel window
      const el = document.querySelector(`.ing-actual-input[data-window="Evening Protein"]`);
      const qty = el ? (parseFloat(el.value)||0) : 0;
      const m = IMACRO["Whey"];
      const act = {p:Math.round(m.p*qty*10)/10, c:Math.round(m.c*qty*10)/10,
                   f:Math.round(m.f*qty*10)/10, kcal:Math.round(m.kcal*qty)};
      windowActuals[wn] = {
        planned:{p:0,c:0,f:0,kcal:0},
        actual: act,
        ingredients:{"Whey":{planned_qty:0, actual_qty:qty}}
      };
      ap+=act.p; ac+=act.c; af+=act.f; ak+=act.kcal;
      return;
    }
    tp+=w.P||0; tc+=w.C||0; tf+=w.F||0; tk+=w.kcal||0;
    const ings = {};
    (w.foods||[]).forEach(f=>{
      const el = document.querySelector(`.ing-actual-input[data-window="${wn}"][data-name="${f.name}"]`);
      ings[f.name] = {planned_qty: f.amount, actual_qty: el ? (parseFloat(el.value)||0) : f.amount};
    });
    const act = calcWindowActuals((w.foods||[]).map(f=>({...f,_windowName:wn})));
    windowActuals[wn] = {
      planned:{p:w.P||0, c:w.C||0, f:w.F||0, kcal:w.kcal||0},
      actual: act,
      ingredients: ings
    };
    ap+=act.p; ac+=act.c; af+=act.f; ak+=act.kcal;
  });

  ap=Math.round(ap*10)/10; ac=Math.round(ac*10)/10;
  af=Math.round(af*10)/10; ak=Math.round(ak);

  const payload = {
    expo_user_id: USER_ID,
    date: document.getElementById('log-date').value,
    meal_actuals_json: {
      day_type: _currentDayType,
      windows: windowActuals,
      totals: {
        planned: {p:tp, c:tc, f:tf, kcal:tk},
        actual:  {p:ap, c:ac, f:af, kcal:ak},
        delta:   {p:Math.round((ap-tp)*10)/10, c:Math.round((ac-tc)*10)/10,
                  f:Math.round((af-tf)*10)/10, kcal:Math.round(ak-tk)}
      }
    }
  };

  try{
    const res = await fetch('/log/meal-actuals',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
    if(res.ok){ showToast('Actuals saved ✓'); btn.textContent='Actuals Saved ✓'; }
    else { showToast('Error saving actuals'); btn.disabled=false; btn.textContent='Log Actuals'; }
  } catch(e){ showToast('Network error'); btn.disabled=false; btn.textContent='Log Actuals'; }
}

function fmt(s){return s?s.replace(/_/g,' ').replace(/\b\w/g,c=>c.toUpperCase()):'—';}
function showToast(msg){
  const t=document.getElementById('toast');
  t.textContent=msg;t.style.display='block';
  clearTimeout(t._timer);t._timer=setTimeout(()=>t.style.display='none',3000);
}

// Load today's data on page open
loadDate();
</script>
<nav class="bottom-nav">
  <a href="/log"    class="nav-item active"><span class="nav-icon">📋</span>Log</a>
  <a href="/cardio" class="nav-item"><span class="nav-icon">🏃</span>Cardio</a>
  <a href="/lift"   class="nav-item"><span class="nav-icon">🏋️</span>Lift</a>
  <a href="/system" class="nav-item"><span class="nav-icon">⚡</span>System</a>
</nav>
</body>
</html>"""


@router.get("/log", response_class=HTMLResponse, include_in_schema=False)
def daily_log_page():
    return _HTML


# ═══════════════════════════════════════════════════════════════════════════════
# CARDIO PAGE
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/cardio/data", include_in_schema=False)
def get_cardio_data(expo_user_id: str, date: str, db: Session = Depends(get_db)):
    from datetime import date as ddate
    d = ddate.fromisoformat(date)
    rows = (db.query(VitalsCardioSession)
            .filter(VitalsCardioSession.expo_user_id == expo_user_id,
                    VitalsCardioSession.date == d)
            .order_by(desc(VitalsCardioSession.created_at))
            .all())
    sessions = []
    for r in rows:
        sessions.append({
            "id": r.id,
            "mode": r.mode,
            "duration_min": float(r.duration_min) if r.duration_min else None,
            "avg_hr_bpm": float(r.avg_hr_bpm) if r.avg_hr_bpm else None,
            "max_hr_bpm": float(r.max_hr_bpm) if r.max_hr_bpm else None,
            "zone2_min": float(r.zone2_min) if r.zone2_min else None,
            "zone3_min": float(r.zone3_min) if r.zone3_min else None,
        })
    return {"sessions": sessions}


@router.post("/cardio/save", include_in_schema=False)
async def save_cardio(request: Request, db: Session = Depends(get_db)):
    from datetime import date as ddate
    body = await request.json()
    expo_user_id = body.get("expo_user_id", _EXPO_USER_ID)
    d = ddate.fromisoformat(body["date"])
    row = VitalsCardioSession(
        expo_user_id=expo_user_id,
        date=d,
        mode=body.get("mode", "zone_2"),
        duration_min=body.get("duration_min") or None,
        avg_hr_bpm=body.get("avg_hr_bpm") or None,
        max_hr_bpm=body.get("max_hr_bpm") or None,
        zone2_min=body.get("zone2_min") or None,
        zone3_min=body.get("zone3_min") or None,
        source="manual",
    )
    db.add(row)
    db.commit()
    return {"ok": True, "id": row.id}


_CARDIO_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1">
<meta name="apple-mobile-web-app-capable" content="yes">
<title>ArcForge — Cardio</title>
<style>
""" + _CSS_VARS + """
.chip-zone_2{background:#0a2a2a;color:#2dd4bf}
.chip-zone_3{background:#2a200a;color:#facc15}
.chip-recovery_walk{background:#1a1a1a;color:#666}
</style>
</head>
<body>
<div class="header">
  <div class="header-top">
    <h1>⚡ ArcForge — Cardio</h1>
    <span id="day-badge" style="font-size:.72rem;color:var(--muted)"></span>
  </div>
  <div class="date-row">
    <button class="date-nav" onclick="shiftDate(-1)">‹</button>
    <input type="date" id="date-input" onchange="loadDate()">
    <button class="date-nav" onclick="shiftDate(1)">›</button>
  </div>
</div>

<div class="section">
  <div class="section-title">Session Details</div>
  <div class="row">
    <label>Mode</label>
    <div class="right">
      <select id="mode">
        <option value="zone_2">Zone 2</option>
        <option value="zone_3">Zone 3</option>
        <option value="recovery_walk">Recovery Walk</option>
      </select>
    </div>
  </div>
  <div class="row">
    <label>Duration<div class="hint">total session time</div></label>
    <div class="right"><input type="number" id="duration_min" placeholder="—"><span class="unit">min</span></div>
  </div>
  <div class="row">
    <label>Avg Heart Rate</label>
    <div class="right"><input type="number" id="avg_hr_bpm" placeholder="—"><span class="unit">bpm</span></div>
  </div>
  <div class="row">
    <label>Max Heart Rate</label>
    <div class="right"><input type="number" id="max_hr_bpm" placeholder="—"><span class="unit">bpm</span></div>
  </div>
  <div class="row">
    <label>Zone 2 Time<div class="hint">fat-burning aerobic</div></label>
    <div class="right"><input type="number" id="zone2_min" placeholder="—"><span class="unit">min</span></div>
  </div>
  <div class="row">
    <label>Zone 3 Time<div class="hint">aerobic tempo</div></label>
    <div class="right"><input type="number" id="zone3_min" placeholder="—"><span class="unit">min</span></div>
  </div>
</div>

<div id="history-section" style="display:none">
  <div class="hist-card">
    <h3>Today's Sessions</h3>
    <div id="history-list"></div>
  </div>
</div>

<div class="submit-wrap">
  <button class="submit-btn" onclick="saveCardio()">Log Session</button>
</div>

<div id="toast" class="toast"></div>
""" + _NAV_HTML('cardio') + """
<script>
const EXPO = "beeb9b83-58d3-4a22-a1a7-a252fd86a0e0";

function today(){const n=new Date();return n.getFullYear()+'-'+String(n.getMonth()+1).padStart(2,'0')+'-'+String(n.getDate()).padStart(2,'0');}
function shiftDate(d){const dt=new Date(document.getElementById('date-input').value+'T12:00:00');dt.setDate(dt.getDate()+d);document.getElementById('date-input').value=dt.toISOString().slice(0,10);loadDate();}

async function loadDate(){
  const date=document.getElementById('date-input').value||today();
  document.getElementById('date-input').value=date;
  const r=await fetch(`/cardio/data?expo_user_id=${EXPO}&date=${date}`);
  const d=await r.json();
  renderHistory(d.sessions||[]);
}

function renderHistory(sessions){
  const sec=document.getElementById('history-section');
  const list=document.getElementById('history-list');
  if(!sessions.length){sec.style.display='none';return;}
  sec.style.display='block';
  list.innerHTML=sessions.map(s=>`
    <div class="hist-row">
      <span class="hist-lbl"><span class="chip chip-${s.mode}">${s.mode.replace('_',' ')}</span></span>
      <span class="hist-val">${s.duration_min||'—'} min · ${s.avg_hr_bpm||'—'} bpm avg</span>
    </div>
  `).join('');
}

async function saveCardio(){
  const btn=document.querySelector('.submit-btn');
  btn.disabled=true;btn.textContent='Saving…';
  const payload={
    expo_user_id:EXPO,
    date:document.getElementById('date-input').value||today(),
    mode:document.getElementById('mode').value,
    duration_min:parseFloat(document.getElementById('duration_min').value)||null,
    avg_hr_bpm:parseFloat(document.getElementById('avg_hr_bpm').value)||null,
    max_hr_bpm:parseFloat(document.getElementById('max_hr_bpm').value)||null,
    zone2_min:parseFloat(document.getElementById('zone2_min').value)||null,
    zone3_min:parseFloat(document.getElementById('zone3_min').value)||null,
  };
  const res=await fetch('/cardio/save',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
  if(res.ok){
    showToast('Session logged ✓','ok');
    btn.textContent='Log Session';btn.disabled=false;
    // clear fields
    ['duration_min','avg_hr_bpm','max_hr_bpm','zone2_min','zone3_min'].forEach(id=>document.getElementById(id).value='');
    loadDate();
  } else {showToast('Error — try again','err');btn.disabled=false;btn.textContent='Log Session';}
}

""" + _TOAST_JS + """
document.getElementById('date-input').value=today();
loadDate();
</script>
</body>
</html>"""


# ═══════════════════════════════════════════════════════════════════════════════
# LIFT PAGE
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/lift/data", include_in_schema=False)
def get_lift_data(expo_user_id: str, date: str, db: Session = Depends(get_db)):
    from datetime import date as ddate
    d = ddate.fromisoformat(date)
    rows = (db.query(VitalsLiftSession)
            .filter(VitalsLiftSession.expo_user_id == expo_user_id,
                    VitalsLiftSession.date == d)
            .order_by(desc(VitalsLiftSession.created_at))
            .all())
    sessions = []
    for r in rows:
        exs = (db.query(LiftExerciseEntry)
               .filter(LiftExerciseEntry.lift_session_id == r.id)
               .all())
        sessions.append({
            "id": r.id,
            "completed_lift_mode": r.completed_lift_mode,
            "duration_min": float(r.duration_min) if r.duration_min else None,
            "top_set_rpe": float(r.top_set_rpe) if r.top_set_rpe else None,
            "pump_quality_score": r.pump_quality_score,
            "notes": r.notes,
            "exercises": [{"name": e.exercise_name_raw, "sets": e.sets_completed,
                           "reps": e.reps_per_set, "load_lbs": float(e.load_lbs) if e.load_lbs else None,
                           "rpe": float(e.rpe) if e.rpe else None} for e in exs],
        })
    return {"sessions": sessions}


@router.post("/lift/save", include_in_schema=False)
async def save_lift(request: Request, db: Session = Depends(get_db)):
    from datetime import date as ddate
    body = await request.json()
    expo_user_id = body.get("expo_user_id", _EXPO_USER_ID)
    d = ddate.fromisoformat(body["date"])
    session = VitalsLiftSession(
        expo_user_id=expo_user_id,
        date=d,
        completed_lift_mode=body.get("completed_lift_mode") or None,
        duration_min=body.get("duration_min") or None,
        top_set_rpe=body.get("top_set_rpe") or None,
        pump_quality_score=body.get("pump_quality_score") or None,
        rep_speed_subjective_score=body.get("rep_speed") or None,
        notes=body.get("notes") or None,
    )
    db.add(session)
    db.flush()
    for ex in body.get("exercises", []):
        if not ex.get("name"): continue
        entry = LiftExerciseEntry(
            expo_user_id=expo_user_id,
            date=d,
            lift_session_id=session.id,
            exercise_name_raw=ex["name"],
            sets_completed=ex.get("sets") or None,
            reps_per_set=ex.get("reps") or None,
            load_lbs=ex.get("load_lbs") or None,
            rpe=ex.get("rpe") or None,
            set_type="working",
        )
        db.add(entry)
    db.commit()
    return {"ok": True, "id": session.id}


_LIFT_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1">
<meta name="apple-mobile-web-app-capable" content="yes">
<title>ArcForge — Lift</title>
<style>
""" + _CSS_VARS + """
.ex-row{display:grid;grid-template-columns:1fr 48px 48px 72px 52px 36px;gap:6px;padding:10px 12px;border-bottom:1px solid #1a1a1a;align-items:center}
.ex-row:last-of-type{border-bottom:none}
.ex-input{background:var(--input);border:1px solid var(--border);border-radius:7px;color:var(--text);font-size:.85rem;padding:6px 6px;text-align:center;width:100%;-moz-appearance:textfield}
.ex-input::-webkit-outer-spin-button,.ex-input::-webkit-inner-spin-button{-webkit-appearance:none}
.ex-input:focus{outline:none;border-color:var(--accent)}
.ex-name{background:var(--input);border:1px solid var(--border);border-radius:7px;color:var(--text);font-size:.85rem;padding:6px 8px;width:100%}
.ex-name:focus{outline:none;border-color:var(--accent)}
.ex-hdr{display:grid;grid-template-columns:1fr 48px 48px 72px 52px 36px;gap:6px;padding:6px 12px;font-size:.6rem;color:var(--muted);text-transform:uppercase;letter-spacing:.5px}
.del-btn{background:none;border:none;color:var(--muted);font-size:1.1rem;cursor:pointer;padding:4px;line-height:1}
.del-btn:active{color:var(--red)}
.add-ex-btn{width:calc(100% - 24px);margin:10px 12px;padding:10px;background:transparent;border:1px dashed var(--border);border-radius:8px;color:var(--muted);font-size:.85rem;cursor:pointer;text-align:center}
.add-ex-btn:active{border-color:var(--accent);color:var(--accent)}
.vol-bar{background:#111;padding:10px 16px;font-size:.78rem;color:var(--muted);display:flex;gap:16px;flex-wrap:wrap}
.vol-bar span{color:var(--text);font-weight:600}
</style>
</head>
<body>
<div class="header">
  <div class="header-top">
    <h1>⚡ ArcForge — Lift</h1>
  </div>
  <div class="date-row">
    <button class="date-nav" onclick="shiftDate(-1)">‹</button>
    <input type="date" id="date-input" onchange="loadDate()">
    <button class="date-nav" onclick="shiftDate(1)">›</button>
  </div>
</div>

<div class="section">
  <div class="section-title">Session</div>
  <div class="row">
    <label>Mode</label>
    <div class="right">
      <select id="completed_lift_mode">
        <option value="hypertrophy_build">Hypertrophy Build</option>
        <option value="neural_tension">Neural Tension</option>
        <option value="pump">Pump</option>
        <option value="recovery_patterning">Recovery Patterning</option>
        <option value="mobility">Mobility</option>
        <option value="off">Off</option>
      </select>
    </div>
  </div>
  <div class="row">
    <label>Duration</label>
    <div class="right"><input type="number" id="duration_min" placeholder="—"><span class="unit">min</span></div>
  </div>
  <div class="row">
    <label>Top Set RPE<div class="hint">how hard was the hardest set?</div></label>
    <div class="right"><input type="number" id="top_set_rpe" placeholder="—" min="1" max="10" step="0.5"><span class="unit">/10</span></div>
  </div>
</div>

<div class="section" style="margin-top:12px">
  <div class="section-title">Pump Quality</div>
  <div class="score-row" style="padding:12px 16px">
    <div style="display:flex;gap:8px;width:100%">
      <button class="score-btn" onclick="setPump(1)">1</button>
      <button class="score-btn" onclick="setPump(2)">2</button>
      <button class="score-btn" onclick="setPump(3)">3</button>
      <button class="score-btn" onclick="setPump(4)">4</button>
      <button class="score-btn" onclick="setPump(5)">5</button>
    </div>
  </div>
</div>

<div class="section" style="margin-top:12px">
  <div class="section-title">Exercises</div>
  <div class="ex-hdr"><span>Exercise</span><span style="text-align:center">Sets</span><span style="text-align:center">Reps</span><span style="text-align:center">Load (lbs)</span><span style="text-align:center">RPE</span><span></span></div>
  <div id="ex-list"></div>
  <div class="vol-bar" id="vol-bar" style="display:none">Volume: <span id="vol-val">0</span> lbs · <span id="ex-count">0</span> exercises</div>
  <button class="add-ex-btn" onclick="addExercise()">+ Add Exercise</button>
</div>

<div id="history-section" style="display:none">
  <div class="hist-card">
    <h3>Today's Sessions</h3>
    <div id="history-list"></div>
  </div>
</div>

<div class="submit-wrap">
  <button class="submit-btn" onclick="saveLift()">Log Session</button>
</div>

<div id="toast" class="toast"></div>
""" + _NAV_HTML('lift') + """
<script>
const EXPO="beeb9b83-58d3-4a22-a1a7-a252fd86a0e0";
let _pump=null;
let _exCount=0;

function today(){const n=new Date();return n.getFullYear()+'-'+String(n.getMonth()+1).padStart(2,'0')+'-'+String(n.getDate()).padStart(2,'0');}
function shiftDate(d){const dt=new Date(document.getElementById('date-input').value+'T12:00:00');dt.setDate(dt.getDate()+d);document.getElementById('date-input').value=dt.toISOString().slice(0,10);loadDate();}

function setPump(v){
  _pump=v;
  document.querySelectorAll('.score-btn').forEach((b,i)=>b.classList.toggle('active',i+1===v));
}

function addExercise(){
  _exCount++;
  const id='ex'+_exCount;
  const div=document.createElement('div');
  div.className='ex-row';div.id=id;
  div.innerHTML=`
    <input class="ex-name" type="text" placeholder="Exercise name" oninput="calcVol()">
    <input class="ex-input" type="number" placeholder="—" min="1" title="Sets" oninput="calcVol()">
    <input class="ex-input" type="number" placeholder="—" min="1" title="Reps" oninput="calcVol()">
    <input class="ex-input" type="number" placeholder="—" min="0" step="2.5" title="Load lbs" oninput="calcVol()">
    <input class="ex-input" type="number" placeholder="—" min="1" max="10" step="0.5" title="RPE" oninput="calcVol()">
    <button class="del-btn" onclick="this.closest('.ex-row').remove();calcVol()">✕</button>`;
  document.getElementById('ex-list').appendChild(div);
  div.querySelector('.ex-name').focus();
  calcVol();
}

function calcVol(){
  const rows=document.querySelectorAll('#ex-list .ex-row');
  let vol=0,cnt=0;
  rows.forEach(row=>{
    const inputs=row.querySelectorAll('input');
    const sets=parseFloat(inputs[1].value)||0;
    const reps=parseFloat(inputs[2].value)||0;
    const load=parseFloat(inputs[3].value)||0;
    if(sets&&reps&&load){vol+=sets*reps*load;cnt++;}
    else if(inputs[0].value){cnt++;}
  });
  const bar=document.getElementById('vol-bar');
  bar.style.display=rows.length?'flex':'none';
  document.getElementById('vol-val').textContent=Math.round(vol).toLocaleString();
  document.getElementById('ex-count').textContent=cnt;
}

function getExercises(){
  const rows=document.querySelectorAll('#ex-list .ex-row');
  const exs=[];
  rows.forEach(row=>{
    const inputs=row.querySelectorAll('input');
    const name=inputs[0].value.trim();
    if(!name)return;
    exs.push({
      name,
      sets:parseInt(inputs[1].value)||null,
      reps:parseInt(inputs[2].value)||null,
      load_lbs:parseFloat(inputs[3].value)||null,
      rpe:parseFloat(inputs[4].value)||null,
    });
  });
  return exs;
}

async function loadDate(){
  const date=document.getElementById('date-input').value||today();
  document.getElementById('date-input').value=date;
  const r=await fetch(`/lift/data?expo_user_id=${EXPO}&date=${date}`);
  const d=await r.json();
  renderHistory(d.sessions||[]);
}

function renderHistory(sessions){
  const sec=document.getElementById('history-section');
  const list=document.getElementById('history-list');
  if(!sessions.length){sec.style.display='none';return;}
  sec.style.display='block';
  list.innerHTML=sessions.map(s=>`
    <div class="hist-row">
      <span class="hist-lbl">${(s.completed_lift_mode||'session').replace(/_/g,' ')}</span>
      <span class="hist-val">${s.duration_min||'—'}min · ${s.exercises.length} exercises · RPE ${s.top_set_rpe||'—'}</span>
    </div>
  `).join('');
}

async function saveLift(){
  const btn=document.querySelector('.submit-btn');
  btn.disabled=true;btn.textContent='Saving…';
  const payload={
    expo_user_id:EXPO,
    date:document.getElementById('date-input').value||today(),
    completed_lift_mode:document.getElementById('completed_lift_mode').value,
    duration_min:parseFloat(document.getElementById('duration_min').value)||null,
    top_set_rpe:parseFloat(document.getElementById('top_set_rpe').value)||null,
    pump_quality_score:_pump,
    exercises:getExercises(),
  };
  const res=await fetch('/lift/save',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
  if(res.ok){
    showToast('Session logged ✓','ok');
    btn.textContent='Log Session';btn.disabled=false;
    document.getElementById('ex-list').innerHTML='';
    calcVol();_pump=null;
    document.querySelectorAll('.score-btn').forEach(b=>b.classList.remove('active'));
    ['duration_min','top_set_rpe'].forEach(id=>document.getElementById(id).value='');
    loadDate();
  } else {showToast('Error — try again','err');btn.disabled=false;btn.textContent='Log Session';}
}

""" + _TOAST_JS + """
document.getElementById('date-input').value=today();
loadDate();
</script>
</body>
</html>"""


# ═══════════════════════════════════════════════════════════════════════════════
# SYSTEM PAGE
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/system/data", include_in_schema=False)
def get_system_data(expo_user_id: str, db: Session = Depends(get_db)):
    from datetime import date as ddate, timedelta
    today = ddate.today()
    week_ago = today - timedelta(days=6)
    rows = (db.query(VitalsDailyLog)
            .filter(VitalsDailyLog.expo_user_id == expo_user_id,
                    VitalsDailyLog.date >= week_ago,
                    VitalsDailyLog.date <= today)
            .order_by(VitalsDailyLog.date)
            .all())
    days = []
    for r in rows:
        adh = r.meal_adherence_json or {}
        days.append({
            "date": str(r.date),
            "weight": float(r.body_weight_lb) if r.body_weight_lb else None,
            "bf_pct": float(r.body_fat_pct) if r.body_fat_pct else None,
            "ffm": float(r.fat_free_mass_lb) if r.fat_free_mass_lb else None,
            "sleep_hr": round(float(r.sleep_duration_min)/60, 1) if r.sleep_duration_min else None,
            "hrv": float(r.hrv_ms) if r.hrv_ms else None,
            "rhr": float(r.resting_hr_bpm) if r.resting_hr_bpm else None,
            "steps": r.step_count,
            "kcal_consumed": float(r.kcal_actual) if r.kcal_actual else None,
            "day_type": adh.get("day_type"),
            "cardio_mode": r.actual_cardio_mode,
            "lift_mode": r.completed_lift_mode,
            "motivation": r.motivation_score,
            "soreness": r.soreness_score,
            "mood": r.mood_stability_score,
        })
    return {"days": days, "today": str(today)}


_SYSTEM_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1">
<meta name="apple-mobile-web-app-capable" content="yes">
<title>ArcForge — System State</title>
<style>
""" + _CSS_VARS + """
.score-dot{display:inline-block;width:10px;height:10px;border-radius:50%;margin-right:6px}
.trend-up{color:var(--green)}
.trend-down{color:var(--red)}
.trend-flat{color:var(--muted)}
</style>
</head>
<body>
<div class="header">
  <div class="header-top">
    <h1>⚡ ArcForge — System</h1>
    <span id="today-lbl" style="font-size:.75rem;color:var(--muted)"></span>
  </div>
  <div style="font-size:.7rem;color:var(--muted);margin-top:6px">7-day rolling state · live from log</div>
</div>

<div id="loading" style="text-align:center;padding:40px;color:var(--muted);font-size:.9rem">Loading system state…</div>
<div id="content" style="display:none"></div>

<div id="toast" class="toast"></div>
""" + _NAV_HTML('system') + """
<script>
const EXPO="beeb9b83-58d3-4a22-a1a7-a252fd86a0e0";

const DAY_COLORS={build:'#4ade80',surge:'#f97316',reset:'#60a5fa',resensitize:'#a78bfa'};
const DAY_BG={build:'#1a2a1a',surge:'#2a1a0a',reset:'#1a1a2a',resensitize:'#2a1a2a'};

async function loadSystem(){
  const r=await fetch(`/system/data?expo_user_id=${EXPO}`);
  const d=await r.json();
  document.getElementById('loading').style.display='none';
  document.getElementById('content').style.display='block';
  document.getElementById('today-lbl').textContent=d.today;
  render(d.days, d.today);
}

function avg(arr, key){
  const vals=arr.map(d=>d[key]).filter(v=>v!=null);
  return vals.length?Math.round(vals.reduce((a,b)=>a+b,0)/vals.length*10)/10:null;
}

function render(days, today){
  const c=document.getElementById('content');
  if(!days.length){
    c.innerHTML='<div style="text-align:center;padding:40px;color:var(--muted)">No log data in the past 7 days.<br>Start logging on the Log tab.</div>';
    return;
  }

  // Stats row
  const avgWeight=avg(days,'weight');
  const avgSleep=avg(days,'sleep_hr');
  const avgHrv=avg(days,'hrv');

  // Day type history
  const dayBadges=days.map(d=>{
    const dt=d.day_type||'—';
    const col=DAY_COLORS[dt]||'#666';
    const bg=DAY_BG[dt]||'#1a1a1a';
    const label=d.date.slice(5); // MM-DD
    return `<div style="text-align:center;flex:1">
      <div style="font-size:.6rem;color:var(--muted);margin-bottom:4px">${label}</div>
      <div style="background:${bg};color:${col};border-radius:6px;padding:4px 2px;font-size:.62rem;font-weight:700">${dt}</div>
    </div>`;
  }).join('');

  // Weight sparkline
  const weights=days.map(d=>d.weight).filter(v=>v);
  const wMax=Math.max(...weights)||1;
  const wMin=Math.min(...weights)||0;
  const wRange=wMax-wMin||1;
  const wBars=days.map(d=>{
    const h=d.weight?Math.max(8,Math.round(((d.weight-wMin)/wRange)*40)+8):4;
    const active=d.date===today;
    return `<div class="spark-bar${active?'':' dim'}" style="height:${h}px" title="${d.weight||'—'} lbs"></div>`;
  }).join('');

  // Readiness score (motivation avg)
  const motAvg=avg(days,'motivation');
  const sorenessAvg=avg(days,'soreness');

  // Build HTML
  c.innerHTML=`
    <div class="stat-grid">
      <div class="stat-box">
        <div class="stat-val">${avgWeight||'—'}</div>
        <div class="stat-lbl">Avg Weight<br>lbs</div>
      </div>
      <div class="stat-box">
        <div class="stat-val">${avgSleep||'—'}</div>
        <div class="stat-lbl">Avg Sleep<br>hrs</div>
      </div>
      <div class="stat-box">
        <div class="stat-val">${avgHrv||'—'}</div>
        <div class="stat-lbl">Avg HRV<br>ms</div>
      </div>
    </div>

    <div class="sys-section">
      <div class="sys-section-title">Day Type — 7 Days</div>
      <div style="display:flex;gap:4px;padding:12px 12px 8px">${dayBadges}</div>
    </div>

    ${weights.length>=2?`
    <div class="sys-section">
      <div class="sys-section-title">Body Weight Trend</div>
      <div class="spark-row">${wBars}</div>
      <div style="display:flex;justify-content:space-between;padding:4px 16px 10px;font-size:.7rem;color:var(--muted)">
        <span>${wMin.toFixed(1)} lb low</span><span>${wMax.toFixed(1)} lb high</span>
      </div>
    </div>`:''}

    <div class="sys-section">
      <div class="sys-section-title">Last 7 Days Log</div>
      ${days.slice().reverse().map(d=>`
        <div class="hist-row" style="padding:10px 16px">
          <span>
            <div style="font-size:.75rem;font-weight:600;color:var(--text)">${d.date}</div>
            <div style="font-size:.65rem;color:var(--muted);margin-top:2px">
              ${d.day_type?`<span style="color:${DAY_COLORS[d.day_type]||'#666'}">${d.day_type}</span> · `:''
              }${d.kcal_consumed?d.kcal_consumed+' kcal · ':''
              }${d.sleep_hr?d.sleep_hr+'h sleep':''}</div>
          </span>
          <span style="text-align:right">
            ${d.weight?`<div style="font-weight:600">${d.weight} lb</div>`:''}
            ${d.hrv?`<div style="font-size:.7rem;color:var(--teal)">${d.hrv} ms HRV</div>`:''}
          </span>
        </div>
      `).join('')}
    </div>

    ${(motAvg||sorenessAvg)?`
    <div class="sys-section">
      <div class="sys-section-title">Readiness Signals (7-day avg)</div>
      ${motAvg!=null?`<div class="hist-row" style="padding:10px 16px"><span class="hist-lbl">Motivation</span><span class="hist-val">${motAvg} / 5</span></div>`:''}
      ${sorenessAvg!=null?`<div class="hist-row" style="padding:10px 16px"><span class="hist-lbl">Soreness</span><span class="hist-val">${sorenessAvg} / 5</span></div>`:''}
    </div>`:''}

    <div style="height:8px"></div>
  `;
}

""" + _TOAST_JS + """
loadSystem();
</script>
</body>
</html>"""


# ═══════════════════════════════════════════════════════════════════════════════
# ROUTES
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/cardio", response_class=HTMLResponse, include_in_schema=False)
def cardio_page():
    return _CARDIO_HTML

@router.get("/lift", response_class=HTMLResponse, include_in_schema=False)
def lift_page():
    return _LIFT_HTML

@router.get("/system", response_class=HTMLResponse, include_in_schema=False)
def system_page():
    return _SYSTEM_HTML

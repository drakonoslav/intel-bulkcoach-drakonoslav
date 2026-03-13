from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse, FileResponse
from sqlalchemy.orm import Session
from pathlib import Path
from typing import Optional

from app.database import get_db
from app.vitals_models import VitalsDailyLog

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


@router.get("/log/meal-plan", include_in_schema=False)
def get_meal_plan_for_day(day_type: str = "build"):
    """Return the food plan for a given macro day type."""
    from app.meal_plan import get_meal_plan
    return {"dayType": day_type, "plan": get_meal_plan(day_type)}


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
body{padding:0 0 80px 0}

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

.toast{position:fixed;bottom:30px;left:50%;transform:translateX(-50%);background:#1a1a1a;border:1px solid var(--border);border-radius:10px;padding:12px 20px;font-size:.85rem;color:var(--text);z-index:999;display:none;white-space:nowrap}
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
/* ── Meal Adherence ── */
.adh-badge{font-size:.7rem;font-weight:600;background:#1c1c1c;color:var(--accent);padding:2px 8px;border-radius:20px;margin-left:8px;vertical-align:middle;text-transform:capitalize}
.adh-row{padding:10px 0;border-bottom:1px solid var(--border)}
.adh-row:last-child{border-bottom:none}
.adh-win-label{display:flex;align-items:baseline;gap:8px;margin-bottom:7px}
.adh-win-name{font-size:.88rem;font-weight:600;color:var(--text)}
.adh-win-time{font-size:.72rem;color:var(--muted)}
.adh-btns{display:flex;gap:6px}
.adh-btn{flex:1;padding:8px 4px;border-radius:8px;border:1.5px solid #333;background:transparent;color:var(--muted);font-size:.75rem;font-weight:600;cursor:pointer;text-align:center;transition:background .15s,border-color .15s,color .15s;-webkit-tap-highlight-color:transparent}
.adh-btn:active{opacity:.75}
.adh-kcal{display:block;font-size:.65rem;font-weight:400;margin-top:1px;color:inherit;opacity:.8}
.adh-btn.adh-base.active{background:#14532d;border-color:var(--green);color:var(--green)}
.adh-btn.adh-adj.active{background:#431407;border-color:var(--accent);color:var(--accent)}
.adh-btn.adh-skip.active{background:#450a0a;border-color:var(--red);color:var(--red)}
.adh-tally-row{display:flex;justify-content:space-between;align-items:center;padding:14px 0 10px;border-top:1px solid var(--border);margin-top:4px}
.adh-tally-label{font-size:.78rem;font-weight:600;color:var(--muted);text-transform:uppercase;letter-spacing:.5px}
.adh-save-btn{width:100%;padding:13px;background:#1c1c1c;border:1.5px solid var(--accent);border-radius:var(--radius);color:var(--accent);font-size:.95rem;font-weight:700;cursor:pointer;letter-spacing:.4px;margin-top:4px}
.adh-save-btn:active{opacity:.8}
.adh-save-btn:disabled{opacity:.4;cursor:not-allowed}
.adh-carryover{margin-top:14px;background:#0f1f0f;border:1px solid #1f4b1f;border-radius:10px;padding:12px 14px;display:flex;flex-direction:column;gap:4px}
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
    <div><label>Skeletal Muscle %</label></div>
    <div class="right"><input type="number" id="sm_pct" placeholder="42.0" step="0.1"><span class="unit">%</span></div>
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

<!-- MEAL ADHERENCE -->
<div class="section">
  <div class="section-title">Meal Adherence <span id="adh-day-badge" class="adh-badge">Build Day</span></div>
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

function clearForm(){
  ['sleep_onset','sleep_wake','rem','core','deep','awake'].forEach(id=>{
    document.getElementById(id).value='';
  });
  ['hrv','rhr','temp_f','weight','bf_pct','sm_pct',
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
    body_fat_pct:       num('bf_pct'),
    skeletal_muscle_pct: num('sm_pct'),
    waist_at_navel_in:  num('waist'),
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

// ── Meal Adherence ────────────────────────────────────────────────────────────
const ADH_WINDOWS = [
  {name:"Pre-Cardio",      time:"05:30", intel:false},
  {name:"Post-Cardio",     time:"06:45", intel:false},
  {name:"Mid-Morning",     time:"11:30", intel:false},
  {name:"Pre-Lift",        time:"15:45", intel:false},
  {name:"Post-Lift",       time:"18:20", intel:false},
  {name:"Evening Meal",    time:"20:00", intel:false},
  {name:"Evening Protein", time:"21:30", intel:true},
];
let _adhState    = {};   // {windowName: "base"|"adj"|"skip"|null}
let _adhPlan     = {};   // {windowName: {base_kcal, adj_kcal}}
let _adhDayType  = "build";
let _adhTargetKcal = 2696;

function resetAdherence(){
  ADH_WINDOWS.forEach(w=>{ _adhState[w.name]=null; _adhPlan[w.name]={base_kcal:0,adj_kcal:0}; });
  const carry=document.getElementById("adh-carryover");
  if(carry) carry.style.display="none";
  renderAdherenceWindows();
  updateAdherenceTally();
}

function loadAdherencePlan(dayType){
  _adhDayType = dayType||"build";
  const badge=document.getElementById("adh-day-badge");
  if(badge) badge.textContent=_adhDayType.charAt(0).toUpperCase()+_adhDayType.slice(1)+" Day";
  Promise.all([
    fetch("/log/meal-plan?day_type=build").then(r=>r.json()),
    fetch(`/log/meal-plan?day_type=${_adhDayType}`).then(r=>r.json()),
  ]).then(([bp,ap])=>{
    const b=bp.plan||{}, a=ap.plan||{};
    let tot=0;
    ADH_WINDOWS.forEach(w=>{
      _adhPlan[w.name]={base_kcal:b[w.name]?.kcal??0, adj_kcal:a[w.name]?.kcal??0};
      tot+=b[w.name]?.kcal??0;
    });
    _adhTargetKcal=tot;
    renderAdherenceWindows();
    updateAdherenceTally();
  });
}

function renderAdherenceWindows(){
  const el=document.getElementById("adh-windows");
  if(!el) return;
  el.innerHTML=ADH_WINDOWS.map(w=>{
    const pl=_adhPlan[w.name]||{base_kcal:0,adj_kcal:0};
    const bk=pl.base_kcal, ak=pl.adj_kcal;
    const st=_adhState[w.name];
    const winId=w.name.replace(/\s+/g,'-');
    const intelNote=w.intel?'<span style="font-size:.65rem;color:var(--muted)"> · Intel-managed</span>':'';
    return `<div class="adh-row" id="adh-row-${winId}">
  <div class="adh-win-label">
    <span class="adh-win-name">${w.name}</span>${intelNote}
    <span class="adh-win-time">${w.time}</span>
  </div>
  <div class="adh-btns">
    <button class="adh-btn adh-base${st==='base'?' active':''}"
      onclick="tapAdherence('${w.name}','base')">
      Base${bk?`<span class="adh-kcal">${bk} kcal</span>`:''}
    </button>
    <button class="adh-btn adh-adj${st==='adj'?' active':''}"
      onclick="tapAdherence('${w.name}','adj')">
      Adj${ak?`<span class="adh-kcal">${ak} kcal</span>`:''}
    </button>
    <button class="adh-btn adh-skip${st==='skip'?' active':''}"
      onclick="tapAdherence('${w.name}','skip')">
      Skip
    </button>
  </div>
</div>`;
  }).join('');
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
  _adhDayType=dayType||"build";
  const badge=document.getElementById("adh-day-badge");
  if(badge) badge.textContent=_adhDayType.charAt(0).toUpperCase()+_adhDayType.slice(1)+" Day";
  ADH_WINDOWS.forEach(w=>{
    const saved=adherenceJson[w.name];
    if(saved?.status&&saved.status!=="not_logged"){
      _adhState[w.name]=saved.status;
      _adhPlan[w.name]={base_kcal:saved.base_kcal||0,adj_kcal:saved.adj_kcal||0};
    } else { _adhState[w.name]=null; }
  });
  _adhTargetKcal=adherenceJson.target_kcal||2696;
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
}

// ── Ingredient macro density (brain's own values) ─────────────────────────────
const IMACRO = {
  "Banana":       {p:1.00,  c:27.00, f:0.00,  kcal:104.0},
  "Oats":         {p:0.17,  c:0.67,  f:0.06,  kcal:3.90},
  "Whey":         {p:0.80,  c:0.08,  f:0.05,  kcal:3.97},
  "MCT Powder":   {p:0.00,  c:0.00,  f:0.90,  kcal:8.10},
  "Dextrin":      {p:0.00,  c:1.00,  f:0.00,  kcal:4.00},
  "Greek Yogurt": {p:20.00, c:9.00,  f:0.00,  kcal:116.0},
  "Flaxseed":     {p:0.20,  c:0.27,  f:0.40,  kcal:5.48},
  "Eggs":         {p:6.00,  c:0.00,  f:5.00,  kcal:70.0},
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
</body>
</html>"""


@router.get("/log", response_class=HTMLResponse, include_in_schema=False)
def daily_log_page():
    return _HTML

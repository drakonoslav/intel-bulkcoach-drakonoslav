import logging
import traceback
import uuid
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

logger = logging.getLogger(__name__)

import os
from urllib.parse import urlparse

from app.database import engine, SessionLocal, DATABASE_URL
from app.models import Base
from app.seed import seed_from_csv
from app.routers import datasets, matrix, volume, reports, optimizer, composite, presets, weekly_optimizer, lifts, weekly_muscles, muscle_dose, coach, admin, muscle_day

_parsed = urlparse(DATABASE_URL)
_dialect = _parsed.scheme.split("+")[0] if "+" in _parsed.scheme else _parsed.scheme
print(f"[startup] DB dialect={_dialect} host={_parsed.hostname} port={_parsed.port} dbname={_parsed.path.lstrip('/')}")
if _dialect not in ("postgresql", "postgres"):
    raise RuntimeError(f"FATAL: expected postgres, got dialect={_dialect}. No sqlite fallback allowed.")

Base.metadata.create_all(bind=engine)

with SessionLocal() as db:
    seed_from_csv(db)

app = FastAPI(
    title="Lifting Intel — Biomechanical Engine",
    description="Biomechanical computation engine with real activation matrices from CSV.",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    error_id = uuid.uuid4().hex[:12]
    logger.error(
        "unhandled error_id=%s method=%s path=%s\n%s",
        error_id,
        request.method,
        request.url.path,
        traceback.format_exc(),
    )
    return JSONResponse(
        status_code=500,
        content={
            "detail": "internal_error",
            "error_id": error_id,
            "where": f"{request.method} {request.url.path}",
            "hint": str(exc)[:200],
        },
    )


app.include_router(datasets.router)
app.include_router(matrix.router)
app.include_router(volume.router)
app.include_router(reports.router)
app.include_router(optimizer.router)
app.include_router(composite.router)
app.include_router(presets.router)
app.include_router(weekly_optimizer.router)
app.include_router(lifts.router)
app.include_router(weekly_muscles.router)
app.include_router(muscle_dose.router)
app.include_router(coach.router)
app.include_router(admin.router)
app.include_router(muscle_day.router)


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def root():
    return """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Lifting Intel</title>
<style>
  *{box-sizing:border-box;margin:0;padding:0}
  body{font-family:system-ui,sans-serif;background:#0a0a0a;color:#e0e0e0;padding:40px 20px}
  h1{font-size:1.8rem;font-weight:700;margin-bottom:4px}
  .sub{color:#777;font-size:.85rem;margin-bottom:36px}
  .grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:14px;max-width:960px}
  .card{background:#141414;border:1px solid #222;border-radius:10px;padding:22px}
  .card h2{font-size:.7rem;text-transform:uppercase;letter-spacing:1px;color:#555;margin-bottom:8px}
  .card h3{font-size:1rem;font-weight:600;margin-bottom:6px}
  .card p{font-size:.82rem;color:#888;line-height:1.5;margin-bottom:12px}
  .route{font-family:monospace;font-size:.78rem;margin-bottom:4px}
  .route a{color:#bbb;text-decoration:none}
  .route a:hover{color:#60a5fa;text-decoration:underline}
  .method{font-size:.65rem;font-weight:700;padding:2px 6px;border-radius:3px;margin-right:5px}
  .get{background:#14532d;color:#4ade80}.post{background:#1e3a5f;color:#60a5fa}
  a.btn{display:inline-block;margin-top:8px;padding:7px 14px;background:#1d4ed8;color:#fff;border-radius:7px;text-decoration:none;font-size:.82rem}
  .section-title{font-size:.75rem;text-transform:uppercase;letter-spacing:1.5px;color:#444;margin:28px 0 10px;max-width:960px}
</style>
</head>
<body>
<h1>Lifting Intel</h1>
<p class="sub">Biomechanical Computation Engine &mdash; 92 exercises &times; 26 muscles across 5 matrix versions</p>

<div class="section-title">Matrices</div>
<div class="grid">
  <div class="card">
    <h2>Matrix v2</h2>
    <h3>Activation (92&times;26)</h3>
    <p>Integer scale 0&ndash;5. Raw exercise-muscle activation.</p>
    <div class="route"><span class="method get">GET</span><a href="/matrix/v2">/matrix/v2</a></div>
    <div class="route"><span class="method get">GET</span><a href="/matrix/v2?exercise=Back+Squat+(high-bar)">/matrix/v2?exercise=Back+Squat+(high-bar)</a></div>
  </div>
  <div class="card">
    <h2>Matrix v2</h2>
    <h3>Role-Weighted (92&times;26)</h3>
    <p>Float 0&ndash;1. Hierarchical role weighting per muscle.</p>
    <div class="route"><span class="method get">GET</span><a href="/matrix/role-weighted-v2">/matrix/role-weighted-v2</a></div>
  </div>
  <div class="card">
    <h2>Matrix v3</h2>
    <h3>Phase Model (92&times;26&times;3)</h3>
    <p>Float 0&ndash;5. Per-phase activation: initiation, midrange, lockout.</p>
    <div class="route"><span class="method get">GET</span><a href="/matrix/v3?phase=initiation">/matrix/v3?phase=initiation</a></div>
    <div class="route"><span class="method get">GET</span><a href="/matrix/v3?phase=midrange">/matrix/v3?phase=midrange</a></div>
    <div class="route"><span class="method get">GET</span><a href="/matrix/v3?phase=lockout">/matrix/v3?phase=lockout</a></div>
  </div>
  <div class="card">
    <h2>Matrix v4</h2>
    <h3>Bottleneck Coefficients (92&times;26)</h3>
    <p>Float 0&ndash;1. Per-muscle bottleneck pressure.</p>
    <div class="route"><span class="method get">GET</span><a href="/matrix/v4/bottleneck">/matrix/v4/bottleneck</a></div>
  </div>
  <div class="card">
    <h2>Matrix v5</h2>
    <h3>Stabilization (92&times;26&times;2)</h3>
    <p>Float 0&ndash;1. Dynamic and stability components.</p>
    <div class="route"><span class="method get">GET</span><a href="/matrix/v5?component=dynamic">/matrix/v5?component=dynamic</a></div>
    <div class="route"><span class="method get">GET</span><a href="/matrix/v5?component=stability">/matrix/v5?component=stability</a></div>
  </div>
  <div class="card">
    <h2>Datasets</h2>
    <h3>Version Registry</h3>
    <p>All matrix versions with row counts.</p>
    <div class="route"><span class="method get">GET</span><a href="/datasets">/datasets</a></div>
  </div>
</div>

<div class="section-title">Composite &amp; Presets</div>
<div class="grid">
  <div class="card">
    <h2>Composite</h2>
    <h3>Muscle Profile Index (26 muscles)</h3>
    <p>Composite score (0&ndash;100) with full JSONB payload per muscle.</p>
    <div class="route"><span class="method get">GET</span><a href="/composite/muscles">/composite/muscles</a></div>
    <div class="route"><span class="method get">GET</span><a href="/composite/muscles?preset=hypertrophy">/composite/muscles?preset=hypertrophy</a></div>
    <div class="route"><span class="method get">GET</span><a href="/composite/muscles?preset=strength">/composite/muscles?preset=strength</a></div>
    <div class="route"><span class="method get">GET</span><a href="/composite/muscles?preset=injury">/composite/muscles?preset=injury</a></div>
  </div>
  <div class="card">
    <h2>Presets</h2>
    <h3>Weight Vectors</h3>
    <p>Named presets (hypertrophy, strength, injury) with weight distributions.</p>
    <div class="route"><span class="method get">GET</span><a href="/presets">/presets</a></div>
  </div>
</div>

<div class="section-title">Lift Logging</div>
<div class="grid">
  <div class="card">
    <h2>Lifts</h2>
    <h3>Set Logging</h3>
    <p>Log lift sets with exercise resolution, auto-computed tonnage.</p>
    <div class="route"><span class="method post">POST</span>/lifts/sets</div>
    <div class="route"><span class="method post">POST</span>/lifts/sets/batch</div>
    <div class="route"><span class="method get">GET</span><a href="/lifts/sets?from=2026-02-01&amp;to=2026-03-01">/lifts/sets?from=2026-02-01&amp;to=2026-03-01</a></div>
  </div>
</div>

<div class="section-title">Reports</div>
<div class="grid">
  <div class="card">
    <h2>Weekly Muscles</h2>
    <h3>Multi-Lens Stimulus Report</h3>
    <p>Per-muscle stimulus for an ISO week, viewed through any matrix lens.</p>
    <div class="route"><span class="method get">GET</span><a href="/reports/weekly-muscles?week=2026-W09&amp;lens=v2">/reports/weekly-muscles?week=2026-W09&amp;lens=v2</a></div>
    <div class="route"><span class="method get">GET</span><a href="/reports/weekly-muscles?week=2026-W09&amp;lens=role">/reports/weekly-muscles?lens=role</a></div>
    <div class="route"><span class="method get">GET</span><a href="/reports/weekly-muscles?week=2026-W09&amp;lens=v3">/reports/weekly-muscles?lens=v3</a></div>
    <div class="route"><span class="method get">GET</span><a href="/reports/weekly-muscles?week=2026-W09&amp;lens=v4">/reports/weekly-muscles?lens=v4</a></div>
    <div class="route"><span class="method get">GET</span><a href="/reports/weekly-muscles?week=2026-W09&amp;lens=v5">/reports/weekly-muscles?lens=v5</a></div>
  </div>
  <div class="card">
    <h2>Legacy Reports</h2>
    <h3>Weekly Stimulus (v1)</h3>
    <p>Original weekly report using volume_logs table.</p>
    <div class="route"><span class="method get">GET</span><a href="/reports/weekly?week=2026-W09">/reports/weekly?week=2026-W09</a></div>
  </div>
</div>

<div class="section-title">Coach</div>
<div class="grid">
  <div class="card">
    <h2>Weekly Balance</h2>
    <h3>Underfed vs Overtaxed</h3>
    <p>Per-muscle underfed/overtaxed scores with classification. Uses direct dose, bottleneck, and stability signals.</p>
    <div class="route"><span class="method get">GET</span><a href="/coach/weekly-balance?week=2026-W09">/coach/weekly-balance?week=2026-W09</a></div>
    <div class="route"><span class="method get">GET</span><a href="/coach/weekly-balance?week=2026-W09&amp;lookbackWeeks=4">/coach/weekly-balance?lookbackWeeks=4</a></div>
  </div>
  <div class="card">
    <h2>Session Recommender</h2>
    <h3>Compound vs Isolation</h3>
    <p>Recommends exercises targeting underfed muscles with redundancy, bottleneck, and stability penalties.</p>
    <div class="route"><span class="method get">GET</span><a href="/coach/recommend-session?date=2026-02-28&amp;mode=compound&amp;slots=hinge:2,squat:2,push:2,pull:2">/coach/recommend-session?mode=compound</a></div>
    <div class="route"><span class="method get">GET</span><a href="/coach/recommend-session?date=2026-02-28&amp;mode=isolation&amp;slots=hinge:2,squat:2,push:2,pull:2">/coach/recommend-session?mode=isolation</a></div>
  </div>
  <div class="card">
    <h2>Session Plans</h2>
    <h3>Plan &amp; Execute Loop</h3>
    <p>Snapshot a recommended plan, log sets, then link them for compliance analysis.</p>
    <div class="route"><span class="method post">POST</span>/coach/session/start</div>
    <div class="route"><span class="method post">POST</span>/coach/session/complete</div>
  </div>
</div>

<div class="section-title">Optimizer</div>
<div class="grid">
  <div class="card">
    <h2>Weekly Template</h2>
    <h3>Slot-Aware Optimizer</h3>
    <p>Greedy selection with redundancy, bottleneck, and stability penalties. Uses exercise_tags for candidate pools.</p>
    <div class="route"><span class="method get">GET</span><a href="/optimizer/weekly-template?preset=hypertrophy">/optimizer/weekly-template?preset=hypertrophy</a></div>
    <div class="route"><span class="method get">GET</span><a href="/optimizer/weekly-template?preset=strength&amp;slots=hinge:3,squat:2,push:2,pull:3">/optimizer/weekly-template?preset=strength&amp;slots=...</a></div>
    <div class="route"><span class="method get">GET</span><a href="/optimizer/weekly-template?preset=injury&amp;redundancyLambda=2.0">/optimizer/weekly-template?preset=injury&amp;redundancyLambda=2.0</a></div>
  </div>
  <div class="card">
    <h2>Legacy Optimizer</h2>
    <h3>Greedy Set-Cover</h3>
    <p>Original coverage-based exercise selection.</p>
    <div class="route"><span class="method get">GET</span><a href="/optimizer?goal=coverage&amp;n=8">/optimizer?goal=coverage&amp;n=8</a></div>
  </div>
</div>

<div class="section-title">API Reference</div>
<div class="grid">
  <div class="card">
    <h2>Docs</h2>
    <h3>Interactive API Docs</h3>
    <a class="btn" href="/docs">Swagger UI</a>
    <a class="btn" href="/redoc" style="background:#374151;margin-left:6px">ReDoc</a>
  </div>
</div>

</body>
</html>"""

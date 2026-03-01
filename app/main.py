from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware

from app.database import engine, SessionLocal
from app.models import Base
from app.seed import seed_all
from app.routers import datasets, matrix, volume, reports, optimizer

Base.metadata.create_all(bind=engine)

with SessionLocal() as db:
    seed_all(db)

app = FastAPI(
    title="Lifting Intel — Biomechanical Engine",
    description=(
        "Biomechanical computation engine. "
        "Versioned activation matrices (v2–v5), composite muscle profiles, "
        "volume tracking, stimulus analysis, and matrix-driven exercise optimization."
    ),
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(datasets.router)
app.include_router(matrix.router)
app.include_router(volume.router)
app.include_router(reports.router)
app.include_router(optimizer.router)


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def admin_ui():
    return """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Lifting Intel — Biomechanical Engine</title>
<style>
  *{box-sizing:border-box;margin:0;padding:0}
  body{font-family:system-ui,-apple-system,sans-serif;background:#0a0a0a;color:#e0e0e0;min-height:100vh;padding:40px 20px}
  h1{font-size:1.8rem;font-weight:700;letter-spacing:-.5px;margin-bottom:4px}
  .sub{color:#777;font-size:.85rem;margin-bottom:36px}
  .grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:14px;max-width:960px}
  .card{background:#141414;border:1px solid #222;border-radius:10px;padding:22px}
  .card h2{font-size:.7rem;text-transform:uppercase;letter-spacing:1.2px;color:#555;margin-bottom:10px}
  .card h3{font-size:1.05rem;font-weight:600;margin-bottom:6px}
  .card p{font-size:.82rem;color:#888;line-height:1.5;margin-bottom:14px}
  .tag{display:inline-block;background:#1a1a1a;border:1px solid #2a2a2a;border-radius:5px;padding:2px 9px;font-size:.72rem;color:#aaa;margin:2px;font-family:monospace}
  a.btn{display:inline-block;margin-top:12px;padding:7px 16px;background:#1d4ed8;color:#fff;border-radius:7px;text-decoration:none;font-size:.82rem;font-weight:500}
  a.btn:hover{background:#1e40af}
  .method{font-size:.65rem;font-weight:700;padding:2px 6px;border-radius:3px;margin-right:5px}
  .get{background:#14532d;color:#4ade80}.post{background:#1e3a5f;color:#60a5fa}
  .route{display:flex;align-items:center;font-family:monospace;font-size:.78rem;color:#bbb;margin-bottom:6px}
  .dim{font-size:.75rem;color:#666;margin-bottom:8px}
</style>
</head>
<body>
<h1>Lifting Intel</h1>
<p class="sub">Biomechanical Computation Engine &mdash; activation matrices, phase decomposition, bottleneck analysis, composite profiling</p>
<div class="grid">
  <div class="card">
    <h2>Datasets</h2>
    <h3>Matrix Registry</h3>
    <p>Query available matrix versions, dimensions, and row counts.</p>
    <div class="route"><span class="method get">GET</span>/datasets</div>
    <div><span class="tag">v2</span><span class="tag">v3</span><span class="tag">v4</span><span class="tag">v5</span><span class="tag">composite</span></div>
  </div>
  <div class="card">
    <h2>v2 — Activation</h2>
    <h3>Base Activation Matrix (92&times;26)</h3>
    <p>Muscle activation levels per exercise. Optional role-weighted view (prime mover / synergist / stabilizer).</p>
    <div class="route"><span class="method get">GET</span>/matrix/v2?exercise=back_squat&amp;include_roles=true</div>
  </div>
  <div class="card">
    <h2>v3 — Phases</h2>
    <h3>Phase-Expanded Matrices</h3>
    <p>Activation decomposed into initiation, mid-range, and lockout phases.</p>
    <div class="route"><span class="method get">GET</span>/matrix/v3?exercise=barbell_bench_press&amp;phase=lockout</div>
  </div>
  <div class="card">
    <h2>v4 — Bottleneck</h2>
    <h3>Bottleneck Coefficients</h3>
    <p>Identifies limiting muscles per exercise. Use <code>limiting_only=true</code> to filter.</p>
    <div class="route"><span class="method get">GET</span>/matrix/v4?exercise=conventional_deadlift&amp;limiting_only=true</div>
  </div>
  <div class="card">
    <h2>v5 — Stabilization</h2>
    <h3>Stabilization &amp; Dynamic Scores</h3>
    <p>Decomposed stabilization vs dynamic contribution per muscle.</p>
    <div class="route"><span class="method get">GET</span>/matrix/v5?exercise=overhead_squat</div>
  </div>
  <div class="card">
    <h2>Composite</h2>
    <h3>Composite Muscle Profile Index</h3>
    <p>Weighted composite integrating activation, phase, bottleneck, and stabilization components.</p>
    <div class="route"><span class="method get">GET</span>/matrix/composite?muscle=gluteus_maximus&amp;min_score=0.3</div>
  </div>
  <div class="card">
    <h2>Volume</h2>
    <h3>Set Logging</h3>
    <p>Ingest logged sets. Auto-computes tonnage and estimated 1RM.</p>
    <div class="route"><span class="method post">POST</span>/volume/ingest</div>
    <div class="route"><span class="method get">GET</span>/volume/logs</div>
  </div>
  <div class="card">
    <h2>Reports</h2>
    <h3>Weekly Stimulus Analysis</h3>
    <p>Aggregate volume by week with per-muscle stimulus derived from activation matrices.</p>
    <div class="route"><span class="method get">GET</span>/reports/weekly?week=2026-W09</div>
  </div>
  <div class="card">
    <h2>Optimizer</h2>
    <h3>Matrix-Driven Selection</h3>
    <p>Select n exercises by coverage, bottleneck, stabilization, or composite score.</p>
    <div class="route"><span class="method get">GET</span>/optimizer?goal=coverage&amp;n=8&amp;target_muscles=gluteus_maximus,biceps_femoris</div>
    <div><span class="tag">coverage</span><span class="tag">bottleneck</span><span class="tag">stabilization</span><span class="tag">composite</span></div>
  </div>
  <div class="card">
    <h2>Docs</h2>
    <h3>Interactive API</h3>
    <p>Full OpenAPI spec with live request testing.</p>
    <a class="btn" href="/docs">Swagger UI</a>
    <a class="btn" href="/redoc" style="background:#374151;margin-left:6px">ReDoc</a>
  </div>
</div>
</body>
</html>"""

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware

from app.database import engine, SessionLocal
from app.models import Base
from app.seed import seed_from_csv
from app.routers import datasets, matrix, volume, reports, optimizer

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

app.include_router(datasets.router)
app.include_router(matrix.router)
app.include_router(volume.router)
app.include_router(reports.router)
app.include_router(optimizer.router)


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
  .grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:14px;max-width:900px}
  .card{background:#141414;border:1px solid #222;border-radius:10px;padding:22px}
  .card h2{font-size:.7rem;text-transform:uppercase;letter-spacing:1px;color:#555;margin-bottom:8px}
  .card h3{font-size:1rem;font-weight:600;margin-bottom:6px}
  .card p{font-size:.82rem;color:#888;line-height:1.5;margin-bottom:12px}
  .route{font-family:monospace;font-size:.78rem;color:#bbb;margin-bottom:4px}
  .method{font-size:.65rem;font-weight:700;padding:2px 6px;border-radius:3px;margin-right:5px}
  .get{background:#14532d;color:#4ade80}.post{background:#1e3a5f;color:#60a5fa}
  a.btn{display:inline-block;margin-top:8px;padding:7px 14px;background:#1d4ed8;color:#fff;border-radius:7px;text-decoration:none;font-size:.82rem}
</style>
</head>
<body>
<h1>Lifting Intel</h1>
<p class="sub">Biomechanical Computation Engine &mdash; real activation matrix (92&times;26, scale 0&ndash;5)</p>
<div class="grid">
  <div class="card">
    <h2>Matrix v2</h2>
    <h3>Activation Matrix (92&times;26)</h3>
    <p>Full exercise-muscle activation matrix. Integer scale 0&ndash;5. Imported from CSV.</p>
    <div class="route"><span class="method get">GET</span>/matrix/v2</div>
    <div class="route"><span class="method get">GET</span>/matrix/v2?exercise=Back+Squat+(high-bar)</div>
  </div>
  <div class="card">
    <h2>Datasets</h2>
    <h3>Version Registry</h3>
    <p>Available matrix versions with row counts.</p>
    <div class="route"><span class="method get">GET</span>/datasets</div>
  </div>
  <div class="card">
    <h2>Volume</h2>
    <h3>Set Logging</h3>
    <p>Ingest training sets. Auto-computes tonnage.</p>
    <div class="route"><span class="method post">POST</span>/volume/ingest</div>
    <div class="route"><span class="method get">GET</span>/volume/logs</div>
  </div>
  <div class="card">
    <h2>Reports</h2>
    <h3>Weekly Stimulus</h3>
    <p>Aggregate volume with per-muscle stimulus from real activation values.</p>
    <div class="route"><span class="method get">GET</span>/reports/weekly?week=2026-W09</div>
  </div>
  <div class="card">
    <h2>Optimizer</h2>
    <h3>Greedy Set-Cover</h3>
    <p>Select n exercises maximising muscle coverage from the v2 matrix.</p>
    <div class="route"><span class="method get">GET</span>/optimizer?goal=coverage&amp;n=8</div>
  </div>
  <div class="card">
    <h2>Docs</h2>
    <h3>API Reference</h3>
    <a class="btn" href="/docs">Swagger UI</a>
    <a class="btn" href="/redoc" style="background:#374151;margin-left:6px">ReDoc</a>
  </div>
</div>
</body>
</html>"""

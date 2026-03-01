from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware

from app.database import engine
from app.models import Base
from app.routers import datasets, matrix, volume, reports, optimizer

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Lifting Intel API",
    description=(
        "Versioned lifting datasets (v2–v5, composite), volume tracking, "
        "weekly reports, and exercise optimization."
    ),
    version="1.0.0",
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
<title>Lifting Intel</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: system-ui, -apple-system, sans-serif; background: #0f0f0f; color: #e8e8e8; min-height: 100vh; padding: 40px 20px; }
  h1 { font-size: 2rem; font-weight: 700; letter-spacing: -0.5px; margin-bottom: 4px; }
  .sub { color: #888; font-size: 0.9rem; margin-bottom: 40px; }
  .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 16px; max-width: 900px; }
  .card { background: #1a1a1a; border: 1px solid #2a2a2a; border-radius: 12px; padding: 24px; }
  .card h2 { font-size: 0.75rem; text-transform: uppercase; letter-spacing: 1px; color: #666; margin-bottom: 12px; }
  .card h3 { font-size: 1.1rem; font-weight: 600; margin-bottom: 8px; }
  .card p { font-size: 0.85rem; color: #999; line-height: 1.5; margin-bottom: 16px; }
  .tag { display: inline-block; background: #252525; border: 1px solid #333; border-radius: 6px; padding: 3px 10px; font-size: 0.75rem; color: #ccc; margin: 2px; font-family: monospace; }
  a.btn { display: inline-block; margin-top: 16px; padding: 8px 18px; background: #2563eb; color: #fff; border-radius: 8px; text-decoration: none; font-size: 0.85rem; font-weight: 500; }
  a.btn:hover { background: #1d4ed8; }
  .method { font-size: 0.7rem; font-weight: 700; padding: 2px 7px; border-radius: 4px; margin-right: 6px; }
  .get  { background: #14532d; color: #4ade80; }
  .post { background: #1e3a5f; color: #60a5fa; }
  .route { display: flex; align-items: center; font-family: monospace; font-size: 0.82rem; color: #ccc; margin-bottom: 8px; }
</style>
</head>
<body>
<h1>⚡ Lifting Intel</h1>
<p class="sub">Versioned datasets · Volume tracking · Reports · Optimizer</p>
<div class="grid">
  <div class="card">
    <h2>Datasets</h2>
    <h3>Version Registry</h3>
    <p>Query available dataset versions and their exercise libraries.</p>
    <div class="route"><span class="method get">GET</span>/datasets</div>
    <div>
      <span class="tag">v2</span><span class="tag">v3</span><span class="tag">v4</span><span class="tag">v5</span><span class="tag">composite</span>
    </div>
  </div>
  <div class="card">
    <h2>Matrix</h2>
    <h3>Intensity Tables</h3>
    <p>Per-version intensity matrices: reps → %1RM, RPE, and programming defaults.</p>
    <div class="route"><span class="method get">GET</span>/matrix/{version}</div>
    <div class="route"><span class="method get">GET</span>/matrix/{version}?exercise=squat</div>
  </div>
  <div class="card">
    <h2>Volume</h2>
    <h3>Set Logging</h3>
    <p>Ingest logged sets. Calculates tonnage and estimated 1RM automatically.</p>
    <div class="route"><span class="method post">POST</span>/volume/ingest</div>
    <div class="route"><span class="method get">GET</span>/volume/logs</div>
  </div>
  <div class="card">
    <h2>Reports</h2>
    <h3>Weekly Analysis</h3>
    <p>Aggregate weekly volume by preset: strength, hypertrophy, or injury.</p>
    <div class="route"><span class="method get">GET</span>/reports/weekly?week=YYYY-WW&preset=strength</div>
  </div>
  <div class="card">
    <h2>Optimizer</h2>
    <h3>Exercise Selection</h3>
    <p>Select n exercise slots for a goal with optional constraints.</p>
    <div class="route"><span class="method get">GET</span>/optimizer?goal=strength&n=8</div>
    <div>
      <span class="tag">strength</span><span class="tag">hypertrophy</span><span class="tag">injury</span><span class="tag">conjugate</span><span class="tag">balanced</span>
    </div>
  </div>
  <div class="card">
    <h2>Docs</h2>
    <h3>Interactive API</h3>
    <p>Full OpenAPI documentation with live request testing.</p>
    <a class="btn" href="/docs">Open Swagger UI →</a>
    <br>
    <a class="btn" href="/redoc" style="background:#374151;margin-top:8px">ReDoc →</a>
  </div>
</div>
</body>
</html>"""

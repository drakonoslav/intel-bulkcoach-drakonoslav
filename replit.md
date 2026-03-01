# Lifting Intel

FastAPI-based lifting intelligence platform with versioned datasets, volume tracking, weekly reports, and exercise optimization.

## Tech Stack
- **Runtime**: Python 3.11
- **Framework**: FastAPI + Uvicorn (port 5000)
- **Database**: PostgreSQL (Replit-managed, via DATABASE_URL)
- **ORM**: SQLAlchemy
- **Validation**: Pydantic v2

## Project Structure
```
app/
  main.py          — FastAPI app + admin HTML UI at /
  database.py      — SQLAlchemy engine + session
  models.py        — VolumeLog ORM model
  schemas.py       — Pydantic request/response schemas
  data/
    v2.py          — Linear Progression Baseline dataset
    v3.py          — Wave Loading Intermediate dataset
    v4.py          — Block Periodization Advanced dataset
    v5.py          — Conjugate / Concurrent Method dataset
    composite.py   — Weighted blend across v2–v5
  routers/
    datasets.py    — GET /datasets
    matrix.py      — GET /matrix/{version}
    volume.py      — POST /volume/ingest, GET /volume/logs
    reports.py     — GET /reports/weekly
    optimizer.py   — GET /optimizer
run.py             — Entry point (uvicorn)
```

## API Routes
| Method | Path | Description |
|--------|------|-------------|
| GET | `/datasets` | List all dataset versions |
| GET | `/matrix/{version}` | Intensity matrix for a version (`?exercise=squat` optional filter) |
| POST | `/volume/ingest` | Log a set (exercise, weight_kg, reps, sets, date) |
| GET | `/volume/logs` | Query logged volume entries |
| GET | `/reports/weekly` | Weekly report (`?week=YYYY-WW&preset=strength\|hypertrophy\|injury`) |
| GET | `/optimizer` | Exercise optimizer (`?goal=strength&n=8&constraints=...`) |
| GET | `/docs` | Swagger UI |
| GET | `/` | Admin dashboard UI |

## Dataset Versions
- **v2** — Linear Progression Baseline (beginner)
- **v3** — Wave Loading / 3-week undulating intensity (intermediate)
- **v4** — Block Periodization with Prilepin table (advanced)
- **v5** — Conjugate method with ME/DE day split (elite)
- **composite** — Weighted average blend of v2–v5

## Workflow
- **Command**: `python run.py`
- **Port**: 5000 (webview)

## Database Tables
- `volume_logs` — tracks logged sets with auto-computed tonnage, ISO week, and estimated 1RM

# Lifting Intel — Biomechanical Computation Engine

FastAPI-based biomechanical engine. Real activation matrix imported from CSV — no invented data.

## Tech Stack
- **Runtime**: Python 3.11
- **Framework**: FastAPI + Uvicorn (port 5000)
- **Database**: PostgreSQL (Replit-managed, via DATABASE_URL)
- **ORM**: SQLAlchemy

## Project Structure
```
app/
  main.py          — FastAPI app, table creation, CSV seed, admin UI
  database.py      — SQLAlchemy engine + session
  models.py        — Exercise, Muscle, ActivationMatrixV2, VolumeLog
  schemas.py       — Pydantic schemas
  seed.py          — CSV importer (Exercise_Muscle_Matrix_v2.csv)
  routers/
    datasets.py    — GET /datasets
    matrix.py      — GET /matrix/v2
    volume.py      — POST /volume/ingest, GET /volume/logs
    reports.py     — GET /reports/weekly
    optimizer.py   — GET /optimizer
run.py             — Entry point (uvicorn)
attached_assets/
  Exercise_Muscle_Matrix_v2_*.csv  — Source of truth
```

## Database Tables
| Table | Rows | Description |
|-------|------|-------------|
| `exercises` | 92 | Exercise names from CSV first column |
| `muscles` | 26 | Muscle names from CSV header |
| `activation_matrix_v2` | 2392 | 92×26 integer activations (0–5), PK (exercise_id, muscle_id) |
| `volume_logs` | var | Logged training sets |

## API Routes
| Method | Path | Description |
|--------|------|-------------|
| GET | `/datasets` | List dataset versions with row counts |
| GET | `/matrix/v2` | Full 92×26 activation matrix (integer 0–5) |
| POST | `/volume/ingest` | Log a training set |
| GET | `/volume/logs` | Query volume history |
| GET | `/reports/weekly` | Weekly report with per-muscle stimulus |
| GET | `/optimizer` | Greedy set-cover exercise selection |
| GET | `/docs` | Swagger UI |

## Data Integrity
- Source: `Exercise_Muscle_Matrix_v2.csv` (92 exercises × 26 muscles)
- Activation values: integers 0–5, stored as-is (no normalization)
- Seed runs once at startup; skips if exercises already exist

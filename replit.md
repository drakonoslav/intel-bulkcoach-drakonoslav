# Lifting Intel — Biomechanical Computation Engine

FastAPI-based biomechanical engine. Real activation matrices imported from CSV/XLSX — no invented data.

## Tech Stack
- **Runtime**: Python 3.11
- **Framework**: FastAPI + Uvicorn (port 5000)
- **Database**: PostgreSQL (Replit-managed, via DATABASE_URL)
- **ORM**: SQLAlchemy
- **Dependencies**: openpyxl (xlsx parsing)

## Project Structure
```
app/
  main.py          — FastAPI app, table creation, CSV seed, admin UI
  database.py      — SQLAlchemy engine + session
  models.py        — Exercise, Muscle, ActivationMatrixV2, RoleWeightedMatrixV2, PhaseMatrixV3, VolumeLog
  schemas.py       — Pydantic schemas
  seed.py          — CSV/XLSX importer (activation v2 + role-weighted v2 + phase v3)
  routers/
    datasets.py    — GET /datasets
    matrix.py      — GET /matrix/v2, /matrix/role-weighted-v2, /matrix/v3
    volume.py      — POST /volume/ingest, GET /volume/logs
    reports.py     — GET /reports/weekly
    optimizer.py   — GET /optimizer
run.py             — Entry point (uvicorn)
attached_assets/
  Exercise_Muscle_Matrix_v2_*.csv       — Activation source (int 0–5)
  Role_Weighted_Matrix_v2_*.csv         — Role-weighted source (float 0–1)
  V3_Phase_Model_Outputs_*.xlsx         — Phase matrices (float 0–5, 3 sheets)
```

## Database Tables
| Table | Rows | Description |
|-------|------|-------------|
| `exercises` | 92 | Exercise names from CSV first column |
| `muscles` | 26 | Muscle names from CSV header |
| `activation_matrix_v2` | 2392 | 92×26 integer activations (0–5), PK (exercise_id, muscle_id) |
| `role_weighted_matrix_v2` | 2392 | 92×26 float role weights (0.0–1.0), PK (exercise_id, muscle_id) |
| `phase_matrix_v3` | 7176 | 92×26×3 float phase values (0–5), PK (exercise_id, muscle_id, phase) |
| `volume_logs` | var | Logged training sets |

## API Routes
| Method | Path | Description |
|--------|------|-------------|
| GET | `/datasets` | List dataset versions with row counts |
| GET | `/matrix/v2` | Full 92×26 activation matrix (integer 0–5) |
| GET | `/matrix/role-weighted-v2` | Full 92×26 role-weighted matrix (float 0–1) |
| GET | `/matrix/v3?phase=initiation\|midrange\|lockout` | Phase-specific 92×26 matrix (float 0–5) |
| POST | `/volume/ingest` | Log a training set |
| GET | `/volume/logs` | Query volume history |
| GET | `/reports/weekly` | Weekly report with per-muscle stimulus |
| GET | `/optimizer` | Greedy set-cover exercise selection |
| GET | `/docs` | Swagger UI |

## Data Integrity
- Source files: activation CSV (int 0–5), role-weighted CSV (float 0–1), phase XLSX (float 0–5)
- Values stored as-is — no normalization or rounding
- Seed runs once at startup; skips if data already exists (idempotent)
- Composite PKs on matrix tables — no extra serial id columns
- phase_matrix_v3 uses 3-part PK (exercise_id, muscle_id, phase)

# Lifting Intel — Biomechanical Computation Engine

FastAPI-based biomechanical modeling engine with versioned activation matrices, phase decomposition, bottleneck analysis, stabilization scoring, and composite muscle profiling.

## Tech Stack
- **Runtime**: Python 3.11
- **Framework**: FastAPI + Uvicorn (port 5000)
- **Database**: PostgreSQL (Replit-managed, via DATABASE_URL)
- **ORM**: SQLAlchemy
- **Validation**: Pydantic v2

## Project Structure
```
app/
  main.py          — FastAPI app, table creation, seed trigger, admin UI
  database.py      — SQLAlchemy engine + session
  models.py        — All ORM models (exercises, muscles, matrix tables, volume_logs)
  schemas.py       — Pydantic request/response schemas
  seed.py          — Seed data: 93 exercises, 26 muscles, all matrix tables
  routers/
    datasets.py    — GET /datasets (version registry)
    matrix.py      — GET /matrix/v2, /matrix/v3, /matrix/v4, /matrix/v5, /matrix/composite
    volume.py      — POST /volume/ingest, GET /volume/logs
    reports.py     — GET /reports/weekly (stimulus analysis)
    optimizer.py   — GET /optimizer (matrix-driven exercise selection)
run.py             — Entry point (uvicorn)
```

## Database Tables
| Table | Description |
|-------|-------------|
| `exercises` | 93 exercises with category, movement pattern, equipment, bilateral flag |
| `muscles` | 26 muscles with group and region classification |
| `activation_matrix_v2` | Base activation matrix (exercise × muscle, 0–1 scale) |
| `role_weighted_matrix_v2` | Role-weighted activation (prime_mover / synergist / stabilizer) |
| `phase_matrix_v3` | Phase-expanded: initiation, mid, lockout per exercise×muscle |
| `bottleneck_matrix_v4` | Bottleneck coefficients, is_limiting flag |
| `stabilization_matrix_v5` | Stabilization score + dynamic score per pair |
| `composite_index` | Composite score = weighted blend of all components |
| `volume_logs` | Logged sets with auto-computed tonnage and estimated 1RM |

## API Routes
| Method | Path | Description |
|--------|------|-------------|
| GET | `/datasets` | List matrix versions with row counts and dimensions |
| GET | `/matrix/v2` | Base activation matrix (`?exercise=`, `?muscle=`, `?include_roles=true`) |
| GET | `/matrix/v3` | Phase matrix (`?exercise=`, `?muscle=`, `?phase=initiation\|mid\|lockout`) |
| GET | `/matrix/v4` | Bottleneck matrix (`?exercise=`, `?muscle=`, `?limiting_only=true`) |
| GET | `/matrix/v5` | Stabilization matrix (`?exercise=`, `?muscle=`) |
| GET | `/matrix/composite` | Composite index (`?exercise=`, `?muscle=`, `?min_score=0.3`) |
| POST | `/volume/ingest` | Log a training set |
| GET | `/volume/logs` | Query volume history |
| GET | `/reports/weekly` | Weekly report with per-muscle stimulus from activation matrices |
| GET | `/optimizer` | Matrix-driven optimization (`?goal=coverage\|bottleneck\|stabilization\|composite&n=8&target_muscles=...&constraints=...`) |

## Dataset Versions
- **v2** — Base Activation Matrix (93×26): raw muscle activation levels per exercise
- **v3** — Phase-Expanded Matrices: initiation/mid/lockout decomposition
- **v4** — Bottleneck Coefficient Matrix: identifies limiting muscles per exercise
- **v5** — Stabilization & Dynamic Matrices: stabilization vs dynamic contribution
- **composite** — Composite Muscle Profile Index: weighted integration of all components

## Seed Data
- Activation values derived from movement-pattern heuristics with per-exercise overrides
- Role classification: prime_mover (≥0.70), synergist (≥0.30), stabilizer (<0.30)
- Composite formula: 0.35×activation + 0.25×phase_avg + 0.20×bottleneck + 0.10×stab + 0.10×dynamic

## Workflow
- **Command**: `python run.py`
- **Port**: 5000 (webview)

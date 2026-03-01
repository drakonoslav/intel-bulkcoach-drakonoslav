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
  models.py        — Exercise, Muscle, ActivationMatrixV2, RoleWeightedMatrixV2, PhaseMatrixV3, BottleneckMatrixV4, StabilizationMatrixV5, VolumeLog
  schemas.py       — Pydantic schemas
  seed.py          — CSV/XLSX importer (v2 activation + role-weighted + v3 phase + v4 bottleneck + v5 dynamic/stability)
  routers/
    datasets.py    — GET /datasets
    matrix.py      — GET /matrix/v2, /role-weighted-v2, /v3, /v4/bottleneck, /v5
    volume.py      — POST /volume/ingest, GET /volume/logs
    reports.py     — GET /reports/weekly
    optimizer.py   — GET /optimizer
run.py             — Entry point (uvicorn)
attached_assets/
  Exercise_Muscle_Matrix_v2_*.csv       — Activation source (int 0–5)
  Role_Weighted_Matrix_v2_*.csv         — Role-weighted source (float 0–1)
  V3_Phase_Model_Outputs_*.xlsx         — Phase matrices (float 0–5, 3 sheets)
  V4_Bottleneck_Coefficient_Matrix_*.csv — Bottleneck coefficients (float 0–1)
  V5_Dynamic_Matrix_*.csv               — Dynamic component (float 0–1)
  V5_Stability_Matrix_*.csv             — Stability component (float 0–1)
```

## Database Tables
| Table | Rows | Description |
|-------|------|-------------|
| `exercises` | 92 | Exercise names from CSV first column |
| `muscles` | 26 | Muscle names from CSV header |
| `activation_matrix_v2` | 2392 | 92×26 integer activations (0–5), PK (exercise_id, muscle_id) |
| `role_weighted_matrix_v2` | 2392 | 92×26 float role weights (0.0–1.0), PK (exercise_id, muscle_id) |
| `phase_matrix_v3` | 7176 | 92×26×3 float phase values (0–5), PK (exercise_id, muscle_id, phase) |
| `bottleneck_matrix_v4` | 2392 | 92×26 float bottleneck coefficients (0–1), PK (exercise_id, muscle_id) |
| `stabilization_matrix_v5` | 4784 | 92×26×2 float values (0–1), PK (exercise_id, muscle_id, component) |
| `composite_muscle_index` | 26 | Per-muscle composite score (0–100) + JSONB payload, PK (muscle_id) |
| `presets` | 3 | Named weight presets (hypertrophy/strength/injury), JSONB weights, PK (name) |
| `exercise_tags` | 107 | Per-exercise slot tags (hinge/squat/push/pull/carry/oly), PK (exercise_id, slot), multi-tag supported |
| `lift_sets` | var | Logged lift sets with exercise_id FK, weight, reps, tonnage, notes, source |
| `volume_logs` | var | Legacy logged training sets |

## API Routes
| Method | Path | Description |
|--------|------|-------------|
| GET | `/datasets` | List dataset versions with row counts |
| GET | `/matrix/v2` | Full 92×26 activation matrix (integer 0–5) |
| GET | `/matrix/role-weighted-v2` | Full 92×26 role-weighted matrix (float 0–1) |
| GET | `/matrix/v3?phase=initiation\|midrange\|lockout` | Phase-specific 92×26 matrix (float 0–5) |
| GET | `/matrix/v4/bottleneck` | Full 92×26 bottleneck coefficient matrix (float 0–1) |
| GET | `/matrix/v5?component=dynamic\|stability` | Component-specific 92×26 matrix (float 0–1) |
| GET | `/composite/muscles` | 26-row composite muscle profile index with JSONB payload |
| GET | `/composite/muscles?preset=hypertrophy\|strength\|injury` | Same + preset_score and preset_rank |
| GET | `/presets` | List preset names + weight vectors |
| GET | `/optimizer/weekly-template?preset=...` | Weekly template optimizer with slots, redundancy, fatigue constraints |
| POST | `/lifts/sets` | Log a lift set (exercise_id resolved from name, tonnage computed) |
| GET | `/lifts/sets?from=&to=` | Query lift sets by date range |
| GET | `/reports/weekly-muscles?week=&lens=v2\|role\|v3\|v4\|v5` | Weekly muscle stimulus with configurable matrix lens |
| GET | `/reports/weekly-muscle-dose?week=` | Per-muscle total vs direct dose decomposition + top contributors |
| GET | `/reports/weekly-muscle-dose/{muscle}?week=` | Single muscle drilldown with optional set-level detail |
| POST | `/volume/ingest` | Legacy: log a training set |
| GET | `/volume/logs` | Legacy: query volume history |
| GET | `/reports/weekly` | Legacy: weekly report with muscle stimulus |
| GET | `/optimizer` | Greedy set-cover exercise selection |
| GET | `/docs` | Swagger UI |

## Data Integrity
- Source files: activation CSV (int 0–5), role-weighted CSV (float 0–1), phase XLSX (float 0–5), bottleneck CSV (float 0–1), dynamic/stability CSVs (float 0–1)
- Values stored as-is — no normalization or rounding
- Seed runs once at startup; skips if data already exists (idempotent)
- Composite PKs on matrix tables — no extra serial id columns
- phase_matrix_v3 uses 3-part PK (exercise_id, muscle_id, phase)
- stabilization_matrix_v5 uses 3-part PK (exercise_id, muscle_id, component)

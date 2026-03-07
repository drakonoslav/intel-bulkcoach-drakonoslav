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
| `muscles` | 27 | Muscle names from CSV header + Hands/Grip |
| `activation_matrix_v2` | 2392 | 92×26 integer activations (0–5), PK (exercise_id, muscle_id) |
| `role_weighted_matrix_v2` | 2392 | 92×26 float role weights (0.0–1.0), PK (exercise_id, muscle_id) |
| `phase_matrix_v3` | 7176 | 92×26×3 float phase values (0–5), PK (exercise_id, muscle_id, phase) |
| `bottleneck_matrix_v4` | 2392 | 92×26 float bottleneck coefficients (0–1), PK (exercise_id, muscle_id) |
| `stabilization_matrix_v5` | 4784 | 92×26×2 float values (0–1), PK (exercise_id, muscle_id, component) |
| `composite_muscle_index` | 26 | Per-muscle composite score (0–100) + JSONB payload, PK (muscle_id) |
| `presets` | 3 | Named weight presets (hypertrophy/strength/injury), JSONB weights, PK (name) |
| `exercise_tags` | 107 | Per-exercise slot tags (hinge/squat/push/pull/carry/oly), PK (exercise_id, slot), multi-tag supported |
| `equipment` | 17 | Equipment tags (rack, barbell, plates, bench, etc.), PK (tag) |
| `exercise_equipment` | 168 | Exercise-to-equipment required mappings, PK (exercise_id, equipment_tag) |
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
| GET | `/optimizer/weekly-template?preset=...&available=` | Weekly template optimizer with slots, redundancy, fatigue constraints, optional equipment filter |
| POST | `/lifts/sets` | Log a single lift set (exercise_id resolved from name, tonnage computed) |
| POST | `/lifts/sets/batch` | Batch-log multiple lift sets in one transaction (?bestEffort=true for partial) |
| GET | `/lifts/sets?from=&to=` | Query lift sets by date range |
| GET | `/reports/weekly-muscles?week=&lens=v2\|role\|v3\|v4\|v5` | Weekly muscle stimulus with configurable matrix lens |
| GET | `/coach/weekly-balance?week=&lookbackWeeks=` | Per-muscle underfed/overtaxed scores with classification |
| GET | `/coach/recommend-session?date=&mode=&slots=&bnPercentile=&stabPercentile=&ctPercentile=&available=` | Session recommender with BN/STAB/CT triple-filter, bias boosts, fallback, optional equipment filter |
| POST | `/coach/session/start` | Snapshot a recommended plan into session_plans table |
| POST | `/coach/session/complete` | Link executed set_ids to plan, returns compliance analysis |
| GET | `/reports/weekly-muscle-dose?week=` | Per-muscle total vs direct dose decomposition + top contributors |
| GET | `/reports/weekly-muscle-dose/{muscle}?week=` | Single muscle drilldown with optional set-level detail |
| GET | `/muscle/day?date=` | Per-muscle load for a single date — all 27 regions, 7d rolling, recovery, balances |
| GET | `/strength/trend?from=&to=` | Dense per-day strength index, rolling avg, velocity, phase detection |
| GET | `/strength/day?date=` | Single-day strength breakdown with per-exercise contributors |
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

## Pec Zone Proxy Layer (v2.5 — overlay)
- **Non-breaking sidecar analytics**: partitions existing Pectorals dose into Upper/Mid/Lower Pec zones
- Does NOT modify muscles table, seed CSVs, balance buckets, recovery schema, optimizer vectors, or existing response shapes
- Files:
  - `app/pec_zone_overlay.py` — per-exercise biomechanical feature table (9 coefficients) + weighted formula + confidence scoring
  - `app/exercise_geometry.py` — geometry classifier + grip inference (kept as pipeline stage)
  - `app/pec_zones.py` — v2.5 pipeline allocator
  - `app/routers/pec_zones.py` — endpoints
  - `app/pec_zone_profiles.py` — legacy (archetype defaults; superseded by overlay but kept for reference)
- **v2.5 pipeline** (applied in order): overlay feature formula → geometry blend → V3 phase adjustment → proxy adjustment (fd/tri + stab) → grip-width adjustment → floor + renormalize
- **Overlay coefficients**: upper_bias, mid_bias, lower_bias, stretch_bias, front_delt_coupling, triceps_coupling, adduction_bias, decline_vector_bias, convergence_bias — all 0.0–1.0
- **Data provenance**: overlay coefficients are authored biomechanics priors, NOT newly measured differentiation from canonical matrices. This is a structural/explainability upgrade.
- Conservation rule: zone shares sum to 1.0, zone doses sum to canonical Pectorals dose
- Confidence scoring: per-exercise (0.75–0.92), dose-weighted aggregate for day/week; null when no chest data
- Driver metadata: dominant_zone, top_modifier, archetype — for future Expo visualization
- Endpoints:
  - `GET /reports/pec-zones/day?date=` — daily pec zone breakdown + confidence
  - `GET /reports/pec-zones/week?week=` — weekly pec zone breakdown + confidence
  - `GET /reports/pec-zones/explain?exercise=` — per-exercise overlay features + adjustments + confidence + drivers
  - `GET /reports/pec-zones/analysis?exercise=` — full v2.5 pipeline debug with overlay stage, all pipeline outputs, raw inputs

## Hierarchy Patch (Deltoids/Traps)
- Patched source files (suffix `_2_1772898930398`) have Deltoids and Traps columns zeroed in all 5 CSV matrices + all 3 V3 xlsx sheets
- **Shared utility `app/hierarchy.py`**: `build_derived_groups(db)` returns {group_id: [child_ids]}, `apply_derived_rollup(stim_dict, groups)` sums children into group
- Runtime derivation applied in: `muscle_day.py`, `weekly_muscles.py`, `muscle_dose.py`, `coach.py` (_compute_weekly_balance + recommend-session + session compliance), `weekly_optimizer.py`, `reports.py`
- Balance member lists use leaf muscles only (no group names) to prevent double-counting
- Admin re-seed endpoint: `POST /admin/reseed-matrices` (wipes + reloads matrix tables, does NOT touch lift_sets/exercises/muscles)
- Derived groups marked in `/muscle/day` response with `derived_from: children_sum` and `children` array

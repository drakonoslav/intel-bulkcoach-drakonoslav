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
  seed.py          — CSV/XLSX importer (v2 activation + role-weighted + v3 phase + v4 bottleneck + v5 dynamic/stability + biomechanics + batch1)
  biomechanics_seed.py — Biomechanics metadata for original 92 exercises (v2 spec-driven)
  batch1_seed.py   — Batch 1 expansion: 10 dumbbell/cable isolation exercises with full authored matrices
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
| `exercises` | 119 | Exercise names (92 original + 10 Batch 1 + 10 Batch 2A + 7 Batch 2B) |
| `muscles` | 27 | Muscle names from CSV header + Hands/Grip |
| `activation_matrix_v2` | 3121 | 119×26+extras integer activations (0–5), PK (exercise_id, muscle_id) |
| `role_weighted_matrix_v2` | 3121 | Float role weights (0.0–1.0), PK (exercise_id, muscle_id) |
| `phase_matrix_v3` | 7176 | 92×26×3 float phase values (0–5), PK (exercise_id, muscle_id, phase) |
| `bottleneck_matrix_v4` | 3121 | Float bottleneck coefficients (0–1), PK (exercise_id, muscle_id) |
| `stabilization_matrix_v5` | 6242 | Float values (0–1), PK (exercise_id, muscle_id, component) |
| `exercise_biomechanics` | 119 | Per-exercise biomechanics metadata, PK (exercise_id) |
| `composite_muscle_index` | 26 | Per-muscle composite score (0–100) + JSONB payload, PK (muscle_id) |
| `presets` | 3 | Named weight presets (hypertrophy/strength/injury), JSONB weights, PK (name) |
| `exercise_tags` | 127 | Per-exercise slot tags (hinge/squat/push/pull/carry/oly), PK (exercise_id, slot) |
| `equipment` | 22 | Equipment tags (rack, barbell, plates, bench, band, etc.), PK (tag) |
| `exercise_equipment` | 192 | Exercise-to-equipment required mappings, PK (exercise_id, equipment_tag) |
| `lift_sets` | var | Logged lift sets with exercise_id FK, weight, reps, tonnage, notes, source |
| `volume_logs` | var | Legacy logged training sets |

## Biomechanics Contract v2 (FROZEN)

Authoritative contract defined in `app/biomechanics_contract.py`. Served at `GET /game/biomechanics-contract`.

### Field Classification
**STRUCTURAL** (safe for hard filtering by Expo):
- `implement_type` — REQUIRED — barbell|dumbbell|bodyweight|cable|machine|kettlebell|band|sled|sandbag|tire|yoke
- `body_position` — REQUIRED — standing|seated|supine|prone|incline|decline|hanging|inverted|kneeling|side_lying
- `laterality` — REQUIRED — bilateral|unilateral|alternating
- `resistance_origin` — REQUIRED — gravity|floor|low|mid|high|overhead|elastic
- `resistance_direction` — REQUIRED — vertical|horizontal|diagonal_low_high|diagonal_high_low|rotational
- `grip_style` — NULLABLE — null when grip not defining; overhand|underhand|neutral|mixed|false|rope|handle
- `bench_angle` — NULLABLE — null when no bench; float degrees (0=flat, 30/45=incline, -15/-30=decline, 90=seated OHP)

**CATEGORICAL** (safe for filtering/display):
- `movement_family` — REQUIRED — press|row|fly|curl|extension|raise|squat|hinge|lunge|thrust|carry|pull|dip|olympic|complex|push
- `pattern_class` — REQUIRED — compound|isolation|carry|ballistic|olympic

**INTERPRETIVE** (display/advisory only, not for hard filtering):
- `stability_demand` — REQUIRED float 0-1 — always applicable
- `stretch_bias` — NULLABLE float 0-1 — only when resistance meaningfully peaks at stretched position
- `shortened_bias` — NULLABLE float 0-1 — only when resistance meaningfully peaks at contraction
- `convergence_arc` — NULLABLE 0|1 — only for movements with real inward converging arm path
- `humeral_plane` — NULLABLE — only for upper-body shoulder-driven patterns; sagittal|frontal|scapular|transverse
- `elbow_path` — NULLABLE — only where elbow tracking materially defines the exercise; fixed|free|tracking

**VERSIONING**:
- `biomechanics_version` — INTEGER, current = 2
- `metadata_tier` — TEXT: core|extended|full
  - core = structural + stability_demand + movement_family + pattern_class only
  - extended = core + applicable interpretive fields (existing 92 exercises)
  - full = all applicable fields authored with high confidence (Batch 1 isolation exercises)
- `updated_at` — ISO 8601 timestamp of last authoring update

**field_classification** — included in each biomechanics response with 3 categories: structural, categorical, interpretive

### Validation
- `app/biomechanics_contract.py` — frozen enums, validation functions, contract documentation
- `validate_biomechanics()` — validates a single exercise's biomechanics dict against the contract
- `validate_exercise_batch()` — validates a full batch (biomechanics + all 5 matrices + tags + equipment)
- Both validators run at seed time — invalid data blocks startup

### Proof Queries
- `GET /game/catalog-proof` — regression check: row counts, coverage gaps, tier/version distribution
- Returns `proof_status: PASS` when all exercises have all 5 matrices + biomechanics + movement_family + pattern_class

### Manual Entry Linkage Rules (documented future behavior — not yet implemented)
- Exact Intel catalog selection → store `intel_exercise_id` on lift_set, full matrix scoring applies
- Free-text custom movement → `intel_exercise_id = null`, bridge-dose fallback only
- No inferred variants: do NOT map generic input to specific exercise variants
- Currently: `LiftSet.exercise_id` is required; custom/unlinked entries not yet supported

### Future Considerations
- `parent_exercise_id` / `variant_group` — UI grouping only, not for scoring
- `intel_exercise_id` nullable FK on lift_sets for bridging custom vs. catalog entries

## Batch 1 Expansion (10 exercises — `app/batch1_seed.py`)
- Dumbbell Lateral Raise, Dumbbell Rear Delt Fly, Dumbbell Hammer Curl, Incline Dumbbell Curl
- Cable Fly (low-to-high), Cable Fly (high-to-low), Cable Tricep Pushdown, Cable Face Pull
- Cable Lateral Raise, Cable Rear Delt Fly

## Batch 2A Expansion (10 exercises — `app/batch2a_seed.py`)
- Dumbbell Front Raise, Dumbbell Overhead Tricep Extension, Dumbbell Fly, Incline Dumbbell Fly, Dumbbell Shrug
- Cable Curl, Cable Overhead Tricep Extension
- Band Pull-Apart, Band Face Pull, Band Lateral Raise

## Batch 2B Expansion (7 exercises — `app/batch2b_seed.py`)
- Band Curl, Band Pushdown, Band Pallof Press
- Kettlebell Goblet Squat, Kettlebell Press, Kettlebell Row, Kettlebell Swing

## Batch Seeding Pipeline
- Generic `_seed_batch_exercises(db, batch_data, batch_name)` in `app/seed.py`
- All batches go through `_seed_all_batches(db)` which runs validation before DB writes
- Every batch must pass `validate_exercise_batch()` — invalid data blocks startup
- Each exercise gets: exercise row, all 5 matrix tables, tags, equipment, biomechanics
- All matrices authored with real values, not inferred overlays
- metadata_tier = "full", biomechanics_version = 2

## Batch Sequencing Plan
- **Batch 2C** (next): Kettlebell Clean, Kettlebell Snatch, Turkish Get-Up
- Rule: no batch lands without passing validation + regression checks

## API Routes
| Method | Path | Description |
|--------|------|-------------|
| GET | `/datasets` | List dataset versions with row counts |
| GET | `/matrix/v2` | Full activation matrix (integer 0–5) |
| GET | `/matrix/role-weighted-v2` | Full role-weighted matrix (float 0–1) |
| GET | `/matrix/v3?phase=initiation\|midrange\|lockout` | Phase-specific matrix (float 0–5) |
| GET | `/matrix/v4/bottleneck` | Full bottleneck coefficient matrix (float 0–1) |
| GET | `/matrix/v5?component=dynamic\|stability` | Component-specific matrix (float 0–1) |
| GET | `/composite/muscles` | 26-row composite muscle profile index with JSONB payload |
| GET | `/composite/muscles?preset=hypertrophy\|strength\|injury` | Same + preset_score and preset_rank |
| GET | `/presets` | List preset names + weight vectors |
| GET | `/optimizer/weekly-template?preset=...&available=` | Weekly template optimizer |
| POST | `/lifts/sets` | Log a single lift set |
| POST | `/lifts/sets/batch` | Batch-log multiple lift sets |
| GET | `/lifts/sets?from=&to=` | Query lift sets by date range |
| GET | `/reports/weekly-muscles?week=&lens=v2\|role\|v3\|v4\|v5` | Weekly muscle stimulus |
| GET | `/coach/weekly-balance?week=&lookbackWeeks=` | Per-muscle balance scores |
| GET | `/coach/recommend-session?date=&mode=&slots=&available=` | Session recommender |
| POST | `/coach/session/start` | Snapshot recommended plan |
| POST | `/coach/session/complete` | Link executed sets to plan |
| GET | `/reports/weekly-muscle-dose?week=` | Per-muscle dose decomposition |
| GET | `/reports/weekly-muscle-dose/{muscle}?week=` | Single muscle drilldown |
| GET | `/muscle/day?date=` | Per-muscle load for a single date |
| GET | `/strength/trend?from=&to=` | Strength index trend |
| GET | `/strength/day?date=` | Single-day strength breakdown |
| POST | `/volume/ingest` | Legacy volume log |
| GET | `/volume/logs` | Legacy volume query |
| GET | `/reports/weekly` | Legacy weekly report |
| GET | `/optimizer` | Greedy set-cover exercise selection |
| GET | `/game/muscle-state?date=` | 27-muscle physiological snapshot |
| GET | `/game/muscle-priority?mode=&date=&top_n=` | Ranked muscle training queue |
| POST | `/game/log-set` | Log workout action (FROZEN — do not modify) |
| POST | `/game/session-close` | Finalize session (FROZEN — do not modify) |
| GET | `/game/exercise-catalog` | Full 102-exercise list with biomechanics v2 |
| GET | `/game/exercise-recommendations?muscle_id=&mode=&date=&top_n=&available=` | Scored exercise recommendations |
| GET | `/game/muscle-schema` | Canonical 27-muscle schema |
| GET | `/game/biomechanics-contract` | Frozen v2 contract: enums, nullability, tiers, field classification |
| GET | `/game/catalog-proof` | Regression/proof queries for catalog integrity |
| GET | `/health` | Service health check |
| GET | `/docs` | Swagger UI |

## Data Integrity
- Source files: activation CSV (int 0–5), role-weighted CSV (float 0–1), phase XLSX (float 0–5), bottleneck CSV (float 0–1), dynamic/stability CSVs (float 0–1)
- Values stored as-is — no normalization or rounding
- Seed runs once at startup; skips if data already exists (idempotent)
- Biomechanics v2 update uses version comparison — only updates when seed version > DB version
- Batch 1 exercises use name-based dedup — skips if exercise name already exists
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
- Conservation rule: zone shares sum to 1.0, zone doses sum to canonical Pectorals dose
- Confidence scoring: per-exercise (0.75–0.92), dose-weighted aggregate for day/week; null when no chest data
- Driver metadata: dominant_zone, top_modifier, archetype — for future Expo visualization
- Endpoints:
  - `GET /reports/pec-zones/day?date=` — daily pec zone breakdown + confidence
  - `GET /reports/pec-zones/week?week=` — weekly pec zone breakdown + confidence
  - `GET /reports/pec-zones/explain?exercise=` — per-exercise overlay features + adjustments + confidence + drivers
  - `GET /reports/pec-zones/analysis?exercise=` — full v2.5 pipeline debug with overlay stage, all pipeline outputs, raw inputs

## Game Integration Layer (Expo BulkCoach)
- **Non-breaking additive layer**: endpoints under `/game/` prefix
- **New table**: `game_bridge_sets` — stores muscle-target events from Expo, completely separate from canonical `lift_sets`
- **Bridge-dose formula**: `(estimated_tonnage or default) × (rpe/10) / N_targets`, defaults: compound=500, isolation=200
- **Data blending**: `/game/muscle-state` merges canonical lift_sets + bridge events
- **underfed_score**: uses ONLY canonical lift_sets, NOT bridge estimates
- **Idempotency**: `event_id` field for deduplication
- **session-close**: read-only finalizer, NOT required for correctness
- **Scoring formulas**:
  - freshness: `1/(1+fatigue/1000)` — normalized readiness index
  - heatmap: `0.50×(1-freshness) + 0.30×(load_7d/max) + 0.20×(1-recency_norm)`
  - priority: `gate × (0.25×deficit + 0.15×load_deficit + 0.20×freshness + 0.20×recency + 0.20×mode_suit)`, gate=freshness≥0.30
  - proximity fatigue bypass: if freshness < 0.30 AND load_deficit > 0.85, muscle enters queue with dampened score

## Hierarchy Patch (Deltoids/Traps)
- Patched source files have Deltoids and Traps columns zeroed in all 5 CSV matrices + all 3 V3 xlsx sheets
- **Shared utility `app/hierarchy.py`**: `build_derived_groups(db)` returns {group_id: [child_ids]}, `apply_derived_rollup(stim_dict, groups)` sums children into group
- Runtime derivation applied in: `muscle_day.py`, `weekly_muscles.py`, `muscle_dose.py`, `coach.py`, `weekly_optimizer.py`, `reports.py`
- Balance member lists use leaf muscles only (no group names) to prevent double-counting
- Admin re-seed endpoint: `POST /admin/reseed-matrices` (wipes + reloads matrix tables, does NOT touch lift_sets/exercises/muscles)

## Data Floor
- `DATA_FLOOR_DATE = date(2026, 3, 8)` and `DATA_FLOOR_TS = datetime(2026, 3, 8, 12, 38, 0, tzinfo=timezone.utc)` in `app/game_state.py`
- All time-series endpoints enforce BOTH: `performed_at >= DATA_FLOOR_DATE` AND `created_at >= DATA_FLOOR_TS`
- `created_at` column added to `lift_sets` via startup migration
- Purpose: isolate fresh data after prod DB reset

## Critical Rules
- **muscle_schema_version: 27** — 27 regions canonical
- **Pectorals = muscle_id 17** — pec zones are sidecar only, NOT in canonical schema
- **GAME_SOURCES**: `{"expo_bulkcoach"}` only for strength source classification
- **Frozen write contract**: `POST /game/log-set` and `POST /game/session-close` must NOT be modified
- **No invented seed data**: all values stored as-is from source files or authored batch data
- **New exercises get new rows and real authored matrices; no inferred overlays**

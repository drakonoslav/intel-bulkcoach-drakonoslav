# BulkCoach × Lifting-Intel — Daily Log Submission Spec

**For: Expo (BulkCoach) team**
**Intel endpoint:** `POST https://<intel-host>/vitals/daily-log`

---

## Overview

When the user taps **Save Entry** on the Daily Log screen, Expo sends one POST to Intel.
Intel handles all computation (scores, rolling averages, recommendations, macro deltas) and returns a full recommendation payload.
Expo stores the recommendation and displays it. No math happens on the Expo side.

---

## Part 1 — What Expo Already Has (Wire These Up Now)

These fields are already logged in the Expo Daily Log UI.
Map them to the Intel payload field name shown below — no new UI work needed.

### Identity (always required)

| Expo source | Intel field | Notes |
|---|---|---|
| Auth context | `expo_user_id` | String — Expo user ID |
| Date header in Daily Log | `date` | ISO string `"2026-03-11"` |

### Sleep — SELF-REPORT section

| Expo UI label | Intel field | Notes |
|---|---|---|
| Sleep field (min) | `sleep_duration_min` | Already shown as 420 |
| Actual Bed time | `bedtime_local` | Send as ISO datetime `"2026-03-10T21:45:00"` |
| Actual Wake time | `waketime_local` | Send as ISO datetime `"2026-03-11T05:30:00"` |

Intel derives from these automatically (no extra Expo work):
- `time_in_bed_min` — waketime minus bedtime
- `sleep_efficiency_pct` — sleep_duration / time_in_bed × 100
- `sleep_midpoint_min` — midpoint of the sleep window

### Heart / HRV section

| Expo UI label | Intel field | Type |
|---|---|---|
| HRV | `hrv_ms` | float |
| RHR | `resting_hr_bpm` | float |

### Weight / Body Comp section

| Expo UI label | Intel field | Type |
|---|---|---|
| Morning Weight | `body_weight_lb` | float |
| BIA AM average | `body_fat_pct` | float (%) |
| Fat-Free Mass | `fat_free_mass_lb` | float |
| Waist at Navel | `waist_at_navel_in` | float |

### Activity — Steps

| Expo UI label | Intel field | Type |
|---|---|---|
| Steps | `step_count` | int |

### Cardio Session section

| Expo UI label | Intel field | Notes |
|---|---|---|
| Start time | `cardio_start_time` | ISO datetime |
| End time | `cardio_end_time` | ISO datetime |
| Duration (computed) | `cardio_duration_min` | end − start in minutes |
| Z2 minutes | `cardio_zone2_min` | float |
| Z3 minutes | `cardio_zone3_min` | float (Z3 only, not Z4/Z5) |
| Cardio skipped | omit cardio fields | If skipped, send no cardio fields |

Intel derives `actual_cardio_mode` from zone minutes automatically:
- `zone3_min > 0` → `"zone_3"`
- `zone2_min > 0` → `"zone_2"`
- both zero or omitted → `"recovery_walk"`

### Lift Session section

| Expo UI label | Intel field | Notes |
|---|---|---|
| Start time | `lift_start_time` | ISO datetime |
| End time | `lift_end_time` | ISO datetime |
| Duration (computed) | `lift_duration_min` | end − start in minutes |
| Working Time | `lift_working_time_min` | float |
| Training Load selection | `completed_lift_mode` | Map: None→omit, Light→`"recovery_patterning"`, Moderate→`"pump"`, Hard→`"hypertrophy_build"`, Lifted→`"neural_tension"`, Deload→`"mobility"` |
| Lift skipped | omit lift fields | |

### Nutrition section

| Expo UI label | Intel field | Notes |
|---|---|---|
| Calories Consumed | `kcal_actual` | float |

### Pain / Injury section

| Expo UI label | Intel field | Mapping |
|---|---|---|
| Pain 0–10 slider | `soreness_score` | `round(pain / 2) + 1`, clamp 1–5 |

### Nocturnal Vitals — Androgen Proxy

| Expo UI label | Intel field | Mapping |
|---|---|---|
| Count + Firmness | `morning_erection_score` | Count=0→0, Count=1+Firmness<5→1, Count=1+Firmness≥5→2, Count≥2→3 |

---

## Part 2 — New Fields Expo Needs to Add

These DB columns already exist in Intel. No backend work needed.
Expo only needs to add the UI controls and include them in the payload.

All 6 subjective sliders use the same pattern: tap-to-rate 1–5 strip (same style as existing Quality star rating).

### Subjective Drive Block (add to existing SLEEP or new WELLBEING section)

| New UI label | Intel field | Scale | Default if skipped |
|---|---|---|---|
| Libido | `libido_score` | 1–5 | omit (Intel uses neutral) |
| Motivation | `motivation_score` | 1–5 | omit |
| Mood Stability | `mood_stability_score` | 1–5 | omit |
| Mental Drive | `mental_drive_score` | 1–5 | omit |
| Joint Friction | `joint_friction_score` | 1–5 | omit |

These sit adjacent to the Pain slider since they're the same subjective-feel cluster.

### Macro Actuals (add to NUTRITION section, below Calories Consumed)

| New UI label | Intel field | Type | Notes |
|---|---|---|---|
| Protein | `protein_g_actual` | float (g) | Number entry, same style as kcal |
| Carbs | `carbs_g_actual` | float (g) | Number entry |
| Fat | `fat_g_actual` | float (g) | Number entry |

These let Intel score macro adherence against the recommended day type (build vs reset etc).
All three are optional — if user skips, Intel still runs with kcal only.

---

## Part 3 — The Submission Payload (Complete Template)

```json
POST /vitals/daily-log
Content-Type: application/json

{
  "expo_user_id": "<user_id>",
  "date": "2026-03-11",

  "sleep_duration_min": 420,
  "bedtime_local": "2026-03-10T21:45:00",
  "waketime_local": "2026-03-11T05:30:00",

  "hrv_ms": 45,
  "resting_hr_bpm": 58,

  "body_weight_lb": 156.2,
  "body_fat_pct": 14.1,
  "fat_free_mass_lb": 134.0,
  "waist_at_navel_in": 31.4,

  "step_count": 8400,

  "cardio_duration_min": 40,
  "cardio_zone2_min": 30,
  "cardio_zone3_min": 10,

  "lift_duration_min": 75,
  "lift_working_time_min": 50,
  "completed_lift_mode": "hypertrophy_build",

  "kcal_actual": 2695,
  "protein_g_actual": 174,
  "carbs_g_actual": 331,
  "fat_g_actual": 54,

  "morning_erection_score": 2,
  "libido_score": 4,
  "motivation_score": 4,
  "mood_stability_score": 4,
  "mental_drive_score": 4,
  "soreness_score": 2,
  "joint_friction_score": 2
}
```

**All fields except `expo_user_id` and `date` are optional.**
Intel runs with whatever is available. Omit fields the user skipped rather than sending null.

---

## Part 4 — What Intel Returns

Intel returns the full recommendation synchronously in the same response. No polling needed.

```json
{
  "ok": true,
  "date": "2026-03-11",
  "expo_user_id": "<user_id>",
  "recommendation": {
    "cycleDay28": 11,
    "cycleWeekType": "overload",
    "scores": {
      "acuteScore": 74,
      "resourceScore": 68,
      "seasonalScore": 52,
      "compositeScore": 69,
      "oscillatorClass": "strong_build"
    },
    "flags": {
      "hardStopFatigue": false,
      "suppressedHrv": false,
      "elevatedRhr": false,
      "lowSleep": false,
      "monthlyResensitizeOverride": false,
      "cardioMonotony": false
    },
    "recommendedCardioMode": "zone_3",
    "recommendedLiftMode": "hypertrophy_build",
    "recommendedMacroDayType": "build",
    "macroTargets": {
      "kcal": 2695,
      "proteinG": 175,
      "carbsG": 350,
      "fatG": 60
    },
    "macroDelta": {
      "proteinDeltaG": 1.1,
      "carbsDeltaG": 19.1,
      "fatDeltaG": 5.6,
      "kcalDelta": 0.0
    },
    "reasoning": [
      "Composite score 69 (strong_build).",
      "Acute 74, Resource 68, Seasonal 52.",
      "Assigned cardio mode: zone_3.",
      "Assigned lift mode: hypertrophy_build.",
      "Assigned macro day: build."
    ]
  },
  "scoreBreakdowns": {
    "acute": [ ... ],
    "resource": [ ... ],
    "seasonal": [ ... ]
  }
}
```

**Key fields for Expo to surface on the dashboard:**

| Intel field | Display |
|---|---|
| `compositeScore` | OCS ring / number |
| `oscillatorClass` | Label (Strong Build / Peak / etc.) |
| `recommendedCardioMode` | "Zone 3 today" |
| `recommendedLiftMode` | "Hypertrophy Build" |
| `recommendedMacroDayType` | "Build Day" |
| `macroTargets` | Target gram numbers |
| `macroDelta.carbsDeltaG` | "+19g carbs from base plan" |
| `macroDelta.fatDeltaG` | "+6g fat from base plan" |
| `reasoning` | One-line explanation string |
| `flags.hardStopFatigue` | Warning banner if true |

---

## Part 5 — Submission Button Mechanics

The existing **Save Entry** button should:

1. Collect all available log fields into the payload above
2. `POST /vitals/daily-log` — single call, no pre-flight needed
3. On success: store `recommendation` object locally for the day's dashboard
4. On error: show toast, allow retry (Intel is idempotent — same day re-POST overwrites)

**Idempotency:** Intel uses `(expo_user_id, date)` as the unique key.
Submitting twice for the same day updates the record in place. Safe to retry.

---

## Part 6 — What Intel Computes (Expo Never Calculates)

For reference — Expo never needs to derive any of this:

- All 7d / 14d / 28d rolling averages
- Sleep efficiency, midpoint, time-in-bed
- `actual_cardio_mode` from zone minutes
- `morning_erection_score` → handled server-side if Expo sends raw count/firmness instead
- OCS composite score and all sub-scores
- Macro delta vs real food baseline
- Cycle day (1–28) and week type
- All flags and recommendation logic
- Macro templates and meal timing targets

from dataclasses import dataclass
from typing import List, Optional


@dataclass
class ConfidenceWeightedMetric:
    key: str
    raw_score: float
    max_score: float
    confidence: float
    weighted_score: float
    weighted_max: float


@dataclass
class ConfidenceWeightedScoreResult:
    score: float
    raw_weighted_score: float
    raw_weighted_max: float
    overall_confidence: float
    low_confidence_keys: List[str]


def make_metric(key: str, raw_score: float, max_score: float, confidence: float) -> ConfidenceWeightedMetric:
    c = max(0.0, min(1.0, float(confidence)))
    return ConfidenceWeightedMetric(
        key=key,
        raw_score=float(raw_score),
        max_score=float(max_score),
        confidence=c,
        weighted_score=float(raw_score) * c,
        weighted_max=float(max_score) * c,
    )


def finalize_weighted_score(metrics: List[ConfidenceWeightedMetric]) -> ConfidenceWeightedScoreResult:
    """
    Score = 100 * sum(s_i * c_i) / sum(m_i * c_i)
    """
    weighted_score_sum = sum(m.weighted_score for m in metrics)
    weighted_max_sum = sum(m.weighted_max for m in metrics)

    if weighted_max_sum == 0:
        score = 0.0
    else:
        score = 100.0 * weighted_score_sum / weighted_max_sum

    score = max(0.0, min(100.0, score))
    overall_confidence = (
        sum(m.confidence for m in metrics) / len(metrics) if metrics else 0.0
    )
    low_confidence_keys = [m.key for m in metrics if m.confidence < 0.6]

    return ConfidenceWeightedScoreResult(
        score=round(score, 1),
        raw_weighted_score=round(weighted_score_sum, 2),
        raw_weighted_max=round(weighted_max_sum, 2),
        overall_confidence=round(overall_confidence, 3),
        low_confidence_keys=low_confidence_keys,
    )


def derive_hrv_confidence(
    hrv_ms,
    hrv_sample_count: Optional[int] = None,
    consistent_window: Optional[bool] = None,
) -> float:
    """
    c_HRV = 0.50 base (if present)
            + 0.25 if consistent measurement window
            + 0.10 assumed overnight
            + 0.15 if sample count adequate (>=3)
    clamped to [0, 1]
    """
    if hrv_ms is None:
        return 0.0
    c = 0.50
    if consistent_window:
        c += 0.25
    if hrv_sample_count is not None and hrv_sample_count >= 3:
        c += 0.15
    c += 0.10  # assume overnight morning log
    return max(0.0, min(1.0, c))


def derive_rhr_confidence(rhr_bpm) -> float:
    if rhr_bpm is None:
        return 0.0
    return 0.90


def derive_sleep_confidence(
    sleep_duration_min,
    sleep_efficiency_pct=None,
    sleep_midpoint_known: bool = False,
) -> float:
    if sleep_duration_min is None:
        return 0.0
    c = 0.65
    if sleep_efficiency_pct is not None:
        c += 0.15
    if sleep_midpoint_known:
        c += 0.10
    return max(0.0, min(1.0, c))


def derive_body_comp_confidence(
    body_weight_lb,
    body_fat_pct=None,
    ffm_lb=None,
    tbw_pct=None,
    fasted_morning: Optional[bool] = None,
    delta_bf_pct: Optional[float] = None,
    delta_ffm_lb: Optional[float] = None,
    stored_confidence: Optional[float] = None,
) -> float:
    """
    c_FFM = base
            + 0.10 if fasted_morning
            - 0.20 if abs(delta_bf) > 1.0%
            - 0.20 if abs(delta_ffm) > 2.0 lb
            - 0.10 if TBW outside [45, 70]%
    clamped to [0, 1]
    """
    if body_weight_lb is None:
        return 0.0

    if stored_confidence is not None:
        c = float(stored_confidence)
    elif body_fat_pct is None or ffm_lb is None:
        c = 0.55  # weight only
    else:
        c = 0.70  # full smart-scale reading

    if fasted_morning:
        c += 0.10

    if delta_bf_pct is not None and abs(delta_bf_pct) > 1.0:
        c -= 0.20
    if delta_ffm_lb is not None and abs(delta_ffm_lb) > 2.0:
        c -= 0.20
    if tbw_pct is not None and not (45 <= tbw_pct <= 70):
        c -= 0.10

    return max(0.0, min(1.0, c))


def derive_waist_confidence(
    waist_value,
    days_since_measure: Optional[int] = None,
    manual_confidence: Optional[float] = None,
) -> float:
    """
    c_waist = manual_confidence - staleness_penalty
    staleness: 0 days→0 penalty, 4-7 days→-0.10, 8-10→-0.15, >10→-0.25
    """
    if waist_value is None:
        return 0.0
    c = manual_confidence if manual_confidence is not None else 0.80
    if days_since_measure is not None:
        if days_since_measure <= 3:
            pass
        elif days_since_measure <= 7:
            c -= 0.10
        elif days_since_measure <= 10:
            c -= 0.15
        else:
            c -= 0.25
    return max(0.0, min(1.0, c))


def derive_subjective_confidence(
    fields_completed: int,
    total_fields: int = 4,
    logged_in_window: bool = False,
) -> float:
    """
    c_subjective = completed/expected + 0.10 if logged in correct window
    Missing fields reduce confidence — do NOT treat as low readiness.
    """
    if total_fields == 0:
        return 0.0
    c = fields_completed / total_fields
    if logged_in_window:
        c += 0.10
    return max(0.0, min(1.0, c))

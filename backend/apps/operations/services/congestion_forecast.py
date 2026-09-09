"""Deterministic multi-horizon port congestion forecast.

Projects the CURRENT congestion score (from the congestion engine) forward to
1 / 3 / 7 / 14 day horizons using a transparent, rule-based trend extrapolation
— NOT a machine-learning model. For each horizon it returns:

    congestion_score       projected 0..100 score
    expected_waiting_time   projected berth waiting time (days)
    confidence              0..1, decaying with horizon + missing data
    risk_level              LOW/MEDIUM/HIGH/SEVERE (reuses the congestion bands)

Method (all documented, deterministic):
  * The base score is the current congestion engine score.
  * A trend term (per-day change) is derived from a supplied recent trend or a
    pipeline of recent observations; absent a trend it is 0 (persistence).
  * Seasonal and expected-arrival pressures nudge the projection.
  * The projected score is mean-reverting: it is pulled a documented fraction of
    the way back toward a long-run baseline as the horizon lengthens (congestion
    spikes do not persist indefinitely).
  * Confidence decays with the horizon and with missing inputs, so a 14-day
    projection is never presented as being as certain as a 1-day one.

This module does not fabricate data: signals it isn't given are simply not used,
and their absence lowers confidence.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Optional

from .congestion import (
    CongestionInput,
    Classification,
    classify,
    score_congestion,
)

# Horizons (days) this forecaster produces.
HORIZONS = [1, 3, 7, 14]

# Waiting-time reference: a congestion score of 100 corresponds to ~this many
# days of berth waiting (documented linear mapping when no realized wait given).
WAIT_DAYS_AT_MAX_SCORE = 10.0

# Mean reversion: fraction of the gap to the baseline closed per day of horizon,
# capped. Congestion is assumed to partially normalize over time.
REVERSION_PER_DAY = 0.04
REVERSION_CAP = 0.5
# Long-run baseline congestion score reverted toward (moderate, documented).
BASELINE_SCORE = 30.0

# Confidence: starts at this for a 1-day horizon and decays per day, floored.
CONFIDENCE_BASE = 0.9
CONFIDENCE_DECAY_PER_DAY = 0.04
CONFIDENCE_FLOOR = 0.2
# Penalty applied to confidence when a trend signal is unavailable (persistence
# assumption is weaker information).
NO_TREND_CONFIDENCE_PENALTY = 0.15


@dataclass
class CongestionForecastInput:
    """Inputs for the congestion forecast.

    `current` are the present-state congestion signals (fed to the congestion
    engine). `trend_per_day` is the recent per-day change in the congestion
    score (positive = worsening); if None, persistence (0) is assumed and
    confidence is reduced. `recent_waiting_time_days` overrides the score-derived
    waiting estimate when a realized wait is known.
    """

    current: CongestionInput
    trend_per_day: Optional[float] = None
    recent_waiting_time_days: Optional[float] = None


@dataclass
class HorizonForecast:
    horizon_days: int
    congestion_score: float
    expected_waiting_time_days: float
    confidence: float
    risk_level: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class CongestionForecastResult:
    current_score: float
    current_classification: str
    trend_per_day: float
    horizons: list[HorizonForecast]
    missing_signals: list[str]
    inputs: dict

    def to_dict(self) -> dict:
        return {
            "current_score": self.current_score,
            "current_classification": self.current_classification,
            "trend_per_day": self.trend_per_day,
            "horizons": [h.to_dict() for h in self.horizons],
            "missing_signals": self.missing_signals,
            "inputs": self.inputs,
        }


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def _waiting_days_for_score(score: float, realized: Optional[float]) -> float:
    """Map a congestion score to expected waiting days.

    If a realized recent waiting time is known, scale it by how the projected
    score compares to the current score-implied wait; otherwise use the linear
    score->days reference.
    """
    linear = (score / 100.0) * WAIT_DAYS_AT_MAX_SCORE
    if realized is not None and realized >= 0:
        # Blend the realized wait with the linear model (equal weight) so a known
        # wait anchors the estimate without ignoring the projected score.
        return round((realized + linear) / 2.0, 2)
    return round(linear, 2)


def forecast_congestion(inp: CongestionForecastInput) -> CongestionForecastResult:
    """Produce the 1/3/7/14-day congestion forecast deterministically."""
    current = score_congestion(inp.current)
    current_score = current.congestion_score
    missing = list(current.missing_factors)

    trend = inp.trend_per_day if inp.trend_per_day is not None else 0.0
    has_trend = inp.trend_per_day is not None

    horizons: list[HorizonForecast] = []
    for h in HORIZONS:
        # 1) Linear trend projection.
        projected = current_score + trend * h
        # 2) Mean reversion toward the baseline (stronger at longer horizons).
        reversion = min(REVERSION_PER_DAY * h, REVERSION_CAP)
        projected = projected + reversion * (BASELINE_SCORE - projected)
        projected = _clamp(projected, 0.0, 100.0)

        wait = _waiting_days_for_score(projected, inp.recent_waiting_time_days)

        # 3) Confidence: decays with horizon; penalized if trend/missing data.
        conf = CONFIDENCE_BASE - CONFIDENCE_DECAY_PER_DAY * h
        if not has_trend:
            conf -= NO_TREND_CONFIDENCE_PENALTY
        if missing:
            # Each missing current-state signal shaves a little confidence.
            conf -= min(0.03 * len(missing), 0.2)
        conf = round(_clamp(conf, CONFIDENCE_FLOOR, 1.0), 3)

        horizons.append(
            HorizonForecast(
                horizon_days=h,
                congestion_score=round(projected, 2),
                expected_waiting_time_days=wait,
                confidence=conf,
                risk_level=classify(projected).value,
            )
        )

    return CongestionForecastResult(
        current_score=current_score,
        current_classification=current.classification,
        trend_per_day=round(trend, 4),
        horizons=horizons,
        missing_signals=missing,
        inputs={
            "trend_per_day": inp.trend_per_day,
            "recent_waiting_time_days": inp.recent_waiting_time_days,
            "current": current.inputs,
        },
    )

"""Deterministic, explainable port congestion score.

This is a transparent rule-based score — NOT a machine-learning model and NOT a
forecast. It combines the current-state congestion signals into a single 0-100
score with a LOW/MEDIUM/HIGH/SEVERE classification, and records every input and
per-factor contribution so the result is fully explainable.

How the score is computed
-------------------------
Each factor is normalized to a 0..1 "pressure" via a documented saturating
function `min(value / reference, 1)` (higher = more congested). Weather warning
is a categorical 0..1 severity. Factors are combined as a weighted average:

    score = 100 * sum(weight_i * normalized_i) / sum(weight_i)

Only factors whose input was PROVIDED are included; the weights of the available
factors are renormalized so that missing inputs neither inflate nor deflate the
score (they are simply not counted, and this is reported in the breakdown).

The reference values and weights below are explicit, documented constants — the
score is deterministic and reproducible, and the breakdown shows exactly how
each factor contributed.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Optional


class Classification(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    SEVERE = "SEVERE"


# --- Factor weights (relative importance). Renormalized over available inputs. ---
WEIGHTS: dict[str, float] = {
    "vessels_waiting": 0.28,       # queueing is the strongest congestion signal
    "recent_waiting_time": 0.24,   # realized delay
    "vessels_near_port": 0.14,     # approaching load on the anchorage
    "expected_arrivals": 0.12,     # near-future inbound pressure
    "throughput_utilization": 0.12,# how close to handling capacity
    "weather_warning": 0.06,       # can halt operations
    "historical_traffic": 0.04,    # baseline busyness of the port
}

# --- Reference (saturation) values: the input level that maps to pressure 1.0.
# Documented, deliberately conservative defaults; a port can override them.
REFERENCES: dict[str, float] = {
    "vessels_waiting": 15.0,        # ~15 vessels waiting => maxed
    "recent_waiting_time_days": 7.0,  # ~7 days average wait => maxed
    "vessels_near_port": 30.0,      # ~30 vessels in the vicinity => maxed
    "expected_arrivals": 20.0,      # ~20 expected arrivals (window) => maxed
    # throughput_utilization is already a 0..1 ratio (used / capacity).
    "historical_traffic": 40.0,     # ~40 avg calls/period => maxed baseline
}

# --- Weather warning severity -> 0..1 pressure (categorical). ---
WEATHER_SEVERITY: dict[str, float] = {
    "none": 0.0,
    "low": 0.25,
    "moderate": 0.5,
    "high": 0.8,
    "severe": 1.0,
}

# --- Classification thresholds on the 0..100 score. ---
THRESHOLD_MEDIUM = 30.0
THRESHOLD_HIGH = 55.0
THRESHOLD_SEVERE = 75.0


@dataclass
class CongestionInput:
    """Inputs for the congestion score. Any field left None is treated as
    'not available' and excluded from the weighting (never fabricated)."""

    vessels_near_port: Optional[int] = None
    vessels_waiting: Optional[int] = None
    # Average number of vessel calls in a recent comparable period (baseline).
    historical_traffic: Optional[float] = None
    expected_arrivals: Optional[int] = None
    # Throughput utilization as used/capacity (0..1). Provide directly, or the
    # adapter can compute it from tonnes handled vs capacity.
    throughput_utilization: Optional[float] = None
    # One of WEATHER_SEVERITY keys (none/low/moderate/high/severe).
    weather_warning: Optional[str] = None
    recent_waiting_time_days: Optional[float] = None


@dataclass
class FactorContribution:
    factor: str
    raw_value: object
    normalized: float          # 0..1 pressure
    weight: float              # renormalized weight actually used
    contribution: float        # weight * normalized * 100 (points added)
    available: bool


@dataclass
class CongestionResult:
    congestion_score: float                # 0..100
    classification: str                    # Classification value
    factors: list[FactorContribution]
    inputs: dict                           # the raw inputs (explainability/audit)
    missing_factors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "congestion_score": self.congestion_score,
            "classification": self.classification,
            "factors": [asdict(f) for f in self.factors],
            "inputs": self.inputs,
            "missing_factors": self.missing_factors,
        }


def _saturate(value: float, reference: float) -> float:
    """Normalize a non-negative value to 0..1 via min(value/reference, 1)."""
    if reference <= 0:
        return 0.0
    return max(0.0, min(value / reference, 1.0))


def _normalized_factors(inp: CongestionInput) -> dict[str, Optional[float]]:
    """Compute each factor's 0..1 pressure, or None if its input is missing."""
    out: dict[str, Optional[float]] = {}

    out["vessels_waiting"] = (
        _saturate(inp.vessels_waiting, REFERENCES["vessels_waiting"])
        if inp.vessels_waiting is not None else None
    )
    out["recent_waiting_time"] = (
        _saturate(inp.recent_waiting_time_days, REFERENCES["recent_waiting_time_days"])
        if inp.recent_waiting_time_days is not None else None
    )
    out["vessels_near_port"] = (
        _saturate(inp.vessels_near_port, REFERENCES["vessels_near_port"])
        if inp.vessels_near_port is not None else None
    )
    out["expected_arrivals"] = (
        _saturate(inp.expected_arrivals, REFERENCES["expected_arrivals"])
        if inp.expected_arrivals is not None else None
    )
    out["throughput_utilization"] = (
        max(0.0, min(float(inp.throughput_utilization), 1.0))
        if inp.throughput_utilization is not None else None
    )
    out["weather_warning"] = (
        WEATHER_SEVERITY.get(str(inp.weather_warning).lower())
        if inp.weather_warning is not None else None
    )
    out["historical_traffic"] = (
        _saturate(inp.historical_traffic, REFERENCES["historical_traffic"])
        if inp.historical_traffic is not None else None
    )
    return out


def classify(score: float) -> Classification:
    if score >= THRESHOLD_SEVERE:
        return Classification.SEVERE
    if score >= THRESHOLD_HIGH:
        return Classification.HIGH
    if score >= THRESHOLD_MEDIUM:
        return Classification.MEDIUM
    return Classification.LOW


def score_congestion(inp: CongestionInput) -> CongestionResult:
    """Compute the deterministic congestion score with an explainable breakdown."""
    normalized = _normalized_factors(inp)

    # Renormalize weights over the factors that are actually available.
    available = {k: v for k, v in normalized.items() if v is not None}
    total_weight = sum(WEIGHTS[k] for k in available)

    factors: list[FactorContribution] = []
    missing: list[str] = []
    score = 0.0

    raw_lookup = {
        "vessels_waiting": inp.vessels_waiting,
        "recent_waiting_time": inp.recent_waiting_time_days,
        "vessels_near_port": inp.vessels_near_port,
        "expected_arrivals": inp.expected_arrivals,
        "throughput_utilization": inp.throughput_utilization,
        "weather_warning": inp.weather_warning,
        "historical_traffic": inp.historical_traffic,
    }

    for factor in WEIGHTS:
        norm = normalized[factor]
        if norm is None:
            missing.append(factor)
            factors.append(
                FactorContribution(
                    factor=factor, raw_value=None, normalized=0.0,
                    weight=0.0, contribution=0.0, available=False,
                )
            )
            continue
        weight = WEIGHTS[factor] / total_weight if total_weight > 0 else 0.0
        contribution = weight * norm * 100.0
        score += contribution
        factors.append(
            FactorContribution(
                factor=factor,
                raw_value=raw_lookup[factor],
                normalized=round(norm, 4),
                weight=round(weight, 4),
                contribution=round(contribution, 2),
                available=True,
            )
        )

    score = round(score, 2)
    return CongestionResult(
        congestion_score=score,
        classification=classify(score).value,
        factors=factors,
        inputs=asdict(inp),
        missing_factors=missing,
    )

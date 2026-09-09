"""Transparent, deterministic vessel suitability scoring.

A rule-based score (0-100) for how suitable a vessel is for a given cargo /
lane / destination — NOT a machine-learning model. Every factor is scored
independently to a 0..1 "goodness" (higher = better), combined as a weighted
average, and the full per-factor breakdown is returned so the score is always
explainable.

Factors
-------
Hard constraints (a failure zeroes the factor, heavily penalizing the score):
    port_compatibility, draft_suitability, loa_suitability, beam_suitability
Capacity / commercial / risk (graded 0..1):
    cargo_capacity, estimated_freight, eta_reliability, congestion_risk,
    weather_risk, expected_demurrage, fuel_efficiency

Missing inputs are EXCLUDED (their weight is redistributed), never treated as
zero — so incomplete data neither inflates nor deflates the score. This mirrors
the congestion engine's approach.

No ML is used. Pure Python (no Django) so it is easy to unit-test; a thin
adapter can map ORM models onto SuitabilityInput.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from decimal import Decimal
from typing import Optional

Number = float


# ---------------------------------------------------------------------------
# Factor weights (relative importance). Renormalized over available factors.
# Documented, explicit constants — the score is deterministic given these.
# ---------------------------------------------------------------------------
WEIGHTS: dict[str, float] = {
    # Hard physical/operational fit — dominate the score.
    "port_compatibility": 0.16,
    "draft_suitability": 0.14,
    "loa_suitability": 0.08,
    "beam_suitability": 0.06,
    "cargo_capacity": 0.14,
    # Commercial.
    "estimated_freight": 0.14,
    # Reliability / risk (higher factor = lower risk = better).
    "eta_reliability": 0.09,
    "congestion_risk": 0.07,
    "weather_risk": 0.06,
    "expected_demurrage": 0.06,
    # Efficiency (where data exists).
    "fuel_efficiency": 0.04,
}

# --- Reference (saturation) values for graded factors. Documented defaults. ---
# Demurrage cost (currency) at which the demurrage factor hits its worst (0).
REF_DEMURRAGE_MAX = 500_000.0
# Congestion score (0..100) is used directly as risk.
# Weather risk is already 0..1.
# ETA reliability (0..1) and fuel efficiency (0..1) are used directly.


@dataclass
class SuitabilityInput:
    """Inputs for the suitability score. Any field left None is 'not available'
    and excluded from the weighting (never fabricated)."""

    # --- hard constraints ---
    # port_compatible: True/False/None. A concrete False zeroes the factor.
    port_compatible: Optional[bool] = None

    # Dimensions: vessel value + berth/port limit. If vessel exceeds the limit
    # the factor is 0 (infeasible); otherwise graded by headroom.
    vessel_draft: Optional[Number] = None
    max_draft: Optional[Number] = None
    vessel_loa: Optional[Number] = None
    max_loa: Optional[Number] = None
    vessel_beam: Optional[Number] = None
    max_beam: Optional[Number] = None

    # --- capacity ---
    vessel_dwt: Optional[Number] = None
    required_tonnes: Optional[Number] = None

    # --- commercial ---
    # estimated_freight_per_tonne for THIS vessel, plus a market reference range
    # so lower-than-market freight scores better.
    estimated_freight_per_tonne: Optional[Number] = None
    market_freight_low: Optional[Number] = None
    market_freight_high: Optional[Number] = None

    # --- reliability / risk (0..1 unless noted) ---
    eta_reliability: Optional[Number] = None          # 0..1, higher = more reliable
    congestion_score: Optional[Number] = None         # 0..100 (destination)
    weather_risk: Optional[Number] = None             # 0..1, higher = worse
    expected_demurrage_cost: Optional[Number] = None  # currency, higher = worse

    # --- efficiency ---
    fuel_efficiency: Optional[Number] = None          # 0..1, higher = better


@dataclass
class FactorScore:
    factor: str
    raw_value: object
    normalized: float      # 0..1 goodness
    weight: float          # renormalized weight actually used
    contribution: float    # weight * normalized * 100 (points)
    available: bool
    note: str = ""


@dataclass
class SuitabilityResult:
    score: float                       # 0..100
    factors: list[FactorScore]
    inputs: dict
    missing_factors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "score": self.score,
            "factors": [asdict(f) for f in self.factors],
            "inputs": self.inputs,
            "missing_factors": self.missing_factors,
        }


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


# ---------------------------------------------------------------------------
# Per-factor scorers: return (normalized_or_None, note). None => unavailable.
# ---------------------------------------------------------------------------
def _score_port_compatibility(inp: SuitabilityInput):
    if inp.port_compatible is None:
        return None, "no compatibility verdict provided"
    return (1.0, "compatible") if inp.port_compatible else (0.0, "port incompatible")


def _score_dimension(vessel, limit, label):
    """Graded fit: exceeding the limit => 0; otherwise reward headroom.

    A vessel using <= the limit scores 1.0 at exactly the limit is still fine
    (score ~1). We give full marks up to the limit (fit is binary-ish for a
    berth), so any feasible dimension scores 1.0 and an infeasible one 0.0.
    """
    if vessel is None or limit is None:
        return None, f"{label}: value/limit not provided"
    if limit <= 0:
        return None, f"{label}: invalid limit"
    if vessel > limit:
        return 0.0, f"{label} {vessel} exceeds limit {limit}"
    return 1.0, f"{label} {vessel} within limit {limit}"


def _score_cargo_capacity(inp: SuitabilityInput):
    if inp.vessel_dwt is None or inp.required_tonnes is None:
        return None, "dwt/required tonnes not provided"
    if inp.required_tonnes <= 0:
        return None, "required tonnes not positive"
    if inp.vessel_dwt < inp.required_tonnes:
        # Cannot carry the required parcel in one lift -> infeasible.
        return 0.0, f"DWT {inp.vessel_dwt} < required {inp.required_tonnes}"
    # Best fit when DWT closely matches the requirement (little wasted capacity).
    ratio = inp.required_tonnes / inp.vessel_dwt   # 0..1, 1 = perfect fit
    # Utilization 0.7..1.0 is ideal; below that, capacity is under-used.
    return _clamp01(ratio / 0.9), f"utilization {ratio:.2f} of DWT"


def _score_estimated_freight(inp: SuitabilityInput):
    f = inp.estimated_freight_per_tonne
    if f is None:
        return None, "no estimated freight"
    lo, hi = inp.market_freight_low, inp.market_freight_high
    if lo is None or hi is None or hi <= lo:
        return None, "no market reference range for freight"
    # Lower freight is better: map [lo, hi] -> [1, 0], clamp outside.
    norm = (hi - f) / (hi - lo)
    return _clamp01(norm), f"freight {f} vs market [{lo}, {hi}]"


def _score_eta_reliability(inp: SuitabilityInput):
    if inp.eta_reliability is None:
        return None, "no ETA reliability"
    return _clamp01(inp.eta_reliability), f"eta reliability {inp.eta_reliability}"


def _score_congestion_risk(inp: SuitabilityInput):
    if inp.congestion_score is None:
        return None, "no congestion score"
    # 0..100 risk -> goodness = 1 - risk/100.
    return _clamp01(1.0 - inp.congestion_score / 100.0), f"congestion {inp.congestion_score}/100"


def _score_weather_risk(inp: SuitabilityInput):
    if inp.weather_risk is None:
        return None, "no weather risk"
    return _clamp01(1.0 - inp.weather_risk), f"weather risk {inp.weather_risk}"


def _score_expected_demurrage(inp: SuitabilityInput):
    d = inp.expected_demurrage_cost
    if d is None:
        return None, "no expected demurrage"
    if d < 0:
        return None, "negative demurrage ignored"
    # Higher demurrage is worse; saturate at REF_DEMURRAGE_MAX.
    return _clamp01(1.0 - d / REF_DEMURRAGE_MAX), f"expected demurrage {d}"


def _score_fuel_efficiency(inp: SuitabilityInput):
    if inp.fuel_efficiency is None:
        return None, "no fuel efficiency data"
    return _clamp01(inp.fuel_efficiency), f"fuel efficiency {inp.fuel_efficiency}"


def _all_factor_scores(inp: SuitabilityInput) -> dict[str, tuple]:
    return {
        "port_compatibility": _score_port_compatibility(inp),
        "draft_suitability": _score_dimension(inp.vessel_draft, inp.max_draft, "draft"),
        "loa_suitability": _score_dimension(inp.vessel_loa, inp.max_loa, "LOA"),
        "beam_suitability": _score_dimension(inp.vessel_beam, inp.max_beam, "beam"),
        "cargo_capacity": _score_cargo_capacity(inp),
        "estimated_freight": _score_estimated_freight(inp),
        "eta_reliability": _score_eta_reliability(inp),
        "congestion_risk": _score_congestion_risk(inp),
        "weather_risk": _score_weather_risk(inp),
        "expected_demurrage": _score_expected_demurrage(inp),
        "fuel_efficiency": _score_fuel_efficiency(inp),
    }


def score_vessel_suitability(inp: SuitabilityInput) -> SuitabilityResult:
    """Compute the deterministic suitability score with an explainable breakdown."""
    raw_scores = _all_factor_scores(inp)

    raw_lookup = {
        "port_compatibility": inp.port_compatible,
        "draft_suitability": inp.vessel_draft,
        "loa_suitability": inp.vessel_loa,
        "beam_suitability": inp.vessel_beam,
        "cargo_capacity": inp.required_tonnes,
        "estimated_freight": inp.estimated_freight_per_tonne,
        "eta_reliability": inp.eta_reliability,
        "congestion_risk": inp.congestion_score,
        "weather_risk": inp.weather_risk,
        "expected_demurrage": inp.expected_demurrage_cost,
        "fuel_efficiency": inp.fuel_efficiency,
    }

    # Available factors = those whose scorer returned a value.
    available = {k: v[0] for k, v in raw_scores.items() if v[0] is not None}
    total_weight = sum(WEIGHTS[k] for k in available)

    factors: list[FactorScore] = []
    missing: list[str] = []
    score = 0.0

    for factor in WEIGHTS:
        norm, note = raw_scores[factor]
        if norm is None:
            missing.append(factor)
            factors.append(
                FactorScore(factor, raw_lookup[factor], 0.0, 0.0, 0.0, False, note)
            )
            continue
        weight = WEIGHTS[factor] / total_weight if total_weight > 0 else 0.0
        contribution = weight * norm * 100.0
        score += contribution
        factors.append(
            FactorScore(
                factor=factor,
                raw_value=raw_lookup[factor],
                normalized=round(norm, 4),
                weight=round(weight, 4),
                contribution=round(contribution, 2),
                available=True,
                note=note,
            )
        )

    return SuitabilityResult(
        score=round(score, 2),
        factors=factors,
        inputs={
            k: (float(v) if isinstance(v, Decimal) else v)
            for k, v in asdict(inp).items()
        },
        missing_factors=missing,
    )

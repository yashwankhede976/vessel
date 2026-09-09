"""Unified risk engine (transparent, deterministic).

Blends independent risk signals into one overall 0..100 risk score with a
LOW/MEDIUM/HIGH level and a full factor breakdown. Each factor is a 0..1 risk
(higher = worse) with documented normalization. It is rule-based — NOT ML.

Factors:
    freight        freight-rate risk (volatility / rate uncertainty), 0..1
    port           port congestion risk (0..100 congestion score), normalized
    weather        weather/marine risk, 0..1
    eta            schedule risk (delay probability), 0..1
    demurrage      expected demurrage cost, saturated against a reference
    commodity      commodity-price risk (volatility), 0..1
    fx             FX risk (currency volatility), 0..1
    geopolitical   disruption risk, 0..1 (only when reliable data exists)

CRITICAL RULE: a factor with no data stays UNKNOWN. It is NOT given an invented
value and is excluded from the weighting (its weight is redistributed across the
factors that DO have data). Unknown factors are reported in `unknown_factors`
and shown as available=False in the breakdown. This mirrors the congestion and
suitability engines and satisfies the platform rule that unknown data must
remain UNKNOWN rather than receiving fabricated values.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Optional

Number = float


class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


# --- Factor weights (relative importance). Renormalized over KNOWN factors. ---
WEIGHTS: dict[str, float] = {
    "freight": 0.20,
    "port": 0.16,
    "weather": 0.14,
    "eta": 0.14,
    "demurrage": 0.12,
    "commodity": 0.10,
    "fx": 0.08,
    "geopolitical": 0.06,
}

# --- Reference: expected demurrage cost (currency) mapping to risk 1.0. ---
REF_DEMURRAGE_MAX = 500_000.0

# --- Level thresholds on the 0..100 overall score. ---
LEVEL_MEDIUM = 33.0
LEVEL_HIGH = 66.0


@dataclass
class RiskInput:
    """Risk signals. Any field left None stays UNKNOWN (never invented)."""

    freight_volatility: Optional[Number] = None       # 0..1
    port_congestion: Optional[Number] = None           # 0..100
    weather_risk: Optional[Number] = None              # 0..1
    eta_delay_probability: Optional[Number] = None     # 0..1
    expected_demurrage_cost: Optional[Number] = None   # currency
    commodity_volatility: Optional[Number] = None      # 0..1
    fx_volatility: Optional[Number] = None             # 0..1
    geopolitical_risk: Optional[Number] = None         # 0..1 (reliable data only)


@dataclass
class RiskFactor:
    factor: str
    raw_value: object
    normalized: Optional[float]   # 0..1 risk, or None if UNKNOWN
    weight: float                 # renormalized weight actually used (0 if unknown)
    contribution: float           # weight * normalized * 100 (0 if unknown)
    available: bool               # False => UNKNOWN (excluded)
    note: str = ""


@dataclass
class RiskResult:
    overall_score: float               # 0..100
    risk_level: str                    # RiskLevel value
    factors: list[RiskFactor]
    inputs: dict
    unknown_factors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "overall_score": self.overall_score,
            "risk_level": self.risk_level,
            "factors": [asdict(f) for f in self.factors],
            "inputs": self.inputs,
            "unknown_factors": self.unknown_factors,
        }


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def level_for(score: float) -> RiskLevel:
    if score >= LEVEL_HIGH:
        return RiskLevel.HIGH
    if score >= LEVEL_MEDIUM:
        return RiskLevel.MEDIUM
    return RiskLevel.LOW


def _normalized(inp: RiskInput) -> dict[str, tuple]:
    """Return {factor: (normalized_or_None, note)}. None => UNKNOWN."""
    out: dict[str, tuple] = {}
    out["freight"] = (
        (_clamp01(inp.freight_volatility), f"freight volatility {inp.freight_volatility}")
        if inp.freight_volatility is not None else (None, "UNKNOWN: no freight signal")
    )
    out["port"] = (
        (_clamp01(inp.port_congestion / 100.0), f"congestion {inp.port_congestion}/100")
        if inp.port_congestion is not None else (None, "UNKNOWN: no port signal")
    )
    out["weather"] = (
        (_clamp01(inp.weather_risk), f"weather risk {inp.weather_risk}")
        if inp.weather_risk is not None else (None, "UNKNOWN: no weather signal")
    )
    out["eta"] = (
        (_clamp01(inp.eta_delay_probability), f"delay prob {inp.eta_delay_probability}")
        if inp.eta_delay_probability is not None else (None, "UNKNOWN: no ETA signal")
    )
    if inp.expected_demurrage_cost is None:
        out["demurrage"] = (None, "UNKNOWN: no demurrage estimate")
    elif inp.expected_demurrage_cost < 0:
        out["demurrage"] = (None, "UNKNOWN: negative demurrage ignored")
    else:
        out["demurrage"] = (
            _clamp01(inp.expected_demurrage_cost / REF_DEMURRAGE_MAX),
            f"expected demurrage {inp.expected_demurrage_cost}",
        )
    out["commodity"] = (
        (_clamp01(inp.commodity_volatility), f"commodity volatility {inp.commodity_volatility}")
        if inp.commodity_volatility is not None else (None, "UNKNOWN: no commodity signal")
    )
    out["fx"] = (
        (_clamp01(inp.fx_volatility), f"fx volatility {inp.fx_volatility}")
        if inp.fx_volatility is not None else (None, "UNKNOWN: no FX signal")
    )
    out["geopolitical"] = (
        (_clamp01(inp.geopolitical_risk), f"geopolitical {inp.geopolitical_risk}")
        if inp.geopolitical_risk is not None else (None, "UNKNOWN: no reliable geopolitical data")
    )
    return out


def score_risk(inp: RiskInput) -> RiskResult:
    """Compute the unified risk score (0-100) with an explainable breakdown.

    Unknown factors are excluded (weight redistributed) and reported — never
    assigned a fabricated value.
    """
    signals = _normalized(inp)
    raw_lookup = {
        "freight": inp.freight_volatility,
        "port": inp.port_congestion,
        "weather": inp.weather_risk,
        "eta": inp.eta_delay_probability,
        "demurrage": inp.expected_demurrage_cost,
        "commodity": inp.commodity_volatility,
        "fx": inp.fx_volatility,
        "geopolitical": inp.geopolitical_risk,
    }

    available = {k: v[0] for k, v in signals.items() if v[0] is not None}
    total_weight = sum(WEIGHTS[k] for k in available)

    factors: list[RiskFactor] = []
    unknown: list[str] = []
    score = 0.0

    for factor in WEIGHTS:
        norm, note = signals[factor]
        if norm is None:
            unknown.append(factor)
            factors.append(
                RiskFactor(factor, raw_lookup[factor], None, 0.0, 0.0, False, note)
            )
            continue
        weight = WEIGHTS[factor] / total_weight if total_weight > 0 else 0.0
        contribution = weight * norm * 100.0
        score += contribution
        factors.append(
            RiskFactor(
                factor=factor,
                raw_value=raw_lookup[factor],
                normalized=round(norm, 4),
                weight=round(weight, 4),
                contribution=round(contribution, 2),
                available=True,
                note=note,
            )
        )

    score = round(score, 2)
    return RiskResult(
        overall_score=score,
        risk_level=level_for(score).value,
        factors=factors,
        inputs=raw_lookup,
        unknown_factors=unknown,
    )

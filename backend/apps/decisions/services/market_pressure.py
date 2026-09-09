"""Freight Market Pressure Index (transparent, deterministic).

A single 0-100 index describing how TIGHT the freight market is (higher = more
pressure on rates = a chartererss market turning owners' way). It is a
rule-based weighted blend of independent signals, each normalized to a 0..1
"pressure" with documented references — NOT a machine-learning model and NOT a
forecast of the index itself.

Signals (each higher => more upward pressure on freight):
    vessel_supply        LOWER available supply => MORE pressure (inverted)
    cargo_demand         HIGHER demand => MORE pressure
    freight_volatility   HIGHER volatility => MORE pressure (uncertainty premium)
    port_congestion      HIGHER congestion ties up tonnage => MORE pressure
    ton_mile_demand      HIGHER ton-mile demand absorbs tonnage => MORE pressure
    bunker               HIGHER bunker prices push freight up => MORE pressure
    seasonality          a 0..1 seasonal pressure factor (e.g. monsoon/peak)

Only signals that are PROVIDED are counted; the weights of the available signals
are renormalized so missing data neither inflates nor deflates the index (the
missing signals are reported). The factor breakdown is returned in full so the
index is always explainable and auditable.

Classification bands (documented, on the 0..100 index):
    0-25   VERY_WEAK
    25-45  WEAK
    45-60  NEUTRAL
    60-75  TIGHT
    75-100 EXTREMELY_TIGHT
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Optional

Number = float


class PressureBand(str, Enum):
    VERY_WEAK = "VERY_WEAK"
    WEAK = "WEAK"
    NEUTRAL = "NEUTRAL"
    TIGHT = "TIGHT"
    EXTREMELY_TIGHT = "EXTREMELY_TIGHT"


# --- Factor weights (relative importance). Renormalized over available inputs.
WEIGHTS: dict[str, float] = {
    "vessel_supply": 0.22,      # tonnage availability is the core balance driver
    "cargo_demand": 0.22,       # the other side of the balance
    "ton_mile_demand": 0.16,    # ton-miles absorb effective supply
    "port_congestion": 0.14,    # congestion sequesters tonnage
    "freight_volatility": 0.12, # volatility => risk premium in rates
    "bunker": 0.08,             # fuel cost feeds into freight
    "seasonality": 0.06,        # calendar/peak effects
}

# --- Documented classification band thresholds on the 0..100 index. ---
BAND_VERY_WEAK = 25.0
BAND_WEAK = 45.0
BAND_NEUTRAL = 60.0
BAND_TIGHT = 75.0


class MarketPressureError(ValueError):
    """Raised for invalid market-pressure inputs."""


@dataclass
class MarketPressureInput:
    """Inputs for the index. Every field is an already-normalized 0..1 pressure
    signal EXCEPT vessel_supply which is a 0..1 availability (inverted inside).
    Any field left None is 'not available' and excluded from the weighting."""

    # 0..1 available-tonnage level (1 = abundant supply). Inverted to pressure.
    vessel_supply: Optional[Number] = None
    # 0..1 demand intensity (1 = very high demand).
    cargo_demand: Optional[Number] = None
    # 0..1 recent freight volatility (1 = extreme).
    freight_volatility: Optional[Number] = None
    # 0..100 destination/lane port congestion score (from the congestion engine).
    port_congestion: Optional[Number] = None
    # 0..1 ton-mile demand intensity proxy.
    ton_mile_demand: Optional[Number] = None
    # 0..1 bunker-price pressure (1 = very expensive fuel vs reference).
    bunker: Optional[Number] = None
    # 0..1 seasonal pressure factor.
    seasonality: Optional[Number] = None


@dataclass
class PressureFactor:
    factor: str
    raw_value: object
    normalized: float      # 0..1 pressure actually used
    weight: float          # renormalized weight actually used
    contribution: float    # weight * normalized * 100 (index points)
    available: bool
    note: str = ""


@dataclass
class MarketPressureResult:
    index: float                       # 0..100
    classification: str                # PressureBand value
    factors: list[PressureFactor]
    inputs: dict
    missing_factors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "index": self.index,
            "classification": self.classification,
            "factors": [asdict(f) for f in self.factors],
            "inputs": self.inputs,
            "missing_factors": self.missing_factors,
        }


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def classify(index: float) -> PressureBand:
    if index < BAND_VERY_WEAK:
        return PressureBand.VERY_WEAK
    if index < BAND_WEAK:
        return PressureBand.WEAK
    if index < BAND_NEUTRAL:
        return PressureBand.NEUTRAL
    if index < BAND_TIGHT:
        return PressureBand.TIGHT
    return PressureBand.EXTREMELY_TIGHT


def _normalized_signals(inp: MarketPressureInput) -> dict[str, tuple]:
    """Return {factor: (normalized_or_None, note)}. None => unavailable."""
    out: dict[str, tuple] = {}

    if inp.vessel_supply is None:
        out["vessel_supply"] = (None, "no vessel-supply signal")
    else:
        # Availability -> pressure is inverted: abundant supply => low pressure.
        out["vessel_supply"] = (
            _clamp01(1.0 - inp.vessel_supply),
            f"availability {inp.vessel_supply} -> pressure {1.0 - inp.vessel_supply:.2f}",
        )

    out["cargo_demand"] = (
        (_clamp01(inp.cargo_demand), f"demand {inp.cargo_demand}")
        if inp.cargo_demand is not None else (None, "no demand signal")
    )
    out["freight_volatility"] = (
        (_clamp01(inp.freight_volatility), f"volatility {inp.freight_volatility}")
        if inp.freight_volatility is not None else (None, "no volatility signal")
    )
    out["port_congestion"] = (
        (_clamp01(inp.port_congestion / 100.0), f"congestion {inp.port_congestion}/100")
        if inp.port_congestion is not None else (None, "no congestion signal")
    )
    out["ton_mile_demand"] = (
        (_clamp01(inp.ton_mile_demand), f"ton-mile {inp.ton_mile_demand}")
        if inp.ton_mile_demand is not None else (None, "no ton-mile signal")
    )
    out["bunker"] = (
        (_clamp01(inp.bunker), f"bunker pressure {inp.bunker}")
        if inp.bunker is not None else (None, "no bunker signal")
    )
    out["seasonality"] = (
        (_clamp01(inp.seasonality), f"seasonality {inp.seasonality}")
        if inp.seasonality is not None else (None, "no seasonality signal")
    )
    return out


def compute_market_pressure(inp: MarketPressureInput) -> MarketPressureResult:
    """Compute the deterministic Freight Market Pressure Index (0-100) with a
    full, explainable factor breakdown and its classification band."""
    signals = _normalized_signals(inp)

    raw_lookup = {
        "vessel_supply": inp.vessel_supply,
        "cargo_demand": inp.cargo_demand,
        "freight_volatility": inp.freight_volatility,
        "port_congestion": inp.port_congestion,
        "ton_mile_demand": inp.ton_mile_demand,
        "bunker": inp.bunker,
        "seasonality": inp.seasonality,
    }

    available = {k: v[0] for k, v in signals.items() if v[0] is not None}
    total_weight = sum(WEIGHTS[k] for k in available)

    factors: list[PressureFactor] = []
    missing: list[str] = []
    index = 0.0

    for factor in WEIGHTS:
        norm, note = signals[factor]
        if norm is None:
            missing.append(factor)
            factors.append(
                PressureFactor(factor, raw_lookup[factor], 0.0, 0.0, 0.0, False, note)
            )
            continue
        weight = WEIGHTS[factor] / total_weight if total_weight > 0 else 0.0
        contribution = weight * norm * 100.0
        index += contribution
        factors.append(
            PressureFactor(
                factor=factor,
                raw_value=raw_lookup[factor],
                normalized=round(norm, 4),
                weight=round(weight, 4),
                contribution=round(contribution, 2),
                available=True,
                note=note,
            )
        )

    index = round(index, 2)
    return MarketPressureResult(
        index=index,
        classification=classify(index).value,
        factors=factors,
        inputs=raw_lookup,
        missing_factors=missing,
    )

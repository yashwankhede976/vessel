"""Spot-vs-contract strategy comparison (transparent, deterministic).

Compares the four chartering strategies for covering a cargo requirement:

    SPOT           one-off fixture at today's spot rate
    SHORT_TERM     a short period/consecutive-voyage cover (weeks)
    MEDIUM_TERM    a medium period cover (months)
    MULTI_VOYAGE   a committed series of voyages

For each strategy it estimates the expected freight, freight volatility exposure,
flexibility, volume commitment, expected demurrage, a risk score, and a total
cost, then returns the lowest RISK-ADJUSTED cost strategy as the recommendation
with the expected saving vs the most expensive alternative and a plain-language
reason.

It is a rule-based comparator built on documented assumptions — NOT ML and NOT a
solver. The assumptions (period discounts, volatility exposure, risk weights) are
explicit constants so the comparison is reproducible and auditable. Longer
commitments trade a lower/again more stable rate for less flexibility; the engine
makes that trade-off transparent rather than hiding it in a single number.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

from .risk_engine import RiskInput, score_risk

MONEY_QUANT = Decimal("0.01")
DEFAULT_CURRENCY = "USD"

STRATEGIES = ["SPOT", "SHORT_TERM", "MEDIUM_TERM", "MULTI_VOYAGE"]

# --- Documented per-strategy assumptions -----------------------------------
# Freight multiplier applied to the spot rate: committing to a longer period
# typically fixes a rate at a modest discount to spot (owner accepts a lower
# rate for utilization certainty). These are transparent planning assumptions,
# NOT observed market data.
FREIGHT_MULTIPLIER = {
    "SPOT": 1.00,
    "SHORT_TERM": 0.98,
    "MEDIUM_TERM": 0.95,
    "MULTI_VOYAGE": 0.93,
}

# Fraction of the spot freight-rate volatility the charterer remains EXPOSED to.
# Spot is fully exposed; longer commitments lock the rate so exposure falls.
VOLATILITY_EXPOSURE = {
    "SPOT": 1.00,
    "SHORT_TERM": 0.60,
    "MEDIUM_TERM": 0.30,
    "MULTI_VOYAGE": 0.15,
}

# Flexibility (1 = fully flexible to re-decide each voyage). Inverse of commitment.
FLEXIBILITY = {
    "SPOT": 1.00,
    "SHORT_TERM": 0.70,
    "MEDIUM_TERM": 0.40,
    "MULTI_VOYAGE": 0.20,
}

# Volume commitment (0 = none, 1 = full-period committed).
VOLUME_COMMITMENT = {
    "SPOT": 0.0,
    "SHORT_TERM": 0.30,
    "MEDIUM_TERM": 0.60,
    "MULTI_VOYAGE": 1.0,
}

# Expected demurrage multiplier: spot fixtures carry more schedule risk (less
# planning, more waiting exposure); committed cover reduces it.
DEMURRAGE_MULTIPLIER = {
    "SPOT": 1.00,
    "SHORT_TERM": 0.90,
    "MEDIUM_TERM": 0.80,
    "MULTI_VOYAGE": 0.75,
}

# Risk-adjustment: the recommended strategy minimizes cost * (1 + RISK_AVERSION *
# risk_score). A documented, mild risk aversion so a slightly cheaper but much
# riskier strategy does not automatically win.
RISK_AVERSION = 0.25


class SpotVsContractError(ValueError):
    """Raised for invalid spot-vs-contract inputs."""


def _dec(v) -> Optional[Decimal]:
    if v is None:
        return None
    return v if isinstance(v, Decimal) else Decimal(str(v))


def _money(v: Decimal) -> Decimal:
    return v.quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)


@dataclass
class SpotVsContractInput:
    """Inputs for the comparison.

    spot_freight_per_tonne : current spot freight rate (currency/tonne).
    cargo_tonnes           : parcel size.
    freight_volatility     : 0..1 recent spot volatility (drives exposure/risk).
    base_demurrage_cost    : expected demurrage for a spot fixture (currency);
                             scaled per strategy. Optional.
    non_freight_cost       : per-strategy-invariant other costs (bunker/port/
                             handling) added to every strategy's total. Optional.
    congestion_score       : 0..100 destination congestion (feeds risk). Optional.
    """

    spot_freight_per_tonne: Decimal
    cargo_tonnes: Decimal
    freight_volatility: Optional[float] = None
    base_demurrage_cost: Optional[Decimal] = None
    non_freight_cost: Optional[Decimal] = None
    congestion_score: Optional[float] = None
    currency: str = DEFAULT_CURRENCY

    def __post_init__(self):
        self.spot_freight_per_tonne = _dec(self.spot_freight_per_tonne)
        self.cargo_tonnes = _dec(self.cargo_tonnes)
        self.base_demurrage_cost = _dec(self.base_demurrage_cost)
        self.non_freight_cost = _dec(self.non_freight_cost)


@dataclass
class StrategyOption:
    strategy: str
    expected_freight_per_tonne: Decimal
    expected_freight_cost: Decimal
    volatility_exposure: float
    flexibility: float
    volume_commitment: float
    expected_demurrage: Decimal
    total_cost: Decimal
    risk_score: float               # 0..100 from the risk engine
    risk_adjusted_cost: Decimal
    currency: str

    def to_dict(self) -> dict:
        return {
            "strategy": self.strategy,
            "expected_freight_per_tonne": str(self.expected_freight_per_tonne),
            "expected_freight_cost": str(self.expected_freight_cost),
            "volatility_exposure": self.volatility_exposure,
            "flexibility": self.flexibility,
            "volume_commitment": self.volume_commitment,
            "expected_demurrage": str(self.expected_demurrage),
            "total_cost": str(self.total_cost),
            "risk_score": self.risk_score,
            "risk_adjusted_cost": str(self.risk_adjusted_cost),
            "currency": self.currency,
        }


@dataclass
class SpotVsContractResult:
    recommended_strategy: str
    expected_cost: Decimal          # total cost of the recommended strategy
    expected_savings: Decimal       # vs the most expensive alternative (total)
    risk_score: float               # of the recommended strategy (0..100)
    reason: str
    options: list[StrategyOption]   # all strategies, cheapest risk-adjusted first
    currency: str

    def to_dict(self) -> dict:
        return {
            "recommended_strategy": self.recommended_strategy,
            "expected_cost": str(self.expected_cost),
            "expected_savings": str(self.expected_savings),
            "risk_score": self.risk_score,
            "reason": self.reason,
            "options": [o.to_dict() for o in self.options],
            "currency": self.currency,
        }


def _validate(inp: SpotVsContractInput) -> None:
    if inp.spot_freight_per_tonne is None or inp.spot_freight_per_tonne < 0:
        raise SpotVsContractError("spot_freight_per_tonne must be non-negative.")
    if inp.cargo_tonnes is None or inp.cargo_tonnes <= 0:
        raise SpotVsContractError("cargo_tonnes must be positive.")
    if inp.freight_volatility is not None and not (0.0 <= inp.freight_volatility <= 1.0):
        raise SpotVsContractError("freight_volatility must be within [0, 1].")


def compare_strategies(inp: SpotVsContractInput) -> SpotVsContractResult:
    """Compare the four strategies and recommend the lowest risk-adjusted cost."""
    _validate(inp)
    cur = inp.currency
    other = inp.non_freight_cost or Decimal("0")
    base_dem = inp.base_demurrage_cost or Decimal("0")

    options: list[StrategyOption] = []
    for strat in STRATEGIES:
        freight_pt = _money(inp.spot_freight_per_tonne * Decimal(str(FREIGHT_MULTIPLIER[strat])))
        freight_cost = _money(freight_pt * inp.cargo_tonnes)
        demurrage = _money(base_dem * Decimal(str(DEMURRAGE_MULTIPLIER[strat])))
        total = _money(freight_cost + demurrage + other)

        exposure = VOLATILITY_EXPOSURE[strat]
        # Residual freight-volatility risk after locking = exposure * volatility.
        residual_vol = (
            None if inp.freight_volatility is None
            else round(exposure * inp.freight_volatility, 4)
        )
        risk = score_risk(
            RiskInput(
                freight_volatility=residual_vol,
                port_congestion=inp.congestion_score,
                expected_demurrage_cost=float(demurrage) if demurrage else None,
            )
        )
        risk_adjusted = _money(
            total * (Decimal("1") + Decimal(str(RISK_AVERSION)) * Decimal(str(risk.overall_score / 100.0)))
        )

        options.append(
            StrategyOption(
                strategy=strat,
                expected_freight_per_tonne=freight_pt,
                expected_freight_cost=freight_cost,
                volatility_exposure=exposure,
                flexibility=FLEXIBILITY[strat],
                volume_commitment=VOLUME_COMMITMENT[strat],
                expected_demurrage=demurrage,
                total_cost=total,
                risk_score=risk.overall_score,
                risk_adjusted_cost=risk_adjusted,
                currency=cur,
            )
        )

    # Recommend the lowest RISK-ADJUSTED cost; deterministic tie-break by the
    # canonical strategy order.
    order = {s: i for i, s in enumerate(STRATEGIES)}
    options.sort(key=lambda o: (o.risk_adjusted_cost, order[o.strategy]))
    best = options[0]

    most_expensive_total = max(o.total_cost for o in options)
    savings = _money(most_expensive_total - best.total_cost)

    reason = _build_reason(best, options)

    return SpotVsContractResult(
        recommended_strategy=best.strategy,
        expected_cost=best.total_cost,
        expected_savings=savings,
        risk_score=best.risk_score,
        reason=reason,
        options=options,
        currency=cur,
    )


def _build_reason(best: StrategyOption, options: list[StrategyOption]) -> str:
    parts = [
        f"{best.strategy} has the lowest risk-adjusted cost "
        f"({best.risk_adjusted_cost} {best.currency}; total {best.total_cost})."
    ]
    if best.strategy == "SPOT":
        parts.append(
            "Spot keeps full flexibility but leaves full exposure to freight "
            "volatility."
        )
    else:
        parts.append(
            f"Committing ({best.strategy}) locks a rate ~"
            f"{round((1 - FREIGHT_MULTIPLIER[best.strategy]) * 100)}% under spot and "
            f"cuts freight-volatility exposure to "
            f"{int(VOLATILITY_EXPOSURE[best.strategy] * 100)}%, at the cost of "
            f"{int((1 - FLEXIBILITY[best.strategy]) * 100)}% less flexibility."
        )
    return " ".join(parts)

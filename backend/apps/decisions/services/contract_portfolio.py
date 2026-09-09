"""Contract portfolio construction (transparent, deterministic).

Given a multi-month cargo requirement, recommend a MIX of chartering strategies
(spot / short-term / medium-term / multi-voyage) rather than committing the whole
volume to one. The rationale is diversification: a base load is covered on
committed (cheaper, lower-volatility) contracts while a flexible tranche stays on
spot to retain optionality.

The allocation is a rule-based function of the market pressure and the volume /
horizon of the requirement — NOT a solver and NOT ML. The blend weights are
documented constants; the engine prices each tranche with the spot-vs-contract
engine and reports expected cost, the volatility (risk) reduction vs an all-spot
book, and the estimated saving vs an all-spot book.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

from .spot_vs_contract import FREIGHT_MULTIPLIER, VOLATILITY_EXPOSURE

MONEY_QUANT = Decimal("0.01")
DEFAULT_CURRENCY = "USD"

STRATEGIES = ["SPOT", "SHORT_TERM", "MEDIUM_TERM", "MULTI_VOYAGE"]

# --- Documented base allocation blends by market tightness ------------------
# Tighter markets -> commit MORE volume (lock rates before they rise). Looser
# markets -> keep MORE on spot (stay flexible, ride rates down). Each blend sums
# to 1.0 across the four strategies. These are transparent planning heuristics.
BLENDS = {
    # (spot, short, medium, multi)
    "loose":   (0.55, 0.25, 0.15, 0.05),   # market_pressure < LOOSE_MAX
    "neutral": (0.35, 0.30, 0.20, 0.15),
    "tight":   (0.20, 0.25, 0.30, 0.25),   # market_pressure >= TIGHT_MIN
}
LOOSE_MAX = 45.0   # market pressure index below this => "loose"
TIGHT_MIN = 60.0   # market pressure index at/above this => "tight"


class ContractPortfolioError(ValueError):
    """Raised for invalid contract-portfolio inputs."""


def _dec(v) -> Optional[Decimal]:
    if v is None:
        return None
    return v if isinstance(v, Decimal) else Decimal(str(v))


def _money(v: Decimal) -> Decimal:
    return v.quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)


@dataclass
class ContractPortfolioInput:
    total_tonnes: Decimal
    spot_freight_per_tonne: Decimal
    market_pressure_index: Optional[float] = None   # 0..100 (from MPI engine)
    freight_volatility: Optional[float] = None      # 0..1
    currency: str = DEFAULT_CURRENCY

    def __post_init__(self):
        self.total_tonnes = _dec(self.total_tonnes)
        self.spot_freight_per_tonne = _dec(self.spot_freight_per_tonne)


@dataclass
class PortfolioAllocation:
    strategy: str
    share: float                 # 0..1 of total volume
    tonnes: Decimal
    freight_per_tonne: Decimal
    cost: Decimal
    volatility_exposure: float

    def to_dict(self) -> dict:
        return {
            "strategy": self.strategy,
            "share": self.share,
            "tonnes": str(self.tonnes),
            "freight_per_tonne": str(self.freight_per_tonne),
            "cost": str(self.cost),
            "volatility_exposure": self.volatility_exposure,
        }


@dataclass
class ContractPortfolioResult:
    regime: str                          # loose | neutral | tight
    allocations: list[PortfolioAllocation]
    expected_cost: Decimal               # blended freight cost of the portfolio
    all_spot_cost: Decimal               # baseline: whole volume on spot
    estimated_savings: Decimal           # all_spot_cost - expected_cost
    risk_reduction: float                # 0..1 reduction in volatility exposure
    currency: str
    reason: str

    def to_dict(self) -> dict:
        return {
            "regime": self.regime,
            "allocations": [a.to_dict() for a in self.allocations],
            "expected_cost": str(self.expected_cost),
            "all_spot_cost": str(self.all_spot_cost),
            "estimated_savings": str(self.estimated_savings),
            "risk_reduction": self.risk_reduction,
            "currency": self.currency,
            "reason": self.reason,
        }


def _regime(mpi: Optional[float]) -> str:
    if mpi is None:
        return "neutral"
    if mpi < LOOSE_MAX:
        return "loose"
    if mpi >= TIGHT_MIN:
        return "tight"
    return "neutral"


def build_portfolio(inp: ContractPortfolioInput) -> ContractPortfolioResult:
    """Recommend a diversified contract mix for a multi-month requirement."""
    if inp.total_tonnes is None or inp.total_tonnes <= 0:
        raise ContractPortfolioError("total_tonnes must be positive.")
    if inp.spot_freight_per_tonne is None or inp.spot_freight_per_tonne < 0:
        raise ContractPortfolioError("spot_freight_per_tonne must be non-negative.")

    regime = _regime(inp.market_pressure_index)
    blend = BLENDS[regime]
    cur = inp.currency

    allocations: list[PortfolioAllocation] = []
    portfolio_cost = Decimal("0")
    # Weighted residual volatility exposure of the portfolio.
    portfolio_exposure = 0.0
    allocated = Decimal("0")

    for i, strat in enumerate(STRATEGIES):
        share = blend[i]
        # Assign remaining tonnage to the last strategy to avoid rounding drift.
        if i == len(STRATEGIES) - 1:
            tonnes = _money(inp.total_tonnes - allocated)
        else:
            tonnes = _money(inp.total_tonnes * Decimal(str(share)))
            allocated += tonnes
        freight_pt = _money(inp.spot_freight_per_tonne * Decimal(str(FREIGHT_MULTIPLIER[strat])))
        cost = _money(freight_pt * tonnes)
        portfolio_cost += cost
        portfolio_exposure += share * VOLATILITY_EXPOSURE[strat]
        allocations.append(
            PortfolioAllocation(
                strategy=strat,
                share=round(share, 4),
                tonnes=tonnes,
                freight_per_tonne=freight_pt,
                cost=cost,
                volatility_exposure=VOLATILITY_EXPOSURE[strat],
            )
        )

    portfolio_cost = _money(portfolio_cost)
    all_spot_cost = _money(inp.spot_freight_per_tonne * inp.total_tonnes)
    savings = _money(all_spot_cost - portfolio_cost)
    # All-spot exposure is 1.0 by definition; reduction is 1 - portfolio exposure.
    risk_reduction = round(1.0 - portfolio_exposure, 4)

    reason = (
        f"Market regime '{regime}' (pressure index "
        f"{inp.market_pressure_index if inp.market_pressure_index is not None else 'n/a'}). "
        f"Committing {int((1 - blend[0]) * 100)}% of volume across term contracts "
        f"locks cheaper rates and cuts freight-volatility exposure to "
        f"{round(portfolio_exposure * 100)}% of an all-spot book, while keeping "
        f"{int(blend[0] * 100)}% on spot for flexibility."
    )

    return ContractPortfolioResult(
        regime=regime,
        allocations=allocations,
        expected_cost=portfolio_cost,
        all_spot_cost=all_spot_cost,
        estimated_savings=savings,
        risk_reduction=risk_reduction,
        currency=cur,
        reason=reason,
    )

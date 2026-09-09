"""Deterministic total landed-cost engine.

Computes the all-in delivered cost of a cargo for a given origin -> destination:

    commodity + freight + bunker + port charges + handling + demurrage
    + insurance/other  (each converted to a common currency via FX)

and returns the total landed cost and the landed cost per tonne, with an
itemized breakdown. Every financial value carries its currency and unit, so no
number is ambiguous.

It also supports COMPARING origins for a selected destination (the five project
origins: Australia, Indonesia, Mozambique, USA, Russia) — returning each
origin's landed cost sorted cheapest-first with the delta vs the cheapest.

This is a transparent calculator, NOT an optimizer: it does not choose an origin
or recommend one, it only computes and compares. No ML.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

MONEY_QUANT = Decimal("0.01")
RATE_QUANT = Decimal("0.0001")
DEFAULT_CURRENCY = "USD"

# The project origins that may be compared for a destination.
PROJECT_ORIGINS = ["Australia", "Indonesia", "Mozambique", "USA", "Russia"]

# Landed-cost components, in canonical order.
COMPONENT_FIELDS = [
    "commodity_cost",
    "freight_cost",
    "bunker_cost",
    "port_charges",
    "handling_cost",
    "demurrage_cost",
    "insurance_other_cost",
]


class LandedCostError(ValueError):
    """Raised for invalid landed-cost inputs (bad cargo, missing FX rate, etc.)."""


def _dec(value) -> Optional[Decimal]:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _money(value: Decimal) -> Decimal:
    return value.quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)


@dataclass
class Money:
    """A financial value that always carries its currency and unit."""

    amount: Decimal
    currency: str
    unit: str  # "total" | "per_tonne"

    def to_dict(self) -> dict:
        return {"amount": str(self.amount), "currency": self.currency, "unit": self.unit}


@dataclass
class CostComponent:
    """A single cost component in its ORIGINAL (source) currency.

    amount is in `currency`; the engine converts it to the target currency using
    the supplied FX rates. A component whose amount is None is 'not provided' and
    contributes zero (recorded as such in the breakdown).
    """

    amount: Optional[Decimal]
    currency: str = DEFAULT_CURRENCY

    def __post_init__(self):
        self.amount = _dec(self.amount)


@dataclass
class LandedCostInput:
    """Inputs for one origin->destination landed-cost calculation."""

    origin: str
    destination: str
    cargo_tonnes: Decimal

    commodity_cost: Optional[CostComponent] = None
    freight_cost: Optional[CostComponent] = None
    bunker_cost: Optional[CostComponent] = None
    port_charges: Optional[CostComponent] = None
    handling_cost: Optional[CostComponent] = None
    demurrage_cost: Optional[CostComponent] = None
    insurance_other_cost: Optional[CostComponent] = None

    # Target currency all components are converted into, and the FX rate map
    # (source_currency -> units of target per 1 source). The target->target rate
    # defaults to 1 and does not need to be supplied.
    target_currency: str = DEFAULT_CURRENCY
    fx_rates: dict = field(default_factory=dict)

    def __post_init__(self):
        self.cargo_tonnes = _dec(self.cargo_tonnes)


@dataclass
class LandedCostResult:
    origin: str
    destination: str
    currency: str
    cargo_tonnes: Decimal
    components: dict                 # name -> Money (converted, "total")
    total_landed_cost: Money
    landed_cost_per_tonne: Optional[Money]
    fx_rates_used: dict
    missing_components: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "origin": self.origin,
            "destination": self.destination,
            "currency": self.currency,
            "cargo_tonnes": str(self.cargo_tonnes),
            "components": {k: v.to_dict() for k, v in self.components.items()},
            "total_landed_cost": self.total_landed_cost.to_dict(),
            "landed_cost_per_tonne": (
                self.landed_cost_per_tonne.to_dict()
                if self.landed_cost_per_tonne else None
            ),
            "fx_rates_used": {k: str(v) for k, v in self.fx_rates_used.items()},
            "missing_components": self.missing_components,
        }


def _fx_rate(source_currency: str, target_currency: str, fx_rates: dict) -> Decimal:
    """Return the FX rate to convert `source_currency` into `target_currency`.

    Same currency -> 1. Otherwise the rate must be present in fx_rates (keyed by
    source currency). A missing rate is an error (we never guess an FX rate).
    """
    if source_currency == target_currency:
        return Decimal("1")
    if source_currency in fx_rates:
        return _dec(fx_rates[source_currency])
    raise LandedCostError(
        f"Missing FX rate for {source_currency}->{target_currency}; provide it "
        "in fx_rates. FX rates are never assumed."
    )


def _validate(inp: LandedCostInput) -> None:
    if inp.cargo_tonnes is None or inp.cargo_tonnes <= 0:
        raise LandedCostError("cargo_tonnes must be positive.")
    for name in COMPONENT_FIELDS:
        comp: Optional[CostComponent] = getattr(inp, name)
        if comp is not None and comp.amount is not None and comp.amount < 0:
            raise LandedCostError(f"{name} cannot be negative.")


def compute_landed_cost(inp: LandedCostInput) -> LandedCostResult:
    """Compute the itemized total landed cost + per-tonne, converting every
    component into the target currency via the supplied FX rates."""
    _validate(inp)
    target = inp.target_currency

    components: dict[str, Money] = {}
    missing: list[str] = []
    fx_used: dict[str, Decimal] = {}
    total = Decimal("0")

    for name in COMPONENT_FIELDS:
        comp: Optional[CostComponent] = getattr(inp, name)
        if comp is None or comp.amount is None:
            missing.append(name)
            components[name] = Money(_money(Decimal("0")), target, "total")
            continue
        rate = _fx_rate(comp.currency, target, inp.fx_rates)
        if comp.currency != target:
            fx_used[comp.currency] = rate
        converted = _money(comp.amount * rate)
        components[name] = Money(converted, target, "total")
        total += converted

    total = _money(total)
    total_money = Money(total, target, "total")

    per_tonne = (
        Money(_money(total / inp.cargo_tonnes), target, "per_tonne")
        if inp.cargo_tonnes and inp.cargo_tonnes > 0 else None
    )

    return LandedCostResult(
        origin=inp.origin,
        destination=inp.destination,
        currency=target,
        cargo_tonnes=inp.cargo_tonnes,
        components=components,
        total_landed_cost=total_money,
        landed_cost_per_tonne=per_tonne,
        fx_rates_used=fx_used,
        missing_components=missing,
    )


# ---------------------------------------------------------------------------
# Multi-origin comparison for a selected destination (comparison only).
# ---------------------------------------------------------------------------
@dataclass
class OriginComparisonEntry:
    origin: str
    total_landed_cost: Money
    landed_cost_per_tonne: Optional[Money]
    delta_vs_cheapest: Money        # total-cost difference vs the cheapest origin
    is_cheapest: bool
    result: dict                    # full LandedCostResult.to_dict for this origin

    def to_dict(self) -> dict:
        return {
            "origin": self.origin,
            "total_landed_cost": self.total_landed_cost.to_dict(),
            "landed_cost_per_tonne": (
                self.landed_cost_per_tonne.to_dict()
                if self.landed_cost_per_tonne else None
            ),
            "delta_vs_cheapest": self.delta_vs_cheapest.to_dict(),
            "is_cheapest": self.is_cheapest,
            "result": self.result,
        }


@dataclass
class OriginComparison:
    destination: str
    currency: str
    entries: list[OriginComparisonEntry]   # sorted cheapest-first

    def to_dict(self) -> dict:
        return {
            "destination": self.destination,
            "currency": self.currency,
            "entries": [e.to_dict() for e in self.entries],
        }


def compare_origins(inputs: list[LandedCostInput]) -> OriginComparison:
    """Compute landed cost for several origins into the SAME destination and
    return them sorted cheapest-first with the delta vs the cheapest.

    This is a comparison, not an optimization: it does not pick a "winner" or
    make a recommendation — it simply computes and orders the figures so a user
    can compare. All inputs must share the same destination and target currency.
    """
    if not inputs:
        raise LandedCostError("compare_origins requires at least one input.")

    destination = inputs[0].destination
    target = inputs[0].target_currency
    for inp in inputs:
        if inp.destination != destination:
            raise LandedCostError(
                "All inputs must share the same destination to be comparable."
            )
        if inp.target_currency != target:
            raise LandedCostError(
                "All inputs must use the same target currency to be comparable."
            )

    results = [compute_landed_cost(inp) for inp in inputs]
    results.sort(key=lambda r: r.total_landed_cost.amount)

    cheapest_total = results[0].total_landed_cost.amount

    entries: list[OriginComparisonEntry] = []
    for i, r in enumerate(results):
        delta = _money(r.total_landed_cost.amount - cheapest_total)
        entries.append(
            OriginComparisonEntry(
                origin=r.origin,
                total_landed_cost=r.total_landed_cost,
                landed_cost_per_tonne=r.landed_cost_per_tonne,
                delta_vs_cheapest=Money(delta, target, "total"),
                is_cheapest=(i == 0),
                result=r.to_dict(),
            )
        )

    return OriginComparison(destination=destination, currency=target, entries=entries)

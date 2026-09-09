"""Deterministic voyage economics engine.

A transparent, rule-based cost model for a single voyage — NOT a procurement
optimizer and NOT an ML model. Given the physical voyage parameters and the
relevant unit prices/costs, it computes an itemized cost breakdown and the key
per-unit metrics.

Every financial value is a Decimal and is returned WITH its currency and unit,
so no number is ambiguous (see `Money`). Costs are summed exactly; per-unit
metrics are derived from the total.

This module computes economics for ONE given voyage configuration. Choosing the
best origin/port/vessel (procurement optimization) is explicitly out of scope.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

# Conversion + rounding constants.
NM_TO_KM = Decimal("1.852")           # 1 nautical mile = 1.852 km
HOURS_PER_DAY = Decimal("24")
MONEY_QUANT = Decimal("0.01")         # currency rounded to 2 dp
RATE_QUANT = Decimal("0.0001")        # per-unit rates kept to 4 dp
HOURS_QUANT = Decimal("0.01")

DEFAULT_CURRENCY = "USD"


class VoyageEconomicsError(ValueError):
    """Raised for impossible/invalid voyage inputs."""


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
    unit: str  # e.g. "total", "per_tonne", "per_day", "per_tonne_km"

    def to_dict(self) -> dict:
        return {"amount": str(self.amount), "currency": self.currency, "unit": self.unit}


@dataclass
class VoyageEconomicsInput:
    """Inputs for a single voyage's economics.

    Physical:
      distance_nm            : voyage distance (nautical miles)
      speed_kn               : average sailing speed (knots)
      cargo_tonnes           : cargo carried (tonnes) — basis for per-tonne cost
      port_days              : days spent in port(s) (loading + discharge), optional

    Bunkers:
      bunker_rate_tpd        : fuel burned per SAILING day (tonnes/day)
      bunker_idle_rate_tpd   : fuel burned per PORT day (tonnes/day), optional
      bunker_price_per_tonne : fuel price (currency/tonne)

    Direct costs (currency, all optional; default 0):
      port_cost              : total port charges
      freight_cost           : freight/hire cost for the voyage. Alternatively
                               provide freight_rate_per_tonne (x cargo_tonnes).
      freight_rate_per_tonne : per-tonne freight rate (used if freight_cost None)
      canal_cost             : canal/route tolls where applicable
      misc_cost              : miscellaneous voyage costs

    Demurrage (estimated, NOT a full demurrage calc):
      demurrage_rate_per_day : agreed demurrage rate (currency/day)
      expected_demurrage_days: expected days on demurrage
      OR estimated_demurrage : a precomputed demurrage figure (currency)

    currency applies to all monetary values.
    """

    distance_nm: Decimal
    speed_kn: Decimal
    cargo_tonnes: Decimal

    bunker_rate_tpd: Decimal = Decimal("0")
    bunker_price_per_tonne: Decimal = Decimal("0")
    bunker_idle_rate_tpd: Optional[Decimal] = None
    port_days: Decimal = Decimal("0")

    port_cost: Decimal = Decimal("0")
    freight_cost: Optional[Decimal] = None
    freight_rate_per_tonne: Optional[Decimal] = None
    canal_cost: Decimal = Decimal("0")
    misc_cost: Decimal = Decimal("0")

    demurrage_rate_per_day: Optional[Decimal] = None
    expected_demurrage_days: Optional[Decimal] = None
    estimated_demurrage: Optional[Decimal] = None

    currency: str = DEFAULT_CURRENCY

    def __post_init__(self):
        # Coerce numerics to Decimal for exactness.
        for f in (
            "distance_nm", "speed_kn", "cargo_tonnes", "bunker_rate_tpd",
            "bunker_price_per_tonne", "bunker_idle_rate_tpd", "port_days",
            "port_cost", "freight_cost", "freight_rate_per_tonne", "canal_cost",
            "misc_cost", "demurrage_rate_per_day", "expected_demurrage_days",
            "estimated_demurrage",
        ):
            setattr(self, f, _dec(getattr(self, f)))


@dataclass
class VoyageEconomicsResult:
    currency: str
    # Physical.
    distance_nm: Decimal
    distance_km: Decimal
    sailing_days: Decimal
    port_days: Decimal
    total_days: Decimal
    cargo_tonnes: Decimal
    bunker_consumption_tonnes: Decimal
    # Itemized costs (Money, all in `currency`).
    cost_components: dict            # name -> Money
    total_voyage_cost: Money
    # Per-unit metrics (Money with explicit unit).
    cost_per_tonne: Optional[Money]
    cost_per_day: Optional[Money]
    cost_per_tonne_km: Optional[Money]
    inputs: dict

    def to_dict(self) -> dict:
        return {
            "currency": self.currency,
            "distance_nm": str(self.distance_nm),
            "distance_km": str(self.distance_km),
            "sailing_days": str(self.sailing_days),
            "port_days": str(self.port_days),
            "total_days": str(self.total_days),
            "cargo_tonnes": str(self.cargo_tonnes),
            "bunker_consumption_tonnes": str(self.bunker_consumption_tonnes),
            "cost_components": {k: v.to_dict() for k, v in self.cost_components.items()},
            "total_voyage_cost": self.total_voyage_cost.to_dict(),
            "cost_per_tonne": self.cost_per_tonne.to_dict() if self.cost_per_tonne else None,
            "cost_per_day": self.cost_per_day.to_dict() if self.cost_per_day else None,
            "cost_per_tonne_km": self.cost_per_tonne_km.to_dict() if self.cost_per_tonne_km else None,
            "inputs": self.inputs,
        }


def _validate(inp: VoyageEconomicsInput) -> None:
    if inp.distance_nm is None or inp.distance_nm <= 0:
        raise VoyageEconomicsError("distance_nm must be positive.")
    if inp.speed_kn is None or inp.speed_kn <= 0:
        raise VoyageEconomicsError("speed_kn must be positive.")
    if inp.cargo_tonnes is None or inp.cargo_tonnes < 0:
        raise VoyageEconomicsError("cargo_tonnes cannot be negative.")
    for name in ("bunker_rate_tpd", "bunker_price_per_tonne", "port_days",
                 "port_cost", "canal_cost", "misc_cost"):
        v = getattr(inp, name)
        if v is not None and v < 0:
            raise VoyageEconomicsError(f"{name} cannot be negative.")


def compute_voyage_economics(inp: VoyageEconomicsInput) -> VoyageEconomicsResult:
    """Compute the itemized voyage cost and per-unit metrics deterministically."""
    _validate(inp)
    cur = inp.currency

    # --- physical: duration + distance ---
    sailing_hours = (inp.distance_nm / inp.speed_kn)
    sailing_days = (sailing_hours / HOURS_PER_DAY).quantize(HOURS_QUANT)
    port_days = (inp.port_days or Decimal("0")).quantize(HOURS_QUANT)
    total_days = (sailing_days + port_days).quantize(HOURS_QUANT)
    distance_km = (inp.distance_nm * NM_TO_KM).quantize(MONEY_QUANT)

    # --- bunkers: consumption then cost ---
    idle_rate = inp.bunker_idle_rate_tpd if inp.bunker_idle_rate_tpd is not None else Decimal("0")
    sailing_consumption = inp.bunker_rate_tpd * sailing_days
    idle_consumption = idle_rate * port_days
    bunker_consumption = (sailing_consumption + idle_consumption)
    bunker_cost = _money(bunker_consumption * inp.bunker_price_per_tonne)

    # --- freight: explicit cost, else rate * tonnes ---
    if inp.freight_cost is not None:
        freight_cost = _money(inp.freight_cost)
    elif inp.freight_rate_per_tonne is not None:
        freight_cost = _money(inp.freight_rate_per_tonne * inp.cargo_tonnes)
    else:
        freight_cost = _money(Decimal("0"))

    # --- estimated demurrage: explicit, else rate * expected days ---
    if inp.estimated_demurrage is not None:
        demurrage = _money(inp.estimated_demurrage)
    elif inp.demurrage_rate_per_day is not None and inp.expected_demurrage_days is not None:
        demurrage = _money(inp.demurrage_rate_per_day * inp.expected_demurrage_days)
    else:
        demurrage = _money(Decimal("0"))

    port_cost = _money(inp.port_cost or Decimal("0"))
    canal_cost = _money(inp.canal_cost or Decimal("0"))
    misc_cost = _money(inp.misc_cost or Decimal("0"))

    # --- itemized components (every one labelled with currency + unit) ---
    components = {
        "bunker_cost": Money(bunker_cost, cur, "total"),
        "port_cost": Money(port_cost, cur, "total"),
        "freight_cost": Money(freight_cost, cur, "total"),
        "canal_cost": Money(canal_cost, cur, "total"),
        "estimated_demurrage": Money(demurrage, cur, "total"),
        "misc_cost": Money(misc_cost, cur, "total"),
    }

    total = _money(
        bunker_cost + port_cost + freight_cost + canal_cost + demurrage + misc_cost
    )
    total_money = Money(total, cur, "total")

    # --- per-unit metrics (guard against divide-by-zero) ---
    cost_per_tonne = (
        Money(_money(total / inp.cargo_tonnes), cur, "per_tonne")
        if inp.cargo_tonnes and inp.cargo_tonnes > 0 else None
    )
    cost_per_day = (
        Money(_money(total / total_days), cur, "per_day")
        if total_days and total_days > 0 else None
    )
    # tonne-km uses km (nm converted). Only when cargo and distance are positive.
    tonne_km = inp.cargo_tonnes * distance_km
    cost_per_tonne_km = (
        Money(
            (total / tonne_km).quantize(RATE_QUANT, rounding=ROUND_HALF_UP),
            cur, "per_tonne_km",
        )
        if tonne_km and tonne_km > 0 else None
    )

    return VoyageEconomicsResult(
        currency=cur,
        distance_nm=inp.distance_nm,
        distance_km=distance_km,
        sailing_days=sailing_days,
        port_days=port_days,
        total_days=total_days,
        cargo_tonnes=inp.cargo_tonnes,
        bunker_consumption_tonnes=bunker_consumption.quantize(RATE_QUANT),
        cost_components=components,
        total_voyage_cost=total_money,
        cost_per_tonne=cost_per_tonne,
        cost_per_day=cost_per_day,
        cost_per_tonne_km=cost_per_tonne_km,
        inputs={
            k: (str(v) if isinstance(v, Decimal) else v)
            for k, v in asdict(inp).items()
        },
    )

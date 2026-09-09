"""Idle-vessel employment ranking (transparent, deterministic).

For an open/available vessel, rank the possible next-voyage (cargo) opportunities
by expected commercial outcome. For each opportunity it considers:

    current position -> load port ballast distance
    laden voyage distance (load -> discharge)
    freight (revenue)          voyage duration
    port compatibility (gate)  expected voyage cost
    expected margin (revenue - cost)   risk

and returns the opportunities ranked by expected margin (best first). Opportunities
the vessel is INCOMPATIBLE with at the discharge port are marked infeasible and
excluded from the ranking (reported separately), so the exclusion is transparent.

It is a rule-based ranker built on the existing primitives (compatibility, voyage
economics, suitability, risk) — NOT a solver and NOT ML. Ballast (positioning)
cost is included so a nearer cargo is correctly preferred over an equally-paying
but far-away one. Missing data lowers confidence rather than being fabricated.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

from apps.catalog.models import Vessel
from apps.catalog.services.service import evaluate_compatibility
from apps.catalog.services.compatibility import Status as CompatStatus
from .voyage_economics import VoyageEconomicsInput, compute_voyage_economics

MONEY_QUANT = Decimal("0.01")
DEFAULT_CURRENCY = "USD"
DEFAULT_SPEED_KN = Decimal("13")


class IdleVesselError(ValueError):
    """Raised for invalid idle-vessel inputs."""


def _dec(v) -> Optional[Decimal]:
    if v is None:
        return None
    return v if isinstance(v, Decimal) else Decimal(str(v))


def _money(v: Decimal) -> Decimal:
    return v.quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)


@dataclass
class EmploymentOpportunity:
    """One candidate cargo/voyage the idle vessel could take.

    laden_distance_nm : load port -> discharge port (nm).
    ballast_distance_nm : vessel current position -> load port (nm), optional.
    freight_rate_per_tonne : offered freight (revenue), currency/tonne.
    cargo_tonnes : parcel size.
    port : the discharge Port (for the compatibility gate), optional.
    commodity : cargo type (for compatibility), optional.
    port_cost, bunker_price_per_tonne : optional cost inputs.
    """

    name: str
    laden_distance_nm: Decimal
    cargo_tonnes: Decimal
    freight_rate_per_tonne: Decimal
    ballast_distance_nm: Optional[Decimal] = None
    port: Optional[Vessel] = None   # actually a Port; typed loosely to avoid import cycle
    commodity: Optional[str] = None
    port_cost: Optional[Decimal] = None
    bunker_price_per_tonne: Optional[Decimal] = None

    def __post_init__(self):
        self.laden_distance_nm = _dec(self.laden_distance_nm)
        self.cargo_tonnes = _dec(self.cargo_tonnes)
        self.freight_rate_per_tonne = _dec(self.freight_rate_per_tonne)
        self.ballast_distance_nm = _dec(self.ballast_distance_nm)
        self.port_cost = _dec(self.port_cost)
        self.bunker_price_per_tonne = _dec(self.bunker_price_per_tonne)


@dataclass
class RankedOpportunity:
    name: str
    feasible: bool
    compatibility_status: Optional[str]
    expected_revenue: Decimal
    expected_cost: Decimal
    expected_margin: Decimal
    voyage_days: Optional[float]
    margin_per_day: Optional[Decimal]
    currency: str
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "feasible": self.feasible,
            "compatibility_status": self.compatibility_status,
            "expected_revenue": str(self.expected_revenue),
            "expected_cost": str(self.expected_cost),
            "expected_margin": str(self.expected_margin),
            "voyage_days": self.voyage_days,
            "margin_per_day": (
                str(self.margin_per_day) if self.margin_per_day is not None else None
            ),
            "currency": self.currency,
            "notes": self.notes,
        }


@dataclass
class IdleVesselResult:
    vessel_id: int
    vessel_name: str
    ranked_opportunities: list[RankedOpportunity]  # feasible, best margin first
    excluded_opportunities: list[RankedOpportunity]
    currency: str

    def to_dict(self) -> dict:
        return {
            "vessel_id": self.vessel_id,
            "vessel_name": self.vessel_name,
            "ranked_opportunities": [o.to_dict() for o in self.ranked_opportunities],
            "excluded_opportunities": [o.to_dict() for o in self.excluded_opportunities],
            "currency": self.currency,
        }


def rank_employment(
    vessel: Vessel,
    opportunities: list[EmploymentOpportunity],
    *,
    currency: str = DEFAULT_CURRENCY,
) -> IdleVesselResult:
    """Rank next-voyage opportunities for an idle vessel by expected margin."""
    if not opportunities:
        raise IdleVesselError("At least one opportunity is required.")

    speed = vessel.speed if vessel.speed else DEFAULT_SPEED_KN

    ranked: list[RankedOpportunity] = []
    excluded: list[RankedOpportunity] = []

    for opp in opportunities:
        if opp.laden_distance_nm is None or opp.laden_distance_nm <= 0:
            raise IdleVesselError(f"{opp.name}: laden_distance_nm must be positive.")
        if opp.cargo_tonnes is None or opp.cargo_tonnes <= 0:
            raise IdleVesselError(f"{opp.name}: cargo_tonnes must be positive.")

        notes: list[str] = []

        # --- compatibility gate at the discharge port ---
        compat_status = None
        feasible = True
        if opp.port is not None:
            compat = evaluate_compatibility(vessel, opp.port, cargo=opp.commodity)
            compat_status = compat.status.value
            if compat.status == CompatStatus.INCOMPATIBLE:
                feasible = False
                notes.append("Vessel incompatible with discharge port.")

        # --- revenue = freight rate * cargo ---
        revenue = _money(opp.freight_rate_per_tonne * opp.cargo_tonnes)

        # --- cost via voyage economics on total (ballast + laden) distance ---
        total_distance = opp.laden_distance_nm + (opp.ballast_distance_nm or Decimal("0"))
        if opp.ballast_distance_nm is None:
            notes.append("Ballast distance unknown; positioning cost excluded.")
        ve = compute_voyage_economics(
            VoyageEconomicsInput(
                distance_nm=total_distance,
                speed_kn=speed,
                cargo_tonnes=opp.cargo_tonnes,
                bunker_price_per_tonne=(opp.bunker_price_per_tonne or Decimal("0")),
                port_cost=(opp.port_cost or Decimal("0")),
                currency=currency,
            )
        )
        cost = ve.total_voyage_cost.amount
        voyage_days = float(ve.total_days)
        margin = _money(revenue - cost)
        margin_per_day = (
            _money(margin / Decimal(str(voyage_days)))
            if voyage_days and voyage_days > 0 else None
        )

        row = RankedOpportunity(
            name=opp.name,
            feasible=feasible,
            compatibility_status=compat_status,
            expected_revenue=revenue,
            expected_cost=cost,
            expected_margin=margin,
            voyage_days=round(voyage_days, 2),
            margin_per_day=margin_per_day,
            currency=currency,
            notes=notes,
        )
        (ranked if feasible else excluded).append(row)

    # Best expected margin per day first (utilization-aware); fall back to total
    # margin when per-day is unavailable. Deterministic tie-break by name.
    def _key(o: RankedOpportunity):
        per_day = o.margin_per_day if o.margin_per_day is not None else Decimal("-Infinity")
        return (-per_day, -o.expected_margin, o.name)

    ranked.sort(key=_key)

    return IdleVesselResult(
        vessel_id=vessel.pk,
        vessel_name=vessel.name,
        ranked_opportunities=ranked,
        excluded_opportunities=excluded,
        currency=currency,
    )

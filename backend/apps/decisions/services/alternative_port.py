"""Alternative destination-port comparison (transparent, deterministic).

When a requested East Coast India destination is congested or infeasible for a
vessel, this compares the alternative East Coast ports on the factors that drive
delivered cost and schedule:

    freight (route distance proxy)  port cost   expected waiting
    demurrage (from waiting)        vessel compatibility   weather   time

and returns the recommended port (lowest total delivered cost among FEASIBLE
alternatives), the ranked alternatives, and the cost/time difference vs the
requested port with a plain-language reason.

It is a rule-based COMPARATOR built on the existing primitives (compatibility,
congestion, voyage economics) — NOT a solver and NOT ML. Ports the vessel is
INCOMPATIBLE with are marked infeasible and never recommended. Missing data
lowers a port's confidence rather than being fabricated.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

from apps.catalog.models import Port, Route, Vessel
from apps.catalog.services.service import evaluate_compatibility
from apps.catalog.services.compatibility import Status as CompatStatus
from apps.operations.services.congestion_service import score_port_congestion
from apps.operations.services.congestion_forecast import WAIT_DAYS_AT_MAX_SCORE
from .voyage_economics import VoyageEconomicsInput, compute_voyage_economics

MONEY_QUANT = Decimal("0.01")
DEFAULT_CURRENCY = "USD"

# Assumed sailing speed (kn) when a vessel speed isn't supplied (planning proxy).
DEFAULT_SPEED_KN = Decimal("13")


class AlternativePortError(ValueError):
    """Raised for invalid alternative-port inputs."""


def _dec(v) -> Optional[Decimal]:
    if v is None:
        return None
    return v if isinstance(v, Decimal) else Decimal(str(v))


def _money(v: Decimal) -> Decimal:
    return v.quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)


@dataclass
class PortComparisonEntry:
    port_id: int
    port_name: str
    feasible: bool
    compatibility_status: Optional[str]
    congestion_score: Optional[float]
    expected_waiting_days: Optional[float]
    distance_nm: Optional[float]
    total_cost: Optional[Decimal]        # delivered voyage cost (currency)
    estimated_days: Optional[float]      # sailing + waiting (days)
    currency: str
    is_requested: bool
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "port_id": self.port_id,
            "port_name": self.port_name,
            "feasible": self.feasible,
            "compatibility_status": self.compatibility_status,
            "congestion_score": self.congestion_score,
            "expected_waiting_days": self.expected_waiting_days,
            "distance_nm": self.distance_nm,
            "total_cost": str(self.total_cost) if self.total_cost is not None else None,
            "estimated_days": self.estimated_days,
            "currency": self.currency,
            "is_requested": self.is_requested,
            "notes": self.notes,
        }


@dataclass
class AlternativePortResult:
    requested_port: str
    recommended_port: Optional[str]
    alternative_ports: list[PortComparisonEntry]   # ranked, cheapest feasible first
    cost_difference: Optional[Decimal]             # recommended - requested (total)
    time_difference: Optional[float]               # recommended - requested (days)
    currency: str
    reason: str

    def to_dict(self) -> dict:
        return {
            "requested_port": self.requested_port,
            "recommended_port": self.recommended_port,
            "alternative_ports": [p.to_dict() for p in self.alternative_ports],
            "cost_difference": (
                str(self.cost_difference) if self.cost_difference is not None else None
            ),
            "time_difference": self.time_difference,
            "currency": self.currency,
            "reason": self.reason,
        }


def _resolve_route(origin_name: str, port: Port) -> Optional[Route]:
    return (
        Route.objects.select_related("origin", "destination_port")
        .filter(origin__name__iexact=origin_name.strip(), destination_port=port)
        .first()
    )


def _evaluate_port(
    port: Port,
    *,
    origin_name: str,
    vessel: Optional[Vessel],
    cargo_tonnes: Decimal,
    commodity: str,
    bunker_price_per_tonne: Optional[Decimal],
    freight_rate_per_tonne: Optional[Decimal],
    is_requested: bool,
    currency: str,
) -> PortComparisonEntry:
    notes: list[str] = []

    # --- compatibility (feasibility gate) ---
    compat_status = None
    feasible = True
    if vessel is not None:
        compat = evaluate_compatibility(vessel, port, cargo=commodity)
        compat_status = compat.status.value
        if compat.status == CompatStatus.INCOMPATIBLE:
            feasible = False
            notes.append("Vessel incompatible with this port.")

    # --- congestion + expected waiting ---
    congestion_score = None
    waiting_days = None
    try:
        cong = score_port_congestion(port)
        congestion_score = cong.congestion_score
        waiting_days = round((congestion_score / 100.0) * WAIT_DAYS_AT_MAX_SCORE, 2)
    except Exception:
        notes.append("Congestion signals unavailable; waiting time unknown.")

    # --- route distance + voyage economics (delivered cost + time) ---
    distance_nm = None
    total_cost = None
    estimated_days = None
    route = _resolve_route(origin_name, port)
    if route is not None and route.distance_nm is not None:
        distance_nm = float(route.distance_nm)
        speed = (vessel.speed if vessel and vessel.speed else DEFAULT_SPEED_KN)
        ve = compute_voyage_economics(
            VoyageEconomicsInput(
                distance_nm=route.distance_nm,
                speed_kn=speed,
                cargo_tonnes=cargo_tonnes,
                freight_rate_per_tonne=freight_rate_per_tonne,
                bunker_price_per_tonne=(bunker_price_per_tonne or Decimal("0")),
                port_days=_dec(waiting_days) if waiting_days is not None else Decimal("0"),
                currency=currency,
            )
        )
        total_cost = ve.total_voyage_cost.amount
        estimated_days = float(ve.total_days)
    else:
        notes.append("No route/distance for this origin->port; cost/time unknown.")

    return PortComparisonEntry(
        port_id=port.pk,
        port_name=port.name,
        feasible=feasible,
        compatibility_status=compat_status,
        congestion_score=congestion_score,
        expected_waiting_days=waiting_days,
        distance_nm=distance_nm,
        total_cost=total_cost,
        estimated_days=estimated_days,
        currency=currency,
        is_requested=is_requested,
        notes=notes,
    )


def compare_alternative_ports(
    *,
    origin: str,
    requested_destination: str,
    cargo_tonnes,
    commodity: str,
    vessel: Optional[Vessel] = None,
    bunker_price_per_tonne=None,
    freight_rate_per_tonne=None,
    currency: str = DEFAULT_CURRENCY,
    candidate_ports=None,
) -> AlternativePortResult:
    """Compare East Coast India destination ports for an origin/cargo.

    `candidate_ports` defaults to all east-coast-India ports. The requested port
    is always included so the caller can see the delta vs it.
    """
    cargo_tonnes = _dec(cargo_tonnes)
    if cargo_tonnes is None or cargo_tonnes <= 0:
        raise AlternativePortError("cargo_tonnes must be positive.")
    bunker_price_per_tonne = _dec(bunker_price_per_tonne)
    freight_rate_per_tonne = _dec(freight_rate_per_tonne)

    requested = Port.objects.filter(name__iexact=requested_destination.strip()).first()
    if requested is None:
        raise AlternativePortError(
            f"Requested destination port '{requested_destination}' not found."
        )

    if candidate_ports is None:
        candidate_ports = Port.objects.filter(coast=Port.Coast.EAST_COAST_INDIA)
    # Ensure the requested port is in the comparison set.
    ports = list(candidate_ports)
    if requested.pk not in {p.pk for p in ports}:
        ports.append(requested)

    entries = [
        _evaluate_port(
            p,
            origin_name=origin,
            vessel=vessel,
            cargo_tonnes=cargo_tonnes,
            commodity=commodity,
            bunker_price_per_tonne=bunker_price_per_tonne,
            freight_rate_per_tonne=freight_rate_per_tonne,
            is_requested=(p.pk == requested.pk),
            currency=currency,
        )
        for p in ports
    ]

    # Rank FEASIBLE ports with a known total cost, cheapest first; tie-break by
    # estimated time then name for determinism.
    def _sort_key(e: PortComparisonEntry):
        return (
            e.total_cost if e.total_cost is not None else Decimal("Infinity"),
            e.estimated_days if e.estimated_days is not None else float("inf"),
            e.port_name,
        )

    ranked = sorted(entries, key=_sort_key)

    requested_entry = next(e for e in entries if e.is_requested)
    feasible_scored = [
        e for e in ranked if e.feasible and e.total_cost is not None
    ]
    recommended = feasible_scored[0] if feasible_scored else None

    cost_diff = None
    time_diff = None
    if recommended is not None and requested_entry.total_cost is not None:
        cost_diff = _money(recommended.total_cost - requested_entry.total_cost)
    if (
        recommended is not None
        and recommended.estimated_days is not None
        and requested_entry.estimated_days is not None
    ):
        time_diff = round(recommended.estimated_days - requested_entry.estimated_days, 2)

    reason = _build_reason(requested_entry, recommended, cost_diff, time_diff)

    return AlternativePortResult(
        requested_port=requested.name,
        recommended_port=recommended.port_name if recommended else None,
        alternative_ports=ranked,
        cost_difference=cost_diff,
        time_difference=time_diff,
        currency=currency,
        reason=reason,
    )


def _build_reason(requested_entry, recommended, cost_diff, time_diff) -> str:
    if recommended is None:
        return (
            "No feasible alternative with a computable delivered cost was found "
            "(missing routes/distances or all candidates incompatible)."
        )
    if recommended.is_requested:
        return (
            f"The requested port ({requested_entry.port_name}) is already the "
            "lowest delivered-cost feasible option among the alternatives compared."
        )
    parts = [
        f"{recommended.port_name} is the lowest delivered-cost feasible "
        f"alternative."
    ]
    if cost_diff is not None:
        direction = "cheaper" if cost_diff < 0 else "dearer"
        parts.append(
            f"It is {abs(cost_diff)} {recommended.currency} {direction} than "
            f"{requested_entry.port_name}."
        )
    if time_diff is not None:
        faster = "faster" if time_diff < 0 else "slower"
        parts.append(f"and ~{abs(time_diff)} days {faster}.")
    if recommended.congestion_score is not None:
        parts.append(
            f"Projected congestion {recommended.congestion_score}/100, expected "
            f"waiting ~{recommended.expected_waiting_days} days."
        )
    return " ".join(parts)

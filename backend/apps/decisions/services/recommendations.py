"""Vessel recommendation orchestration (deterministic, explainable).

Given a chartering request — origin, destination, cargo quantity, commodity, and
a laycan window — this composes the existing domain engines to produce a RANKED
set of candidate vessels (and a roll-up by vessel type) for the destination:

    compatibility (catalog.services)         -> feasibility + hard filter
    port congestion (operations.services)    -> destination congestion score
    ETA (operations.services)                -> ETA + P50/P80/P95 + delay causes
    voyage economics (decisions.services)    -> estimated freight + total cost
    vessel suitability (decisions.services)  -> 0-100 score (the ranking key)

For every candidate it returns: compatibility, estimated freight, ETA,
demurrage, risk, suitability score, and estimated total cost — each carrying the
underlying engine's explainable breakdown.

Incompatible vessels (a hard compatibility FAIL) are excluded automatically and
reported separately so the exclusion is transparent.

This is a transparent, rule-based composition — NOT an optimizer and NOT ML. It
ranks by the deterministic suitability score; it does not "solve" a fixture or
allocate a fleet. Pure orchestration over the engines; a thin API view adapts
HTTP to it.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Optional

from django.db.models import Max

from apps.catalog.models import Port, Route, Vessel
from apps.catalog.services.service import evaluate_compatibility
from apps.catalog.services.compatibility import Status as CompatStatus
from apps.operations.models import FreightForecast, MarineObservation
from apps.operations.services.congestion_service import score_port_congestion
from apps.operations.services.eta import ETAValidationError
from apps.operations.services.eta_service import predict_vessel_eta
from apps.decisions.services.voyage_economics import (
    VoyageEconomicsError,
    VoyageEconomicsInput,
    compute_voyage_economics,
)
from apps.decisions.services.vessel_suitability import (
    SuitabilityInput,
    score_vessel_suitability,
)

# Weather severity (WarningSeverity) -> 0..1 risk, mirroring the congestion
# engine's mapping so the two agree.
WEATHER_RISK = {
    "none": 0.0,
    "low": 0.25,
    "moderate": 0.5,
    "high": 0.75,
    "severe": 1.0,
}

DEFAULT_CURRENCY = "USD"


class RecommendationError(ValueError):
    """Raised for invalid recommendation requests (bad laycan, missing lane...)."""


@dataclass
class RecommendationRequest:
    """A chartering requirement to recommend vessels for."""

    origin: str
    destination: str
    cargo_tonnes: Decimal
    commodity: str
    laycan_start: date
    laycan_end: date
    # Optional overrides (else derived from stored data / sensible defaults).
    currency: str = DEFAULT_CURRENCY
    # Bunker assumptions for the voyage-cost estimate (documented defaults; the
    # engine is deterministic given these).
    bunker_price_per_tonne: Optional[Decimal] = None

    def __post_init__(self):
        self.cargo_tonnes = Decimal(str(self.cargo_tonnes))
        if self.bunker_price_per_tonne is not None:
            self.bunker_price_per_tonne = Decimal(str(self.bunker_price_per_tonne))


@dataclass
class CandidateRecommendation:
    vessel_id: int
    vessel_name: str
    imo: str
    vessel_type: str
    suitability_score: float          # 0..100, the ranking key
    compatibility: dict               # CompatibilityResult.to_dict()
    estimated_freight: Optional[dict]  # Money dict (per_tonne) or None
    eta: Optional[dict]               # ETAResult.to_dict() or None
    demurrage: Optional[dict]         # Money dict (total) or None
    risk: dict                        # composed risk breakdown
    estimated_total_cost: Optional[dict]  # Money dict (total) or None
    suitability: dict                 # full SuitabilityResult.to_dict()
    voyage_economics: Optional[dict]  # full VoyageEconomicsResult.to_dict() or None

    def to_dict(self) -> dict:
        return {
            "vessel_id": self.vessel_id,
            "vessel_name": self.vessel_name,
            "imo": self.imo,
            "vessel_type": self.vessel_type,
            "suitability_score": self.suitability_score,
            "compatibility": self.compatibility,
            "estimated_freight": self.estimated_freight,
            "eta": self.eta,
            "demurrage": self.demurrage,
            "risk": self.risk,
            "estimated_total_cost": self.estimated_total_cost,
            "suitability": self.suitability,
            "voyage_economics": self.voyage_economics,
        }


@dataclass
class ExcludedVessel:
    vessel_id: int
    vessel_name: str
    imo: str
    vessel_type: str
    reason: str
    compatibility: dict

    def to_dict(self) -> dict:
        return {
            "vessel_id": self.vessel_id,
            "vessel_name": self.vessel_name,
            "imo": self.imo,
            "vessel_type": self.vessel_type,
            "reason": self.reason,
            "compatibility": self.compatibility,
        }


@dataclass
class VesselTypeRanking:
    vessel_type: str
    candidate_count: int
    best_suitability_score: float
    avg_suitability_score: float

    def to_dict(self) -> dict:
        return {
            "vessel_type": self.vessel_type,
            "candidate_count": self.candidate_count,
            "best_suitability_score": self.best_suitability_score,
            "avg_suitability_score": self.avg_suitability_score,
        }


@dataclass
class RecommendationResult:
    request: dict
    route_resolved: bool
    ranked_vessels: list[CandidateRecommendation]
    ranked_vessel_types: list[VesselTypeRanking]
    excluded_vessels: list[ExcludedVessel]
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "request": self.request,
            "route_resolved": self.route_resolved,
            "ranked_vessels": [c.to_dict() for c in self.ranked_vessels],
            "ranked_vessel_types": [t.to_dict() for t in self.ranked_vessel_types],
            "excluded_vessels": [e.to_dict() for e in self.excluded_vessels],
            "notes": self.notes,
        }


# ---------------------------------------------------------------------------
# Lane / market helpers
# ---------------------------------------------------------------------------
def _resolve_route(origin: str, destination: str) -> Optional[Route]:
    return (
        Route.objects.select_related("origin", "destination_port")
        .filter(
            origin__name__iexact=origin.strip(),
            destination_port__name__iexact=destination.strip(),
        )
        .first()
    )


def _resolve_destination_port(destination: str) -> Optional[Port]:
    return Port.objects.filter(name__iexact=destination.strip()).first()


def _market_freight_band(route: Optional[Route], vessel_type: str):
    """Latest forecast freight rate band (low, mid, high) for a lane+type.

    Returns (low, mid, high) Decimals from the most recent forecast generation,
    or (None, None, None) if none exists (freight factor then excluded).
    """
    if route is None:
        return None, None, None
    qs = FreightForecast.objects.filter(route=route, vessel_type=vessel_type)
    latest = qs.aggregate(m=Max("generated_at"))["m"]
    if latest is None:
        return None, None, None
    fc = qs.filter(generated_at=latest).order_by("target_date").first()
    if fc is None:
        return None, None, None
    mid = fc.predicted_rate_per_tonne
    low = fc.lower_bound if fc.lower_bound is not None else mid
    high = fc.upper_bound if fc.upper_bound is not None else mid
    return low, mid, high


def _weather_risk_for_port(port: Port) -> Optional[float]:
    """Latest marine warning severity near the destination -> 0..1 risk, or None.

    Uses MarineObservation.severity (the same signal the congestion engine
    consumes) so weather risk is consistent across engines.
    """
    obs = (
        MarineObservation.objects.filter(port=port)
        .order_by("-timestamp")
        .first()
    )
    if obs is None or not obs.severity:
        return None
    return WEATHER_RISK.get(str(obs.severity).lower())


def _f(value) -> Optional[float]:
    return float(value) if value is not None else None


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------
def _validate_request(req: RecommendationRequest) -> None:
    if req.cargo_tonnes is None or req.cargo_tonnes <= 0:
        raise RecommendationError("cargo_tonnes must be positive.")
    if req.laycan_end < req.laycan_start:
        raise RecommendationError("laycan_end cannot be before laycan_start.")


def _evaluate_candidate(
    vessel: Vessel,
    *,
    req: RecommendationRequest,
    port: Optional[Port],
    route: Optional[Route],
    congestion_score: Optional[float],
    weather_risk: Optional[float],
):
    """Run the engines for one vessel. Returns either a CandidateRecommendation
    or an ExcludedVessel (when compatibility is a hard INCOMPATIBLE)."""
    # --- 1. Compatibility (also the hard exclusion gate) ---
    compat = None
    compat_dict: dict = {}
    if port is not None:
        compat = evaluate_compatibility(vessel, port, cargo=req.commodity)
        compat_dict = compat.to_dict()
        if compat.status == CompatStatus.INCOMPATIBLE:
            return ExcludedVessel(
                vessel_id=vessel.pk,
                vessel_name=vessel.name,
                imo=vessel.imo,
                vessel_type=vessel.vessel_type,
                reason="; ".join(compat.reasons) or "Incompatible with destination.",
                compatibility=compat_dict,
            )
    port_compatible = (
        None if compat is None
        else compat.status in (CompatStatus.COMPATIBLE, CompatStatus.CONDITIONAL)
    )

    # --- 2. ETA (needs a resolved route with a distance) ---
    eta_dict: Optional[dict] = None
    eta_reliability: Optional[float] = None
    if route is not None and route.distance_nm is not None:
        try:
            eta = predict_vessel_eta(
                vessel, route,
                weather_risk=weather_risk if weather_risk is not None else 0.0,
            )
            eta_dict = eta.to_dict()
            # Reliability proxy: tighter spread (P95 vs point) => more reliable.
            # Deterministic transform of the delay fraction, in [0, 1].
            if eta.total_hours > 0:
                delay_frac = eta.total_delay_hours / eta.total_hours
                eta_reliability = max(0.0, min(1.0, 1.0 - delay_frac))
        except ETAValidationError:
            eta_dict = None  # leave ETA unavailable; suitability excludes it

    # --- 3. Voyage economics: estimated freight + total cost + demurrage ---
    voyage_dict: Optional[dict] = None
    estimated_freight: Optional[dict] = None
    estimated_total_cost: Optional[dict] = None
    demurrage: Optional[dict] = None
    freight_per_tonne: Optional[float] = None

    low, mid, high = _market_freight_band(route, vessel.vessel_type)
    if route is not None and route.distance_nm is not None and vessel.speed is not None:
        try:
            ve_input = VoyageEconomicsInput(
                distance_nm=route.distance_nm,
                speed_kn=vessel.speed,
                cargo_tonnes=req.cargo_tonnes,
                freight_rate_per_tonne=mid,  # from forecast, if available
                bunker_price_per_tonne=(
                    req.bunker_price_per_tonne
                    if req.bunker_price_per_tonne is not None else Decimal("0")
                ),
                currency=req.currency,
            )
            ve = compute_voyage_economics(ve_input)
            voyage_dict = ve.to_dict()
            estimated_total_cost = ve.total_voyage_cost.to_dict()
            estimated_freight = ve.cost_components["freight_cost"].to_dict()
            demurrage = ve.cost_components["estimated_demurrage"].to_dict()
        except VoyageEconomicsError:
            voyage_dict = None

    if mid is not None:
        freight_per_tonne = float(mid)

    # --- 4. Suitability score (the ranking key) ---
    demurrage_cost = (
        float(demurrage["amount"]) if demurrage is not None else None
    )
    suit_input = SuitabilityInput(
        port_compatible=port_compatible,
        vessel_draft=_f(vessel.draft),
        max_draft=_compat_limit(compat, "draft"),
        vessel_loa=_f(vessel.loa),
        max_loa=_compat_limit(compat, "loa"),
        vessel_beam=_f(vessel.beam),
        max_beam=_compat_limit(compat, "beam"),
        vessel_dwt=_f(vessel.dwt),
        required_tonnes=float(req.cargo_tonnes),
        estimated_freight_per_tonne=freight_per_tonne,
        market_freight_low=_f(low),
        market_freight_high=_f(high),
        eta_reliability=eta_reliability,
        congestion_score=congestion_score,
        weather_risk=weather_risk,
        expected_demurrage_cost=demurrage_cost,
    )
    suitability = score_vessel_suitability(suit_input)

    # --- 5. Composed risk breakdown (explainable) ---
    risk = {
        "congestion_score": congestion_score,
        "weather_risk": weather_risk,
        "expected_demurrage": demurrage,
        "eta_reliability": eta_reliability,
    }

    return CandidateRecommendation(
        vessel_id=vessel.pk,
        vessel_name=vessel.name,
        imo=vessel.imo,
        vessel_type=vessel.vessel_type,
        suitability_score=suitability.score,
        compatibility=compat_dict,
        estimated_freight=estimated_freight,
        eta=eta_dict,
        demurrage=demurrage,
        risk=risk,
        estimated_total_cost=estimated_total_cost,
        suitability=suitability.to_dict(),
        voyage_economics=voyage_dict,
    )


def _compat_limit(compat, dimension: str) -> Optional[float]:
    """Best-effort extraction of the berth/port limit the compatibility engine
    used, so suitability's dimension factors align with compatibility. The
    compatibility result doesn't expose the numeric limit, so we return None
    (dimension factor excluded) unless a hard fail already excluded the vessel.
    This keeps suitability honest rather than fabricating a limit."""
    return None


def recommend_vessels(
    req: RecommendationRequest,
    *,
    vessels=None,
) -> RecommendationResult:
    """Compute ranked vessel recommendations for a chartering request.

    `vessels` is an optional iterable of Vessel to consider; by default all
    vessels are considered (a caller/endpoint may pre-filter, e.g. to OPEN
    vessels). Incompatible vessels are excluded automatically.
    """
    _validate_request(req)

    route = _resolve_route(req.origin, req.destination)
    port = route.destination_port if route is not None else _resolve_destination_port(
        req.destination
    )

    notes: list[str] = []
    if route is None:
        notes.append(
            "No route found for the given origin/destination; freight, ETA and "
            "voyage-cost estimates that depend on route distance are unavailable."
        )
    elif route.distance_nm is None:
        notes.append(
            "Route has no stored distance; ETA and voyage-cost estimates are "
            "unavailable."
        )
    if port is None:
        notes.append(
            "Destination port not found; compatibility cannot be evaluated and no "
            "vessels can be excluded on compatibility grounds."
        )

    # Destination congestion + weather (computed once, shared by all candidates).
    congestion_score: Optional[float] = None
    weather_risk: Optional[float] = None
    if port is not None:
        try:
            congestion_score = score_port_congestion(port).congestion_score
        except Exception:
            congestion_score = None
        weather_risk = _weather_risk_for_port(port)

    if vessels is None:
        vessels = Vessel.objects.all()

    ranked: list[CandidateRecommendation] = []
    excluded: list[ExcludedVessel] = []
    for vessel in vessels:
        outcome = _evaluate_candidate(
            vessel,
            req=req,
            port=port,
            route=route,
            congestion_score=congestion_score,
            weather_risk=weather_risk,
        )
        if isinstance(outcome, ExcludedVessel):
            excluded.append(outcome)
        else:
            ranked.append(outcome)

    # Rank vessels by suitability (desc); tie-break by name for determinism.
    ranked.sort(key=lambda c: (-c.suitability_score, c.vessel_name))

    return RecommendationResult(
        request={
            "origin": req.origin,
            "destination": req.destination,
            "cargo_tonnes": str(req.cargo_tonnes),
            "commodity": req.commodity,
            "laycan_start": req.laycan_start.isoformat(),
            "laycan_end": req.laycan_end.isoformat(),
            "currency": req.currency,
        },
        route_resolved=route is not None,
        ranked_vessels=ranked,
        ranked_vessel_types=_rank_vessel_types(ranked),
        excluded_vessels=excluded,
        notes=notes,
    )


def _rank_vessel_types(ranked: list[CandidateRecommendation]) -> list[VesselTypeRanking]:
    """Roll candidate scores up by vessel type, ranked by best score."""
    by_type: dict[str, list[float]] = {}
    for c in ranked:
        by_type.setdefault(c.vessel_type, []).append(c.suitability_score)

    rows = [
        VesselTypeRanking(
            vessel_type=vtype,
            candidate_count=len(scores),
            best_suitability_score=round(max(scores), 2),
            avg_suitability_score=round(sum(scores) / len(scores), 2),
        )
        for vtype, scores in by_type.items()
    ]
    rows.sort(key=lambda r: (-r.best_suitability_score, r.vessel_type))
    return rows

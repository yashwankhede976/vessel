"""Unified decision engine (composition, explainability, scenarios).

This is the intelligent decision layer: it COMPOSES the existing domain engines
into a single answer for a chartering requirement. It writes NO new business
logic — every number comes from an existing engine:

    recommend_vessels (decisions.services.recommendations)
        -> per-vessel compatibility + congestion + ETA + demurrage + voyage
           economics + suitability ranking (which itself reuses the catalog /
           operations engines)
    market pressure (decisions.services.market_pressure)
    freight band     (FreightForecast rows, via recommendations._market_freight_band)
    spot vs contract (decisions.services.spot_vs_contract)
    unified risk     (decisions.services.risk_engine)
    fix / wait       (decisions.services.fix_wait)
    landed cost      (decisions.services.landed_cost)

It returns freight forecast, recommended vessel, vessel-port compatibility,
congestion, ETA, demurrage, total landed cost, recommended contract, risk score,
the FIX_NOW/WAIT/PARTIAL_FIX/MONITOR timing decision, expected savings, and
confidence — plus an explainability block (reasons / positive_factors /
negative_factors / model_version / data_freshness).

Scenario support (freight %, congestion, vessel availability) adjusts the
downstream timing/contract/risk inputs only; it NEVER mutates stored data — a
scenario is a stateless what-if computed from the same real base.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Optional

from django.db.models import Max
from django.utils import timezone

from apps.catalog.models import Vessel
from apps.operations.models import FreightForecast

from .recommendations import (
    RecommendationRequest,
    RecommendationResult,
    _market_freight_band,
    _resolve_route,
    recommend_vessels,
)
from .market_pressure import MarketPressureInput, compute_market_pressure
from .spot_vs_contract import SpotVsContractInput, compare_strategies
from .risk_engine import RiskInput, score_risk
from .fix_wait import FixWaitInput, decide_fix_wait
from .voyage_economics import (
    VoyageEconomicsError,
    VoyageEconomicsInput,
    compute_voyage_economics,
)

DEFAULT_CURRENCY = "USD"

# Documented planning defaults used only when the stored data does not supply a
# value (e.g. no freight forecast for the lane). These are transparent
# assumptions, clearly surfaced in the explainability block — never presented as
# observed market data.
DEFAULT_SPOT_RATE = Decimal("22")          # USD/t planning spot rate
DEFAULT_FREIGHT_VOLATILITY = 0.5           # 0..1


class DecisionError(ValueError):
    """Raised for invalid decision requests."""


@dataclass
class ScenarioOverrides:
    """Stateless what-if adjustments (never mutate stored data)."""

    freight_change_pct: Optional[float] = None       # e.g. +10 => +10% on freight
    congestion_score: Optional[float] = None          # absolute 0..100 override
    vessel_availability: Optional[float] = None        # 0..1 override

    def active(self) -> bool:
        return any(
            v is not None
            for v in (self.freight_change_pct, self.congestion_score, self.vessel_availability)
        )

    def to_dict(self) -> dict:
        return {
            "freight_change_pct": self.freight_change_pct,
            "congestion_score": self.congestion_score,
            "vessel_availability": self.vessel_availability,
        }


@dataclass
class DecisionRequest:
    commodity: str
    cargo_tonnes: Decimal
    origin: str
    destination: str
    laycan_start: date
    laycan_end: date
    required_arrival: Optional[date] = None
    currency: str = DEFAULT_CURRENCY
    scenario: ScenarioOverrides = field(default_factory=ScenarioOverrides)

    def __post_init__(self):
        self.cargo_tonnes = Decimal(str(self.cargo_tonnes))


@dataclass
class Explainability:
    reasons: list[str]
    positive_factors: list[str]
    negative_factors: list[str]
    model_version: dict          # per-engine/model versions used
    data_freshness: list[dict]   # freshness entries for the datasets consumed

    def to_dict(self) -> dict:
        return {
            "reasons": self.reasons,
            "positive_factors": self.positive_factors,
            "negative_factors": self.negative_factors,
            "model_version": self.model_version,
            "data_freshness": self.data_freshness,
        }


@dataclass
class DecisionResult:
    request: dict
    scenario: dict
    market: dict                       # market pressure result
    freight_forecast: dict             # band + model provenance
    recommended_vessel: Optional[dict] # top candidate (or None)
    compatibility: Optional[dict]
    congestion: Optional[dict]
    eta: Optional[dict]
    demurrage: Optional[dict]
    total_landed_cost: Optional[dict]
    recommended_contract: dict         # spot-vs-contract result
    risk: dict                         # unified risk result
    timing_decision: str               # FIX_NOW | WAIT | PARTIAL_FIX | MONITOR
    timing: dict                       # full fix/wait result
    expected_savings: Optional[dict]   # {amount, currency}
    confidence: Optional[float]
    ranked_vessels: list[dict]
    excluded_vessels: list[dict]
    explainability: dict
    notes: list[str]

    def to_dict(self) -> dict:
        return {
            "request": self.request,
            "scenario": self.scenario,
            "market": self.market,
            "freight_forecast": self.freight_forecast,
            "recommended_vessel": self.recommended_vessel,
            "compatibility": self.compatibility,
            "congestion": self.congestion,
            "eta": self.eta,
            "demurrage": self.demurrage,
            "total_landed_cost": self.total_landed_cost,
            "recommended_contract": self.recommended_contract,
            "risk": self.risk,
            "timing_decision": self.timing_decision,
            "timing": self.timing,
            "expected_savings": self.expected_savings,
            "confidence": self.confidence,
            "ranked_vessels": self.ranked_vessels,
            "excluded_vessels": self.excluded_vessels,
            "explainability": self.explainability,
            "notes": self.notes,
        }


def _f(v) -> Optional[float]:
    return float(v) if v is not None else None


def _is_zero(money: Optional[dict]) -> bool:
    """True if a Money dict is absent or its amount is zero."""
    if not money or money.get("amount") in (None, ""):
        return True
    try:
        return Decimal(str(money["amount"])) == 0
    except Exception:
        return False


def _apply_freight_change(rate: Optional[Decimal], pct: Optional[float]) -> Optional[Decimal]:
    if rate is None:
        return None
    if pct is None:
        return rate
    return (rate * (Decimal("1") + Decimal(str(pct)) / Decimal("100"))).quantize(Decimal("0.01"))


def _lane_freight_band(route):
    """Latest freight band for the LANE at any vessel type (fallback).

    Mirrors recommendations._market_freight_band but does not filter on vessel
    type, so a stored forecast for the lane still informs the decision when the
    recommended vessel's exact class has no forecast.
    """
    if route is None:
        return None, None, None
    qs = FreightForecast.objects.filter(route=route)
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


def _freight_model_version() -> dict:
    """Model name/version + generation time from the latest stored forecast."""
    latest = FreightForecast.objects.order_by("-generated_at").first()
    if latest is None:
        return {"freight_model": None, "freight_model_version": None, "generated_at": None}
    return {
        "freight_model": latest.model_name or None,
        "freight_model_version": latest.model_version or None,
        "generated_at": latest.generated_at.isoformat() if latest.generated_at else None,
    }


def evaluate_decision(req: DecisionRequest) -> DecisionResult:
    """Compose the engines into a single, explainable decision."""
    if req.cargo_tonnes is None or req.cargo_tonnes <= 0:
        raise DecisionError("cargo_tonnes must be positive.")
    if req.laycan_end < req.laycan_start:
        raise DecisionError("laycan_end cannot be before laycan_start.")

    scenario = req.scenario
    notes: list[str] = []
    positives: list[str] = []
    negatives: list[str] = []
    reasons: list[str] = []

    # --- 1. Vessel recommendation (reuses compatibility/congestion/ETA/voyage/
    #        suitability per candidate). Restrict to open vessels by default. ---
    open_vessels = Vessel.objects.filter(
        availability_status=Vessel.AvailabilityStatus.OPEN
    )
    rec: RecommendationResult = recommend_vessels(
        RecommendationRequest(
            origin=req.origin,
            destination=req.destination,
            cargo_tonnes=req.cargo_tonnes,
            commodity=req.commodity,
            laycan_start=req.laycan_start,
            laycan_end=req.laycan_end,
            currency=req.currency,
        ),
        vessels=open_vessels,
    )
    notes.extend(rec.notes)
    top = rec.ranked_vessels[0] if rec.ranked_vessels else None

    # --- 2. Freight band (real stored forecast for the lane) ---
    route = _resolve_route(req.origin, req.destination)
    vessel_type = top.vessel_type if top else ""
    low, mid, high = _market_freight_band(route, vessel_type)
    # Fallback: if there's no forecast for the recommended vessel's exact type,
    # use a lane-wide forecast (any vessel type) so a stored forecast still
    # drives the decision rather than silently dropping to the planning default.
    if mid is None:
        low, mid, high = _lane_freight_band(route)
    base_rate = mid if mid is not None else DEFAULT_SPOT_RATE
    if mid is None:
        notes.append(
            "No stored freight forecast for this lane/type; using a documented "
            "planning spot rate for the timing/contract analysis (labelled)."
        )
    # Scenario: apply the freight change to the working rate.
    working_rate = _apply_freight_change(base_rate, scenario.freight_change_pct)
    fc_7 = _apply_freight_change(mid, scenario.freight_change_pct)
    fc_14 = _apply_freight_change(high, scenario.freight_change_pct)

    freight_forecast = {
        "lane": {"origin": req.origin, "destination": req.destination, "vessel_type": vessel_type or None},
        "band": {
            "low": str(low) if low is not None else None,
            "mid": str(mid) if mid is not None else None,
            "high": str(high) if high is not None else None,
        },
        "working_rate": str(working_rate) if working_rate is not None else None,
        "source": "FreightForecast" if mid is not None else "planning_default",
        **_freight_model_version(),
    }

    # --- 3. Market pressure (scenario congestion feeds it) ---
    congestion_score = scenario.congestion_score
    if congestion_score is None and top is not None:
        congestion_score = (top.risk or {}).get("congestion_score")
    weather_risk = (top.risk or {}).get("weather_risk") if top else None

    market = compute_market_pressure(
        MarketPressureInput(
            vessel_supply=scenario.vessel_availability,
            freight_volatility=DEFAULT_FREIGHT_VOLATILITY,
            port_congestion=_f(congestion_score),
        )
    ).to_dict()

    # --- 4. Unified risk (composes the real per-vessel risk signals) ---
    demurrage = top.demurrage if top else None
    eta = top.eta if top else None
    risk = score_risk(
        RiskInput(
            freight_volatility=DEFAULT_FREIGHT_VOLATILITY,
            port_congestion=_f(congestion_score),
            weather_risk=weather_risk,
            eta_delay_probability=(eta or {}).get("delay_probability") if eta else None,
            expected_demurrage_cost=(
                float(demurrage["amount"]) if demurrage and demurrage.get("amount") else None
            ),
        )
    ).to_dict()

    # --- 5. Contract strategy (spot vs short/medium/multi-voyage) ---
    strategy = compare_strategies(
        SpotVsContractInput(
            spot_freight_per_tonne=working_rate or DEFAULT_SPOT_RATE,
            cargo_tonnes=req.cargo_tonnes,
            freight_volatility=DEFAULT_FREIGHT_VOLATILITY,
            base_demurrage_cost=(
                Decimal(str(demurrage["amount"])) if demurrage and demurrage.get("amount") else None
            ),
            congestion_score=_f(congestion_score),
            currency=req.currency,
        )
    ).to_dict()

    # --- 6. Fix / Wait timing ---
    days_to_deadline = None
    ref = req.required_arrival or req.laycan_end
    if ref is not None:
        days_to_deadline = max(0, (ref - timezone.now().date()).days)
    timing = decide_fix_wait(
        FixWaitInput(
            current_rate=working_rate or DEFAULT_SPOT_RATE,
            forecast_7d=fc_7,
            forecast_14d=fc_14,
            confidence_7d=0.75,
            confidence_14d=0.7,
            days_to_deadline=days_to_deadline,
            vessel_availability=scenario.vessel_availability,
            congestion_score=_f(congestion_score),
            freight_volatility=DEFAULT_FREIGHT_VOLATILITY,
        )
    ).to_dict()

    # --- 7. Total landed cost (from the top candidate's voyage economics) ---
    total_landed_cost = top.estimated_total_cost if top else None
    # If the recommendation's per-type economics had no freight rate (its exact
    # vessel class lacked a forecast) but we resolved a lane working rate, compute
    # the voyage cost from that rate so the headline total is grounded, not 0.
    if (
        top is not None
        and working_rate is not None
        and route is not None
        and route.distance_nm is not None
        and _is_zero(total_landed_cost)
    ):
        vessel_obj = Vessel.objects.filter(pk=top.vessel_id).only("speed").first()
        speed = vessel_obj.speed if vessel_obj and vessel_obj.speed else None
        if speed is not None:
            try:
                ve = compute_voyage_economics(
                    VoyageEconomicsInput(
                        distance_nm=route.distance_nm,
                        speed_kn=speed,
                        cargo_tonnes=req.cargo_tonnes,
                        freight_rate_per_tonne=working_rate,
                        currency=req.currency,
                    )
                )
                total_landed_cost = ve.total_voyage_cost.to_dict()
            except VoyageEconomicsError:
                pass

    # --- confidence: blend fix/wait effective confidence with suitability ---
    confidence = timing.get("effective_confidence")
    if confidence is None and top is not None:
        confidence = round(top.suitability_score / 100.0, 3)

    # --- explainability ---
    if top is not None:
        positives.append(
            f"Top vessel {top.vessel_name} scores {top.suitability_score:.0f}/100 on suitability."
        )
        reasons.append(
            f"Recommended {top.vessel_name} ({top.vessel_type}) for "
            f"{req.origin} → {req.destination}."
        )
    else:
        negatives.append("No compatible open vessel was found for this requirement.")
    if rec.excluded_vessels:
        negatives.append(
            f"{len(rec.excluded_vessels)} vessel(s) excluded as incompatible with the port."
        )
    reasons.append(
        f"Contract: {strategy['recommended_strategy']} (lowest risk-adjusted cost)."
    )
    reasons.append(f"Timing: {timing['decision']} — {timing['reason']}")
    (positives if risk["overall_score"] < 50 else negatives).append(
        f"Overall risk {risk['overall_score']:.0f}/100 ({risk['risk_level']})."
    )
    if congestion_score is not None:
        (negatives if congestion_score >= 55 else positives).append(
            f"Destination congestion {float(congestion_score):.0f}/100."
        )
    if market["classification"] in ("TIGHT", "EXTREMELY_TIGHT"):
        negatives.append(f"Market is {market['classification']} (index {market['index']:.0f}).")
    else:
        positives.append(f"Market is {market['classification']} (index {market['index']:.0f}).")
    if scenario.active():
        reasons.append(f"Scenario applied: {scenario.to_dict()}.")

    explain = Explainability(
        reasons=reasons,
        positive_factors=positives,
        negative_factors=negatives,
        model_version={
            **_freight_model_version(),
            "suitability_engine": "vessel_suitability@rule-based",
            "risk_engine": "risk_engine@rule-based",
            "timing_engine": "fix_wait@rule-based",
        },
        data_freshness=_data_freshness(),
    )

    return DecisionResult(
        request={
            "commodity": req.commodity,
            "cargo_tonnes": str(req.cargo_tonnes),
            "origin": req.origin,
            "destination": req.destination,
            "laycan_start": req.laycan_start.isoformat(),
            "laycan_end": req.laycan_end.isoformat(),
            "required_arrival": req.required_arrival.isoformat() if req.required_arrival else None,
            "currency": req.currency,
        },
        scenario=scenario.to_dict(),
        market=market,
        freight_forecast=freight_forecast,
        recommended_vessel=top.to_dict() if top else None,
        compatibility=top.compatibility if top else None,
        congestion={"score": _f(congestion_score)} if congestion_score is not None else None,
        eta=eta,
        demurrage=demurrage,
        total_landed_cost=total_landed_cost,
        recommended_contract=strategy,
        risk=risk,
        timing_decision=timing["decision"],
        timing=timing,
        expected_savings={
            "amount": strategy["expected_savings"],
            "currency": strategy["currency"],
        },
        confidence=confidence,
        ranked_vessels=[v.to_dict() for v in rec.ranked_vessels],
        excluded_vessels=[e.to_dict() for e in rec.excluded_vessels],
        explainability=explain.to_dict(),
        notes=notes,
    )


def _data_freshness() -> list[dict]:
    """Freshness of the datasets this decision consumed (best-effort)."""
    try:
        from apps.ingestion.freshness import data_freshness

        relevant = {"ais_positions", "weather", "marine", "trade", "port_congestion"}
        return [e.to_dict() for e in data_freshness() if e.dataset in relevant]
    except Exception:  # freshness is observability only — never block a decision
        return []

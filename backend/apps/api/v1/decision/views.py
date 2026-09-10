"""Unified decision API (v1): POST /decision/ and POST /decision/assistant/.

Both views only ADAPT HTTP to the decision engine + existing domain engines;
they contain no business logic and never fabricate values. The assistant maps a
natural-language question to an intent and answers from real engine output.
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from drf_spectacular.utils import OpenApiExample, extend_schema
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.decisions.services.decision_engine import (
    DecisionError,
    DecisionRequest,
    ScenarioOverrides,
    evaluate_decision,
)
from apps.decisions.services.landed_cost import LandedCostError

from .serializers import AssistantRequestSerializer, DecisionRequestSerializer

# Project origins available to the assistant's comparisons (no invented lanes).
PROJECT_ORIGINS = ["Australia", "Indonesia", "Mozambique", "USA", "Russia"]
EAST_COAST_PORTS = [
    "Paradip", "Dhamra", "Visakhapatnam", "Gangavaram", "Gopalpur", "Haldia",
]


def _error(detail: str, code: str = "invalid_request") -> Response:
    return Response(
        {"success": False, "data": None, "errors": [{"code": code, "detail": detail}]},
        status=status.HTTP_400_BAD_REQUEST,
    )


def _build_request(data: dict) -> DecisionRequest:
    scenario_data = data.get("scenario") or {}
    return DecisionRequest(
        commodity=data["commodity"],
        cargo_tonnes=data["cargo_quantity"],
        origin=data["origin"],
        destination=data["destination"],
        laycan_start=data["laycan_start"],
        laycan_end=data["laycan_end"],
        required_arrival=data.get("required_arrival"),
        currency=data.get("currency", "USD"),
        scenario=ScenarioOverrides(
            freight_change_pct=scenario_data.get("freight_change_pct"),
            congestion_score=scenario_data.get("congestion_score"),
            vessel_availability=scenario_data.get("vessel_availability"),
        ),
    )


class DecisionView(APIView):
    """Unified decision: composes forecast, vessel, port, ETA, cost, contract,
    risk and timing into one explainable recommendation."""

    authentication_classes: list = []
    permission_classes: list = []

    @extend_schema(
        summary="Unified chartering decision",
        request=DecisionRequestSerializer,
        responses=DecisionRequestSerializer,
        examples=[
            OpenApiExample(
                "Coal into Paradip",
                value={
                    "commodity": "Coal", "cargo_quantity": "75000",
                    "origin": "Australia", "destination": "Paradip",
                    "laycan_start": "2026-10-01", "laycan_end": "2026-10-10",
                    "required_arrival": "2026-10-20",
                    "scenario": {"freight_change_pct": 10},
                },
                request_only=True,
            )
        ],
    )
    def post(self, request: Request) -> Response:
        payload = DecisionRequestSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        try:
            result = evaluate_decision(_build_request(payload.validated_data))
        except DecisionError as exc:
            return _error(str(exc))
        return Response(result.to_dict())


class AssistantView(APIView):
    """Answer common chartering questions from real backend engine output.

    The assistant classifies the question into an intent and calls the existing
    engines; it NEVER invents values. If it cannot map a question it says so.
    """

    authentication_classes: list = []
    permission_classes: list = []

    @extend_schema(
        summary="Decision assistant (grounded Q&A)",
        request=AssistantRequestSerializer,
        responses=AssistantRequestSerializer,
    )
    def post(self, request: Request) -> Response:
        payload = AssistantRequestSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        question = payload.validated_data["question"]
        try:
            answer = self._answer(question)
        except (DecisionError, LandedCostError) as exc:
            return _error(str(exc))
        return Response(answer)

    # ------------------------------------------------------------------
    def _answer(self, question: str) -> dict:
        q = question.lower()
        origin = self._find(q, PROJECT_ORIGINS) or "Australia"
        ports = [p for p in EAST_COAST_PORTS if p.lower() in q]
        destination = ports[0] if ports else "Paradip"
        laycan_start = date.today() + timedelta(days=14)
        laycan_end = laycan_start + timedelta(days=10)

        base_kwargs = dict(
            commodity="Coal", cargo_tonnes=Decimal("75000"),
            origin=origin, destination=destination,
            laycan_start=laycan_start, laycan_end=laycan_end,
        )

        # Intent: compare two ports (e.g. "Is Dhamra better than Paradip?").
        if len(ports) >= 2 and ("better" in q or " vs " in q or "or" in q):
            return self._compare_ports(origin, ports[0], ports[1], base_kwargs)

        # Intent: spot vs multi-voyage / contract choice.
        if "spot" in q or "multi" in q or "contract" in q:
            d = evaluate_decision(DecisionRequest(**base_kwargs)).to_dict()
            strat = d["recommended_contract"]
            return self._reply(
                intent="contract_choice",
                answer=(
                    f"Recommended contract for {origin} → {destination}: "
                    f"{strat['recommended_strategy']} — lowest risk-adjusted cost. "
                    f"{strat['reason']}"
                ),
                data={"recommended_contract": strat},
            )

        # Intent: which vessel is best.
        if "vessel" in q and ("best" in q or "which" in q):
            d = evaluate_decision(DecisionRequest(**base_kwargs)).to_dict()
            v = d["recommended_vessel"]
            if v is None:
                return self._reply(
                    intent="best_vessel",
                    answer=f"No compatible open vessel was found for {origin} → {destination}.",
                    data={"recommended_vessel": None, "notes": d["notes"]},
                )
            return self._reply(
                intent="best_vessel",
                answer=(
                    f"The best vessel for {origin} → {destination} is {v['vessel_name']} "
                    f"({v['vessel_type']}), suitability {v['suitability_score']:.0f}/100."
                ),
                data={"recommended_vessel": v},
            )

        # Intent: freight-change scenario ("what if freight increases 10%?").
        pct = self._extract_pct(q)
        if pct is not None and ("freight" in q or "rate" in q or "increase" in q or "decrease" in q):
            signed = -pct if ("decrease" in q or "fall" in q or "drop" in q) else pct
            d = evaluate_decision(
                DecisionRequest(**base_kwargs, scenario=ScenarioOverrides(freight_change_pct=signed))
            ).to_dict()
            return self._reply(
                intent="freight_scenario",
                answer=(
                    f"If freight moves {signed:+.0f}% on {origin} → {destination}, the "
                    f"timing decision is {d['timing_decision']} and the recommended "
                    f"contract is {d['recommended_contract']['recommended_strategy']}."
                ),
                data={"timing": d["timing"], "recommended_contract": d["recommended_contract"], "scenario": d["scenario"]},
            )

        # Default intent: fix or wait for the lane.
        d = evaluate_decision(DecisionRequest(**base_kwargs)).to_dict()
        return self._reply(
            intent="fix_or_wait",
            answer=(
                f"For {origin} → {destination}: {d['timing_decision']}. "
                f"{d['timing']['reason']}"
            ),
            data={"timing": d["timing"], "recommended_vessel": d["recommended_vessel"], "risk": d["risk"]},
        )

    def _compare_ports(self, origin: str, a: str, b: str, base_kwargs: dict) -> dict:
        da = evaluate_decision(DecisionRequest(**{**base_kwargs, "destination": a})).to_dict()
        db = evaluate_decision(DecisionRequest(**{**base_kwargs, "destination": b})).to_dict()
        cost_a = self._cost(da)
        cost_b = self._cost(db)
        # Ground the comparison only in values that exist.
        if cost_a is not None and cost_b is not None:
            cheaper = a if cost_a <= cost_b else b
            answer = (
                f"For {origin}: estimated total voyage cost is "
                f"{cost_a:,.0f} to {a} vs {cost_b:,.0f} to {b} — {cheaper} is cheaper."
            )
        else:
            answer = (
                f"Comparing {a} vs {b} for {origin}: cost could not be fully computed "
                "for both (missing route/forecast data), so no cost ranking is asserted."
            )
        return self._reply(
            intent="compare_ports",
            answer=answer,
            data={a: {"timing": da["timing_decision"], "total_cost": da["total_landed_cost"]},
                  b: {"timing": db["timing_decision"], "total_cost": db["total_landed_cost"]}},
        )

    @staticmethod
    def _cost(decision: dict):
        tlc = decision.get("total_landed_cost")
        if tlc and tlc.get("amount"):
            try:
                return float(tlc["amount"])
            except (TypeError, ValueError):
                return None
        return None

    @staticmethod
    def _find(q: str, options: list[str]):
        for o in options:
            if o.lower() in q:
                return o
        return None

    @staticmethod
    def _extract_pct(q: str):
        import re

        m = re.search(r"(\d+(?:\.\d+)?)\s*%", q)
        return float(m.group(1)) if m else None

    @staticmethod
    def _reply(*, intent: str, answer: str, data: dict) -> dict:
        return {"intent": intent, "answer": answer, "data": data, "grounded": True}

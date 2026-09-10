"""Unified decision API (v1): POST /decision/.

The view only ADAPTS HTTP to the decision engine + existing domain engines; it
contains no business logic and never fabricates values.
"""
from __future__ import annotations

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

from .serializers import DecisionRequestSerializer


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

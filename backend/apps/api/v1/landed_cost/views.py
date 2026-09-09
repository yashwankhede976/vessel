"""Landed-cost API views (v1): single compute + multi-origin comparison."""
from __future__ import annotations

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.decisions.services.landed_cost import (
    CostComponent,
    LandedCostError,
    LandedCostInput,
    compare_origins,
    compute_landed_cost,
)

from .serializers import (
    COMPONENT_FIELDS,
    LandedCostCompareRequestSerializer,
    LandedCostRequestSerializer,
)


def _build_input(data: dict) -> LandedCostInput:
    kwargs = {
        "origin": data["origin"],
        "destination": data["destination"],
        "cargo_tonnes": data["cargo_tonnes"],
        "target_currency": data.get("target_currency", "USD"),
        "fx_rates": data.get("fx_rates", {}),
    }
    for field in COMPONENT_FIELDS:
        comp = data.get(field)
        if comp is not None:
            kwargs[field] = CostComponent(
                amount=comp.get("amount"), currency=comp.get("currency", "USD")
            )
    return LandedCostInput(**kwargs)


def _error(detail: str) -> Response:
    return Response(
        {"success": False, "data": None,
         "errors": [{"code": "invalid_request", "detail": detail}]},
        status=status.HTTP_400_BAD_REQUEST,
    )


class LandedCostView(APIView):
    """Compute total landed cost + per-tonne for one origin -> destination."""

    authentication_classes: list = []
    permission_classes: list = []

    @extend_schema(
        summary="Total landed cost",
        request=LandedCostRequestSerializer,
        responses=LandedCostRequestSerializer,
    )
    def post(self, request: Request) -> Response:
        payload = LandedCostRequestSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        try:
            result = compute_landed_cost(_build_input(payload.validated_data))
        except LandedCostError as exc:
            return _error(str(exc))
        return Response(result.to_dict())


class LandedCostCompareView(APIView):
    """Compare origins (Australia/Indonesia/Mozambique/USA/Russia, etc.) for one
    destination — sorted cheapest-first with delta vs the cheapest."""

    authentication_classes: list = []
    permission_classes: list = []

    @extend_schema(
        summary="Compare origins by landed cost",
        request=LandedCostCompareRequestSerializer,
        responses=LandedCostCompareRequestSerializer,
    )
    def post(self, request: Request) -> Response:
        payload = LandedCostCompareRequestSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        inputs = [_build_input(row) for row in payload.validated_data["inputs"]]
        try:
            result = compare_origins(inputs)
        except LandedCostError as exc:
            return _error(str(exc))
        return Response(result.to_dict())

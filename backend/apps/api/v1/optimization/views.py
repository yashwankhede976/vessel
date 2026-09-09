"""Optimization API view (v1): multi-voyage procurement MILP (OR-Tools)."""
from __future__ import annotations

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.decisions.services.optimization import (
    CandidateVoyage,
    OptimizationError,
    OptimizationInput,
    optimize_multi_voyage,
)

from .serializers import OptimizationRequestSerializer


class MultiVoyageOptimizationView(APIView):
    """Minimize expected procurement cost across candidate voyages subject to the
    cargo requirement, capacity, compatibility, laycan, contract, destination and
    origin constraints. Returns the selected voyages and allocations."""

    authentication_classes: list = []
    permission_classes: list = []

    @extend_schema(
        summary="Multi-voyage procurement optimization",
        request=OptimizationRequestSerializer,
        responses=OptimizationRequestSerializer,
    )
    def post(self, request: Request) -> Response:
        payload = OptimizationRequestSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = payload.validated_data

        candidates = [CandidateVoyage(**c) for c in data["candidates"]]
        inp = OptimizationInput(
            required_tonnes=data["required_tonnes"],
            candidates=candidates,
            tolerance_pct=data.get("tolerance_pct", 0),
            currency=data.get("currency", "USD"),
            destination_capacity=data.get("destination_capacity", {}),
            origin_min_tonnes=data.get("origin_min_tonnes", {}),
            origin_max_tonnes=data.get("origin_max_tonnes", {}),
            contract_min_voyages=data.get("contract_min_voyages", {}),
            contract_max_voyages=data.get("contract_max_voyages", {}),
            time_limit_ms=data.get("time_limit_ms", 5000),
        )
        try:
            result = optimize_multi_voyage(inp)
        except OptimizationError as exc:
            return Response(
                {"success": False, "data": None,
                 "errors": [{"code": "optimization_failed", "detail": str(exc)}]},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(result.to_dict())

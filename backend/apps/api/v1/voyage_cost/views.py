"""Voyage-cost API view (v1)."""
from __future__ import annotations

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.decisions.services.voyage_economics import (
    VoyageEconomicsError,
    VoyageEconomicsInput,
    compute_voyage_economics,
)

from .serializers import VoyageCostRequestSerializer


class VoyageCostView(APIView):
    """Compute itemized voyage economics: total cost, per-tonne, per-day, etc."""

    authentication_classes: list = []
    permission_classes: list = []

    @extend_schema(
        summary="Voyage economics",
        request=VoyageCostRequestSerializer,
        responses=VoyageCostRequestSerializer,
    )
    def post(self, request: Request) -> Response:
        payload = VoyageCostRequestSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        try:
            result = compute_voyage_economics(
                VoyageEconomicsInput(**payload.validated_data)
            )
        except VoyageEconomicsError as exc:
            return Response(
                {"success": False, "data": None,
                 "errors": [{"code": "invalid_request", "detail": str(exc)}]},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(result.to_dict())

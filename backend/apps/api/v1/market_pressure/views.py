"""Market-pressure API view (v1)."""
from __future__ import annotations

from drf_spectacular.utils import extend_schema
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.decisions.services.market_pressure import (
    MarketPressureInput,
    compute_market_pressure,
)

from .serializers import MarketPressureRequestSerializer


class MarketPressureView(APIView):
    """Compute the Freight Market Pressure Index (0-100) with factor breakdown."""

    authentication_classes: list = []
    permission_classes: list = []

    @extend_schema(
        summary="Freight Market Pressure Index",
        request=MarketPressureRequestSerializer,
        responses=MarketPressureRequestSerializer,
    )
    def post(self, request: Request) -> Response:
        payload = MarketPressureRequestSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = payload.validated_data
        result = compute_market_pressure(MarketPressureInput(**data))
        return Response(result.to_dict())

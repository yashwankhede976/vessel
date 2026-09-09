"""Congestion-forecast API view (v1)."""
from __future__ import annotations

from drf_spectacular.utils import extend_schema
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.operations.services.congestion import CongestionInput
from apps.operations.services.congestion_forecast import (
    CongestionForecastInput,
    forecast_congestion,
)

from .serializers import CongestionForecastRequestSerializer


class CongestionForecastView(APIView):
    """Forecast port congestion (score, waiting time, confidence, risk level)
    for the 1 / 3 / 7 / 14-day horizons."""

    authentication_classes: list = []
    permission_classes: list = []

    @extend_schema(
        summary="Multi-horizon port congestion forecast",
        request=CongestionForecastRequestSerializer,
        responses=CongestionForecastRequestSerializer,
    )
    def post(self, request: Request) -> Response:
        payload = CongestionForecastRequestSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = dict(payload.validated_data)

        trend = data.pop("trend_per_day", None)
        recent_wait = data.get("recent_waiting_time_days")
        current = CongestionInput(**data)
        result = forecast_congestion(
            CongestionForecastInput(
                current=current,
                trend_per_day=trend,
                recent_waiting_time_days=recent_wait,
            )
        )
        return Response(result.to_dict())

"""Risk API view (v1)."""
from __future__ import annotations

from drf_spectacular.utils import extend_schema
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.decisions.services.risk_engine import RiskInput, score_risk

from .serializers import RiskRequestSerializer


class RiskView(APIView):
    """Compute the unified risk score (0-100) with factor breakdown.

    Signals not supplied remain UNKNOWN — they are reported and excluded from
    the score rather than being assigned a fabricated value.
    """

    authentication_classes: list = []
    permission_classes: list = []

    @extend_schema(
        summary="Unified risk score",
        request=RiskRequestSerializer,
        responses=RiskRequestSerializer,
    )
    def post(self, request: Request) -> Response:
        payload = RiskRequestSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        result = score_risk(RiskInput(**payload.validated_data))
        return Response(result.to_dict())

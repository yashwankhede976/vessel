"""ETA API view (v1)."""
from __future__ import annotations

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.operations.services.eta import (
    ETAInput,
    ETAValidationError,
    predict_eta,
)

from .serializers import ETARequestSerializer


class ETAView(APIView):
    """Predict ETA with P50/P80/P95, delay probability and delay reasons."""

    authentication_classes: list = []
    permission_classes: list = []

    @extend_schema(
        summary="Vessel ETA prediction",
        request=ETARequestSerializer,
        responses=ETARequestSerializer,
    )
    def post(self, request: Request) -> Response:
        payload = ETARequestSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        try:
            result = predict_eta(ETAInput(**payload.validated_data))
        except ETAValidationError as exc:
            return Response(
                {"success": False, "data": None,
                 "errors": [{"code": "invalid_eta", "detail": str(exc)}]},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(result.to_dict())

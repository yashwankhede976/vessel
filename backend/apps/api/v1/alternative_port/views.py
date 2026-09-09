"""Alternative-port API view (v1)."""
from __future__ import annotations

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.catalog.models import Vessel
from apps.decisions.services.alternative_port import (
    AlternativePortError,
    compare_alternative_ports,
)

from .serializers import AlternativePortRequestSerializer


class AlternativePortView(APIView):
    """Compare East Coast India destination ports for an origin/cargo and
    recommend the lowest delivered-cost feasible port."""

    authentication_classes: list = []
    permission_classes: list = []

    @extend_schema(
        summary="Alternative destination-port comparison",
        request=AlternativePortRequestSerializer,
        responses=AlternativePortRequestSerializer,
    )
    def post(self, request: Request) -> Response:
        payload = AlternativePortRequestSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = payload.validated_data

        vessel = None
        vessel_id = data.get("vessel_id")
        if vessel_id is not None:
            vessel = Vessel.objects.filter(pk=vessel_id).first()
            if vessel is None:
                return _error(f"Vessel id {vessel_id} not found.")

        try:
            result = compare_alternative_ports(
                origin=data["origin"],
                requested_destination=data["requested_destination"],
                cargo_tonnes=data["cargo_tonnes"],
                commodity=data["commodity"],
                vessel=vessel,
                bunker_price_per_tonne=data.get("bunker_price_per_tonne"),
                freight_rate_per_tonne=data.get("freight_rate_per_tonne"),
                currency=data.get("currency", "USD"),
            )
        except AlternativePortError as exc:
            return _error(str(exc))
        return Response(result.to_dict())


def _error(detail: str) -> Response:
    return Response(
        {"success": False, "data": None,
         "errors": [{"code": "invalid_request", "detail": detail}]},
        status=status.HTTP_400_BAD_REQUEST,
    )

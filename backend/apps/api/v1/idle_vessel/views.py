"""Idle-vessel API view (v1)."""
from __future__ import annotations

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.catalog.models import Port, Vessel
from apps.decisions.services.idle_vessel import (
    EmploymentOpportunity,
    IdleVesselError,
    rank_employment,
)

from .serializers import IdleVesselRequestSerializer


def _error(detail: str, code: str = "invalid_request") -> Response:
    return Response(
        {"success": False, "data": None,
         "errors": [{"code": code, "detail": detail}]},
        status=status.HTTP_400_BAD_REQUEST,
    )


class IdleVesselView(APIView):
    """Rank possible next-voyage employment opportunities for an open vessel."""

    authentication_classes: list = []
    permission_classes: list = []

    @extend_schema(
        summary="Idle-vessel employment ranking",
        request=IdleVesselRequestSerializer,
        responses=IdleVesselRequestSerializer,
    )
    def post(self, request: Request) -> Response:
        payload = IdleVesselRequestSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = payload.validated_data

        vessel = Vessel.objects.filter(pk=data["vessel_id"]).first()
        if vessel is None:
            return _error(f"Vessel id {data['vessel_id']} not found.")

        opportunities = []
        for opp in data["opportunities"]:
            port = None
            port_id = opp.get("discharge_port_id")
            if port_id is not None:
                port = Port.objects.filter(pk=port_id).first()
                if port is None:
                    return _error(f"Discharge port id {port_id} not found.")
            opportunities.append(
                EmploymentOpportunity(
                    name=opp["name"],
                    laden_distance_nm=opp["laden_distance_nm"],
                    cargo_tonnes=opp["cargo_tonnes"],
                    freight_rate_per_tonne=opp["freight_rate_per_tonne"],
                    ballast_distance_nm=opp.get("ballast_distance_nm"),
                    port=port,
                    commodity=opp.get("commodity") or None,
                    port_cost=opp.get("port_cost"),
                    bunker_price_per_tonne=opp.get("bunker_price_per_tonne"),
                )
            )

        try:
            result = rank_employment(
                vessel, opportunities, currency=data.get("currency", "USD")
            )
        except IdleVesselError as exc:
            return _error(str(exc))
        return Response(result.to_dict())

"""Recommendations domain API views (v1).

Exposes the deterministic vessel-recommendation engine over HTTP. The heavy
lifting (composing compatibility, congestion, ETA, voyage economics and
suitability, ranking, and excluding incompatible vessels) lives in
apps.decisions.services.recommendations; this view only adapts HTTP <-> service.
"""
from __future__ import annotations

from drf_spectacular.utils import OpenApiExample, extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.catalog.models import Vessel
from apps.decisions.services.recommendations import (
    RecommendationError,
    RecommendationRequest,
    recommend_vessels,
)

from .serializers import VesselRecommendationRequestSerializer


class VesselRecommendationView(APIView):
    """Rank vessels (and vessel types) for a chartering requirement.

    Given origin, destination, cargo quantity, commodity and a laycan window,
    returns candidate vessels ranked by a transparent suitability score. Each
    candidate carries its compatibility, estimated freight, ETA, demurrage,
    risk, suitability score and estimated total cost — with the underlying
    explainable breakdowns. Incompatible vessels are excluded automatically and
    listed under `excluded_vessels`.

    This is a decision-support ranking, not an optimizer: it computes and orders
    candidates; it does not "solve" a fixture or allocate a fleet.
    """

    # Public read-style endpoint, consistent with the rest of the API surface.
    authentication_classes: list = []
    permission_classes: list = []

    @extend_schema(
        summary="Recommend and rank vessels for a chartering requirement",
        request=VesselRecommendationRequestSerializer,
        responses=inline_serializer(
            name="VesselRecommendationResponse",
            fields={
                "request": serializers.DictField(),
                "route_resolved": serializers.BooleanField(),
                "ranked_vessels": serializers.ListField(child=serializers.DictField()),
                "ranked_vessel_types": serializers.ListField(
                    child=serializers.DictField()
                ),
                "excluded_vessels": serializers.ListField(
                    child=serializers.DictField()
                ),
                "notes": serializers.ListField(child=serializers.CharField()),
            },
        ),
        examples=[
            OpenApiExample(
                "Coal into Paradip",
                value={
                    "origin": "Australia",
                    "destination": "Paradip",
                    "cargo_tonnes": "75000",
                    "commodity": "Coal",
                    "laycan_start": "2026-10-01",
                    "laycan_end": "2026-10-10",
                },
                request_only=True,
            )
        ],
    )
    def post(self, request: Request) -> Response:
        payload = VesselRecommendationRequestSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = payload.validated_data

        vessels = None
        if data.get("only_available", True):
            vessels = Vessel.objects.filter(
                availability_status=Vessel.AvailabilityStatus.OPEN
            )

        req = RecommendationRequest(
            origin=data["origin"],
            destination=data["destination"],
            cargo_tonnes=data["cargo_tonnes"],
            commodity=data["commodity"],
            laycan_start=data["laycan_start"],
            laycan_end=data["laycan_end"],
            currency=data.get("currency", "USD"),
            bunker_price_per_tonne=data.get("bunker_price_per_tonne"),
        )

        try:
            result = recommend_vessels(req, vessels=vessels)
        except RecommendationError as exc:
            return Response(
                {
                    "success": False,
                    "data": None,
                    "errors": [{"code": "invalid_request", "detail": str(exc)}],
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(result.to_dict())

"""System / observability API views (v1): data freshness + external services."""
from __future__ import annotations

from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.ingestion.freshness import data_freshness, external_services


class DataFreshnessView(APIView):
    """Freshness (FRESH/STALE/VERY_STALE/UNKNOWN) per dataset."""

    authentication_classes: list = []
    permission_classes: list = []

    @extend_schema(
        summary="Data freshness by dataset",
        responses=inline_serializer(
            name="DataFreshnessResponse",
            fields={
                "generated_at": serializers.DateTimeField(),
                "datasets": serializers.ListField(child=serializers.DictField()),
            },
        ),
    )
    def get(self, request: Request) -> Response:
        from django.utils import timezone

        entries = data_freshness()
        return Response(
            {
                "generated_at": timezone.now().isoformat(),
                "datasets": [e.to_dict() for e in entries],
            }
        )


class ExternalServicesView(APIView):
    """External provider health. Never returns API keys — only a configured flag."""

    authentication_classes: list = []
    permission_classes: list = []

    @extend_schema(
        summary="External service health",
        responses=inline_serializer(
            name="ExternalServicesResponse",
            fields={
                "generated_at": serializers.DateTimeField(),
                "services": serializers.ListField(child=serializers.DictField()),
            },
        ),
    )
    def get(self, request: Request) -> Response:
        from django.utils import timezone

        services = external_services()
        return Response(
            {
                "generated_at": timezone.now().isoformat(),
                "services": [s.to_dict() for s in services],
            }
        )

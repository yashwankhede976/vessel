"""Health-check endpoint.

Minimal endpoint used to verify the backend starts and can serve requests.
It performs no business logic. See docs/ARCHITECTURE.md.
"""
from django.conf import settings
from drf_spectacular.utils import OpenApiExample, extend_schema, inline_serializer
from rest_framework import serializers
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView


class HealthView(APIView):
    """Return basic service status."""

    # Health is a public liveness endpoint; no auth required.
    authentication_classes: list = []
    permission_classes: list = []

    @extend_schema(
        summary="Service health check",
        description="Liveness probe. Returns service status and environment.",
        responses=inline_serializer(
            name="HealthResponse",
            fields={
                "status": serializers.CharField(),
                "service": serializers.CharField(),
                "environment": serializers.CharField(),
            },
        ),
        examples=[
            OpenApiExample(
                "Healthy",
                value={
                    "success": True,
                    "data": {
                        "status": "ok",
                        "service": "vessel-backend",
                        "environment": "development",
                    },
                    "errors": None,
                },
            )
        ],
    )
    def get(self, request: Request) -> Response:
        return Response(
            {
                "status": "ok",
                "service": "vessel-backend",
                "environment": settings.DJANGO_ENV,
            }
        )

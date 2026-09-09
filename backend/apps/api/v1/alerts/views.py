"""Alerts API (v1): list/retrieve + acknowledge/resolve lifecycle actions."""
from __future__ import annotations

from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from django.utils import timezone

from apps.alerts.models import Alert, AlertStatus

from .serializers import AlertSerializer


class AlertViewSet(viewsets.ReadOnlyModelViewSet):
    """List and retrieve alerts; acknowledge / resolve via extra actions.

    Filter by ?status=, ?alert_type=, ?severity=. Ordered newest-first.
    """

    serializer_class = AlertSerializer
    queryset = Alert.objects.all().prefetch_related("notifications")
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["status", "alert_type", "severity"]
    ordering = ["-timestamp"]

    # Public read/lifecycle endpoint, consistent with the rest of the API.
    authentication_classes: list = []
    permission_classes: list = []

    @extend_schema(summary="Acknowledge an alert", request=None, responses=AlertSerializer)
    @action(detail=True, methods=["post"])
    def acknowledge(self, request, pk=None):
        alert = self.get_object()
        if alert.status == AlertStatus.RESOLVED:
            return Response(
                {"success": False, "data": None,
                 "errors": [{"code": "invalid_state",
                             "detail": "A resolved alert cannot be acknowledged."}]},
                status=status.HTTP_400_BAD_REQUEST,
            )
        alert.status = AlertStatus.ACKNOWLEDGED
        alert.acknowledged_at = timezone.now()
        alert.save(update_fields=["status", "acknowledged_at", "updated_at"])
        return Response(self.get_serializer(alert).data)

    @extend_schema(summary="Resolve an alert", request=None, responses=AlertSerializer)
    @action(detail=True, methods=["post"])
    def resolve(self, request, pk=None):
        alert = self.get_object()
        alert.status = AlertStatus.RESOLVED
        alert.resolved_at = timezone.now()
        alert.save(update_fields=["status", "resolved_at", "updated_at"])
        return Response(self.get_serializer(alert).data)

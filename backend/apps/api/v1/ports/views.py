"""Read-only viewsets for the ports domain (ports & berths).

Endpoints (mounted under /api/v1/ports/):
- GET ports/               list ports (filter by coast, commodity, type, country)
- GET ports/{id}/          retrieve a port (with berths)
- GET ports/{id}/constraints/  retrieve a port's aggregated constraints
- GET ports/berths/        list berths (filter by port, commodity)
- GET ports/berths/{id}/   retrieve a berth

No vessel-compatibility logic is implemented here.
"""
from __future__ import annotations

import django_filters as filters
from django.db.models import Count, Prefetch
from drf_spectacular.utils import extend_schema
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.catalog.models import Berth, Port

from .filters import PortFilter
from .serializers import (
    BerthSerializer,
    PortConstraintsSerializer,
    PortDetailSerializer,
    PortSerializer,
)


class PortViewSet(viewsets.ReadOnlyModelViewSet):
    """List and retrieve ports; filter by coast and commodity."""

    filterset_class = PortFilter
    ordering_fields = ["name", "coast", "created_at"]
    ordering = ["name"]
    search_fields = ["name", "unlocode", "country"]

    def get_queryset(self):
        qs = Port.objects.all().annotate(berth_count=Count("berths", distinct=True))
        if self.action in ("retrieve",):
            qs = qs.prefetch_related(
                Prefetch(
                    "berths",
                    queryset=Berth.objects.prefetch_related("supported_commodities"),
                )
            )
        if self.action == "constraints":
            qs = qs.prefetch_related("berths__supported_commodities")
        return qs

    def get_serializer_class(self):
        if self.action == "retrieve":
            return PortDetailSerializer
        if self.action == "constraints":
            return PortConstraintsSerializer
        return PortSerializer

    @extend_schema(
        summary="Retrieve port constraints",
        responses=PortConstraintsSerializer,
    )
    @action(detail=True, methods=["get"])
    def constraints(self, request, pk=None):
        """Aggregated physical/operational constraints for a port."""
        port = self.get_object()
        serializer = self.get_serializer(port)
        return Response(serializer.data)


class BerthFilter(filters.FilterSet):
    port = filters.NumberFilter(field_name="port_id")
    commodity = filters.CharFilter(
        field_name="supported_commodities__name", lookup_expr="iexact"
    )

    class Meta:
        model = Berth
        fields = ["port", "commodity"]


class BerthViewSet(viewsets.ReadOnlyModelViewSet):
    """List and retrieve berths."""

    serializer_class = BerthSerializer
    filterset_class = BerthFilter
    ordering_fields = ["berth_name", "max_draft", "created_at"]
    ordering = ["port__name", "berth_name"]
    search_fields = ["berth_name", "port__name"]

    def get_queryset(self):
        return (
            Berth.objects.select_related("port")
            .prefetch_related("supported_commodities")
            .all()
        )

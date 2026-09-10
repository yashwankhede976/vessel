"""Read-only viewset for the routes (trade lanes) domain.

Endpoints (mounted under /api/v1/routes/):
- GET routes/          list trade lanes with resolved endpoint coordinates
- GET routes/{id}/     retrieve a single trade lane

Purpose: supply the frontend map with drawable origin -> destination voyage
lines for cargo ships. All coordinates are REAL stored values; routes whose
endpoints lack coordinates are returned with drawable=false (never invented).
"""
from __future__ import annotations

import django_filters as filters
from rest_framework import viewsets

from apps.catalog.models import Route

from .serializers import RouteSerializer


class RouteFilter(filters.FilterSet):
    origin = filters.CharFilter(field_name="origin__name", lookup_expr="iexact")
    destination = filters.CharFilter(
        field_name="destination_port__name", lookup_expr="iexact"
    )

    class Meta:
        model = Route
        fields = ["origin", "destination"]


class RouteViewSet(viewsets.ReadOnlyModelViewSet):
    """List and retrieve trade lanes (voyage routes) for map rendering."""

    serializer_class = RouteSerializer
    filterset_class = RouteFilter
    ordering_fields = ["distance_nm", "typical_transit_days"]
    ordering = ["origin__name", "destination_port__name"]
    search_fields = ["origin__name", "destination_port__name"]

    def get_queryset(self):
        return Route.objects.select_related(
            "origin", "origin__load_port", "destination_port"
        ).all()

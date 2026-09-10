"""Read-only viewsets for the vessels domain.

Endpoints (mounted under /api/v1/vessels/):
- GET vessels/                list vessels (filter by type, DWT, draft, position,
                              availability; paginated, orderable, searchable)
- GET vessels/{id}/           retrieve a vessel (with latest position)
- GET vessels/available/      list vessels that are currently open/available

No recommendation or scoring logic is implemented here.
"""
from __future__ import annotations

from decimal import Decimal

from django.db.models import Count, DecimalField, OuterRef, Q, Subquery, Sum
from drf_spectacular.utils import extend_schema
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.catalog.models import Vessel
from apps.operations.models import AISPosition

from .filters import VesselFilter
from .serializers import VesselDetailSerializer, VesselSerializer


class VesselViewSet(viewsets.ReadOnlyModelViewSet):
    """List and retrieve vessels; filter by type, DWT, draft, position."""

    filterset_class = VesselFilter
    ordering_fields = ["name", "dwt", "draft", "year_built", "open_date"]
    ordering = ["name"]
    search_fields = ["name", "imo", "mmsi", "flag"]

    def get_queryset(self):
        # Latest AIS position per vessel via correlated subqueries so we can
        # both filter (bounding box) and serialize without N+1 queries.
        latest = AISPosition.objects.filter(vessel=OuterRef("pk")).order_by(
            "-timestamp"
        )
        return Vessel.objects.annotate(
            latest_lat=Subquery(
                latest.values("latitude")[:1],
                output_field=DecimalField(max_digits=9, decimal_places=6),
            ),
            latest_lon=Subquery(
                latest.values("longitude")[:1],
                output_field=DecimalField(max_digits=9, decimal_places=6),
            ),
        )

    def get_serializer_class(self):
        if self.action == "retrieve":
            return VesselDetailSerializer
        return VesselSerializer

    def _attach_latest_positions(self, vessels):
        """Attach the latest AISPosition object to each vessel (one query)."""
        ids = [v.pk for v in vessels]
        latest_by_vessel: dict[int, AISPosition] = {}
        # Iterate newest-first; keep the first (latest) seen per vessel.
        for pos in AISPosition.objects.filter(vessel_id__in=ids).order_by(
            "vessel_id", "-timestamp"
        ):
            latest_by_vessel.setdefault(pos.vessel_id, pos)
        for vessel in vessels:
            vessel._latest_position = latest_by_vessel.get(vessel.pk)
        return vessels

    def _list_response(self, queryset):
        """Paginate + serialize a vessel queryset, attaching latest positions."""
        page = self.paginate_queryset(queryset)
        if page is not None:
            self._attach_latest_positions(page)
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        vessels = list(queryset)
        self._attach_latest_positions(vessels)
        serializer = self.get_serializer(vessels, many=True)
        return Response(serializer.data)

    def list(self, request, *args, **kwargs):
        return self._list_response(self.filter_queryset(self.get_queryset()))

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        self._attach_latest_positions([instance])
        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    @extend_schema(summary="List available (open) vessels", responses=VesselSerializer)
    @action(detail=False, methods=["get"])
    def available(self, request):
        """Vessels currently open/available for employment."""
        queryset = self.filter_queryset(
            self.get_queryset().filter(
                availability_status=Vessel.AvailabilityStatus.OPEN
            )
        )
        return self._list_response(queryset)

    @extend_schema(summary="Vessel availability summary by vessel type")
    @action(detail=False, methods=["get"], url_path="availability-summary")
    def availability_summary(self, request):
        """Aggregate the fleet by vessel type, breaking each type down by
        availability status. Every number here is a real COUNT/SUM over the
        Vessel table — nothing is estimated. `open_dwt` is the summed DWT of the
        OPEN vessels of that type (chartering-relevant capacity that can be
        fixed now).

        Filters from the list endpoint apply, so e.g. ?dwt_min=60000 restricts
        the summary to the matching vessels.
        """
        qs = self.filter_queryset(Vessel.objects.all())

        status_field = "availability_status"
        # One grouped query: counts per (vessel_type, status) + per-type totals
        # and open DWT via conditional aggregation.
        rows = (
            qs.values("vessel_type")
            .annotate(
                total=Count("id"),
                open=Count("id", filter=Q(**{status_field: Vessel.AvailabilityStatus.OPEN})),
                laden=Count("id", filter=Q(**{status_field: Vessel.AvailabilityStatus.LADEN})),
                ballast=Count("id", filter=Q(**{status_field: Vessel.AvailabilityStatus.BALLAST})),
                fixed=Count("id", filter=Q(**{status_field: Vessel.AvailabilityStatus.FIXED})),
                unknown=Count("id", filter=Q(**{status_field: Vessel.AvailabilityStatus.UNKNOWN})),
                open_dwt=Sum("dwt", filter=Q(**{status_field: Vessel.AvailabilityStatus.OPEN})),
            )
            .order_by("vessel_type")
        )

        type_labels = dict(Vessel.VesselType.choices)
        by_type = [
            {
                "vessel_type": r["vessel_type"],
                "vessel_type_display": type_labels.get(r["vessel_type"], r["vessel_type"]),
                "total": r["total"],
                "open": r["open"],
                "laden": r["laden"],
                "ballast": r["ballast"],
                "fixed": r["fixed"],
                "unknown": r["unknown"],
                "open_dwt": str(
                    (r["open_dwt"] if r["open_dwt"] is not None else Decimal("0")).quantize(
                        Decimal("0.01")
                    )
                ),
            }
            for r in rows
        ]

        totals = {
            "total": sum(r["total"] for r in by_type),
            "open": sum(r["open"] for r in by_type),
            "laden": sum(r["laden"] for r in by_type),
            "ballast": sum(r["ballast"] for r in by_type),
            "fixed": sum(r["fixed"] for r in by_type),
            "unknown": sum(r["unknown"] for r in by_type),
        }

        return Response({"by_type": by_type, "totals": totals})

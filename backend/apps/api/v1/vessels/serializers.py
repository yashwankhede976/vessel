"""Serializers for the vessels domain.

Return clean, frontend-ready JSON including the vessel's latest known AIS
position and availability. No recommendation/scoring logic here.
"""
from __future__ import annotations

from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.catalog.models import Vessel


class LatestPositionSerializer(serializers.Serializer):
    """The most recent AIS position for a vessel (read-only, nested)."""

    latitude = serializers.DecimalField(max_digits=9, decimal_places=6)
    longitude = serializers.DecimalField(max_digits=9, decimal_places=6)
    sog = serializers.DecimalField(
        max_digits=5, decimal_places=2, allow_null=True
    )
    cog = serializers.DecimalField(
        max_digits=5, decimal_places=2, allow_null=True
    )
    heading = serializers.DecimalField(
        max_digits=5, decimal_places=2, allow_null=True
    )
    nav_status = serializers.CharField()
    timestamp = serializers.DateTimeField()


class VesselSerializer(serializers.ModelSerializer):
    """List/summary representation of a vessel."""

    vessel_type_display = serializers.CharField(
        source="get_vessel_type_display", read_only=True
    )
    availability_status_display = serializers.CharField(
        source="get_availability_status_display", read_only=True
    )
    latest_position = serializers.SerializerMethodField()

    class Meta:
        model = Vessel
        fields = [
            "id",
            "imo",
            "mmsi",
            "name",
            "vessel_type",
            "vessel_type_display",
            "dwt",
            "loa",
            "beam",
            "draft",
            "flag",
            "year_built",
            "speed",
            "availability_status",
            "availability_status_display",
            "open_date",
            "metadata",
            "latest_position",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    @extend_schema_field(LatestPositionSerializer)
    def get_latest_position(self, vessel: Vessel):
        # `latest_position` is attached by the view (annotated/prefetched) to
        # avoid N+1 queries; fall back to a query only if absent.
        position = getattr(vessel, "_latest_position", "unset")
        if position == "unset":
            position = vessel.positions.order_by("-timestamp").first()
        if position is None:
            return None
        return LatestPositionSerializer(position).data


class VesselDetailSerializer(VesselSerializer):
    """Detail representation of a vessel (same fields for now)."""

    class Meta(VesselSerializer.Meta):
        pass

"""Serializer for the routes (trade lanes) domain.

Exposes each Route as a drawable voyage: the resolved origin coordinates (from
the origin's representative load port) and destination-port coordinates, plus
the stored distance and typical transit. Coordinates are REAL stored values;
when an endpoint has no coordinate (e.g. an origin without a load port) the
route is marked not drawable rather than having a coordinate invented.
"""
from __future__ import annotations

from rest_framework import serializers

from apps.catalog.models import Route


class RouteSerializer(serializers.ModelSerializer):
    """A trade lane with resolved endpoint coordinates for map rendering."""

    origin_name = serializers.CharField(source="origin.name", read_only=True)
    origin_country = serializers.CharField(source="origin.country", read_only=True)
    destination_name = serializers.CharField(
        source="destination_port.name", read_only=True
    )
    destination_country = serializers.CharField(
        source="destination_port.country", read_only=True
    )

    # Resolved endpoint coordinates (may be null when unavailable).
    origin_latitude = serializers.SerializerMethodField()
    origin_longitude = serializers.SerializerMethodField()
    origin_port_name = serializers.SerializerMethodField()
    destination_latitude = serializers.DecimalField(
        source="destination_port.latitude", max_digits=9, decimal_places=6, read_only=True
    )
    destination_longitude = serializers.DecimalField(
        source="destination_port.longitude", max_digits=9, decimal_places=6, read_only=True
    )

    drawable = serializers.SerializerMethodField()

    class Meta:
        model = Route
        fields = [
            "id",
            "origin_name",
            "origin_country",
            "origin_port_name",
            "origin_latitude",
            "origin_longitude",
            "destination_name",
            "destination_country",
            "destination_latitude",
            "destination_longitude",
            "distance_nm",
            "typical_transit_days",
            "drawable",
        ]
        read_only_fields = fields

    def _load_port(self, route: Route):
        return getattr(route.origin, "load_port", None)

    def get_origin_port_name(self, route: Route):
        lp = self._load_port(route)
        return lp.name if lp else None

    def get_origin_latitude(self, route: Route):
        lp = self._load_port(route)
        return str(lp.latitude) if lp else None

    def get_origin_longitude(self, route: Route):
        lp = self._load_port(route)
        return str(lp.longitude) if lp else None

    def get_drawable(self, route: Route) -> bool:
        """A route is drawable only when BOTH endpoints have coordinates."""
        lp = self._load_port(route)
        return bool(lp and route.destination_port)

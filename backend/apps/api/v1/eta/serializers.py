"""Serializers for the ETA endpoint (v1)."""
from rest_framework import serializers


class ETARequestSerializer(serializers.Serializer):
    """Direct ETA inputs. Impossible values are rejected by the engine."""

    route_distance_nm = serializers.FloatField(min_value=0.0, required=True)
    speed_kn = serializers.FloatField(min_value=0.0, required=True)
    latitude = serializers.FloatField(
        required=False, min_value=-90.0, max_value=90.0, allow_null=True
    )
    longitude = serializers.FloatField(
        required=False, min_value=-180.0, max_value=180.0, allow_null=True
    )
    weather_risk = serializers.FloatField(
        required=False, min_value=0.0, max_value=1.0, default=0.0
    )
    destination_congestion = serializers.FloatField(
        required=False, min_value=0.0, max_value=100.0, default=0.0
    )
    expected_port_waiting_days = serializers.FloatField(
        required=False, min_value=0.0, default=0.0
    )

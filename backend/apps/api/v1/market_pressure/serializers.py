"""Serializers for the market-pressure endpoint (v1)."""
from rest_framework import serializers


class MarketPressureRequestSerializer(serializers.Serializer):
    """Signals for the Freight Market Pressure Index. All optional; any omitted
    signal is excluded from the weighting (never fabricated)."""

    vessel_supply = serializers.FloatField(
        required=False, min_value=0.0, max_value=1.0, allow_null=True
    )
    cargo_demand = serializers.FloatField(
        required=False, min_value=0.0, max_value=1.0, allow_null=True
    )
    freight_volatility = serializers.FloatField(
        required=False, min_value=0.0, max_value=1.0, allow_null=True
    )
    port_congestion = serializers.FloatField(
        required=False, min_value=0.0, max_value=100.0, allow_null=True
    )
    ton_mile_demand = serializers.FloatField(
        required=False, min_value=0.0, max_value=1.0, allow_null=True
    )
    bunker = serializers.FloatField(
        required=False, min_value=0.0, max_value=1.0, allow_null=True
    )
    seasonality = serializers.FloatField(
        required=False, min_value=0.0, max_value=1.0, allow_null=True
    )

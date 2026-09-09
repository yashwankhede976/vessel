"""Serializers for the risk endpoint (v1)."""
from rest_framework import serializers


class RiskRequestSerializer(serializers.Serializer):
    """Risk signals. All optional; any omitted signal stays UNKNOWN (never
    invented) and is excluded from the score."""

    freight_volatility = serializers.FloatField(
        required=False, min_value=0.0, max_value=1.0, allow_null=True
    )
    port_congestion = serializers.FloatField(
        required=False, min_value=0.0, max_value=100.0, allow_null=True
    )
    weather_risk = serializers.FloatField(
        required=False, min_value=0.0, max_value=1.0, allow_null=True
    )
    eta_delay_probability = serializers.FloatField(
        required=False, min_value=0.0, max_value=1.0, allow_null=True
    )
    expected_demurrage_cost = serializers.FloatField(
        required=False, min_value=0.0, allow_null=True
    )
    commodity_volatility = serializers.FloatField(
        required=False, min_value=0.0, max_value=1.0, allow_null=True
    )
    fx_volatility = serializers.FloatField(
        required=False, min_value=0.0, max_value=1.0, allow_null=True
    )
    geopolitical_risk = serializers.FloatField(
        required=False, min_value=0.0, max_value=1.0, allow_null=True
    )

"""Serializers for the fix-wait endpoint (v1)."""
from rest_framework import serializers


class FixWaitRequestSerializer(serializers.Serializer):
    """Inputs for the FIX_NOW / WAIT / PARTIAL_FIX / MONITOR timing decision."""

    current_rate = serializers.DecimalField(
        max_digits=12, decimal_places=2, required=True
    )
    forecast_7d = serializers.DecimalField(
        max_digits=12, decimal_places=2, required=False, allow_null=True
    )
    forecast_14d = serializers.DecimalField(
        max_digits=12, decimal_places=2, required=False, allow_null=True
    )
    forecast_30d = serializers.DecimalField(
        max_digits=12, decimal_places=2, required=False, allow_null=True
    )
    confidence_7d = serializers.FloatField(
        required=False, min_value=0.0, max_value=1.0, allow_null=True
    )
    confidence_14d = serializers.FloatField(
        required=False, min_value=0.0, max_value=1.0, allow_null=True
    )
    confidence_30d = serializers.FloatField(
        required=False, min_value=0.0, max_value=1.0, allow_null=True
    )
    days_to_deadline = serializers.IntegerField(
        required=False, min_value=0, allow_null=True
    )
    vessel_availability = serializers.FloatField(
        required=False, min_value=0.0, max_value=1.0, allow_null=True
    )
    congestion_score = serializers.FloatField(
        required=False, min_value=0.0, max_value=100.0, allow_null=True
    )
    freight_volatility = serializers.FloatField(
        required=False, min_value=0.0, max_value=1.0, allow_null=True
    )

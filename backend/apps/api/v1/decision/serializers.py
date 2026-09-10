"""Serializers for the unified decision endpoint (v1)."""
from decimal import Decimal

from rest_framework import serializers


class ScenarioSerializer(serializers.Serializer):
    """Stateless what-if overrides. All optional."""

    freight_change_pct = serializers.FloatField(required=False, allow_null=True)
    congestion_score = serializers.FloatField(
        required=False, min_value=0.0, max_value=100.0, allow_null=True
    )
    vessel_availability = serializers.FloatField(
        required=False, min_value=0.0, max_value=1.0, allow_null=True
    )


class DecisionRequestSerializer(serializers.Serializer):
    """A chartering requirement for the unified decision endpoint."""

    commodity = serializers.CharField(required=True)
    cargo_quantity = serializers.DecimalField(
        max_digits=12, decimal_places=2, min_value=Decimal("1"), required=True
    )
    origin = serializers.CharField(required=True)
    destination = serializers.CharField(required=True)
    laycan_start = serializers.DateField(required=True)
    laycan_end = serializers.DateField(required=True)
    required_arrival = serializers.DateField(required=False, allow_null=True)
    currency = serializers.CharField(required=False, default="USD")
    scenario = ScenarioSerializer(required=False)

    def validate(self, attrs):
        if attrs["laycan_end"] < attrs["laycan_start"]:
            raise serializers.ValidationError(
                {"laycan_end": "laycan_end cannot be before laycan_start."}
            )
        return attrs


class AssistantRequestSerializer(serializers.Serializer):
    """A free-text question for the assistant."""

    question = serializers.CharField(required=True)

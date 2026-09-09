"""Serializers for the idle-vessel endpoint (v1)."""
from decimal import Decimal

from rest_framework import serializers


class EmploymentOpportunitySerializer(serializers.Serializer):
    """One candidate next-voyage opportunity for the idle vessel."""

    name = serializers.CharField(required=True)
    laden_distance_nm = serializers.DecimalField(
        max_digits=10, decimal_places=2, min_value=Decimal("0.01"), required=True
    )
    cargo_tonnes = serializers.DecimalField(
        max_digits=12, decimal_places=2, min_value=Decimal("0.01"), required=True
    )
    freight_rate_per_tonne = serializers.DecimalField(
        max_digits=12, decimal_places=2, min_value=Decimal("0"), required=True
    )
    ballast_distance_nm = serializers.DecimalField(
        max_digits=10, decimal_places=2, min_value=Decimal("0"),
        required=False, allow_null=True,
    )
    discharge_port_id = serializers.IntegerField(required=False, allow_null=True)
    commodity = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    port_cost = serializers.DecimalField(
        max_digits=14, decimal_places=2, min_value=Decimal("0"),
        required=False, allow_null=True,
    )
    bunker_price_per_tonne = serializers.DecimalField(
        max_digits=12, decimal_places=2, min_value=Decimal("0"),
        required=False, allow_null=True,
    )


class IdleVesselRequestSerializer(serializers.Serializer):
    """Rank next-voyage opportunities for an open vessel."""

    vessel_id = serializers.IntegerField(required=True)
    opportunities = EmploymentOpportunitySerializer(many=True)
    currency = serializers.CharField(required=False, default="USD")

    def validate_opportunities(self, value):
        if not value:
            raise serializers.ValidationError("At least one opportunity is required.")
        return value

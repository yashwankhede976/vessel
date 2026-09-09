"""Serializers for the optimization endpoint (v1)."""
from decimal import Decimal

from rest_framework import serializers


class CandidateVoyageSerializer(serializers.Serializer):
    """One candidate voyage the solver may select 0..max_voyages times."""

    id = serializers.CharField(required=True)
    origin = serializers.CharField(required=True)
    destination = serializers.CharField(required=True)
    vessel_type = serializers.CharField(required=True)
    contract_strategy = serializers.CharField(required=False, default="SPOT")
    cost_per_voyage = serializers.DecimalField(
        max_digits=16, decimal_places=2, min_value=Decimal("0"), required=True
    )
    capacity_tonnes = serializers.DecimalField(
        max_digits=12, decimal_places=2, min_value=Decimal("0.01"), required=True
    )
    max_voyages = serializers.IntegerField(required=False, min_value=0, default=1)
    feasible_in_laycan = serializers.BooleanField(required=False, default=True)
    is_compatible = serializers.BooleanField(required=False, default=True)


class OptimizationRequestSerializer(serializers.Serializer):
    """Multi-voyage procurement optimization request."""

    required_tonnes = serializers.DecimalField(
        max_digits=14, decimal_places=2, min_value=Decimal("1"), required=True
    )
    candidates = CandidateVoyageSerializer(many=True)
    tolerance_pct = serializers.DecimalField(
        max_digits=5, decimal_places=2, min_value=Decimal("0"),
        max_value=Decimal("100"), required=False, default=Decimal("0"),
    )
    currency = serializers.CharField(required=False, default="USD")
    destination_capacity = serializers.DictField(
        child=serializers.FloatField(), required=False
    )
    origin_min_tonnes = serializers.DictField(
        child=serializers.FloatField(), required=False
    )
    origin_max_tonnes = serializers.DictField(
        child=serializers.FloatField(), required=False
    )
    contract_min_voyages = serializers.DictField(
        child=serializers.IntegerField(), required=False
    )
    contract_max_voyages = serializers.DictField(
        child=serializers.IntegerField(), required=False
    )
    time_limit_ms = serializers.IntegerField(
        required=False, min_value=100, max_value=60000, default=5000
    )

    def validate_candidates(self, value):
        if not value:
            raise serializers.ValidationError("At least one candidate is required.")
        return value

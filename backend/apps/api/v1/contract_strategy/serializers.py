"""Serializers for the contract-strategy endpoints (v1)."""
from decimal import Decimal

from rest_framework import serializers


class SpotVsContractRequestSerializer(serializers.Serializer):
    """Inputs to compare SPOT / SHORT_TERM / MEDIUM_TERM / MULTI_VOYAGE."""

    spot_freight_per_tonne = serializers.DecimalField(
        max_digits=12, decimal_places=2, min_value=Decimal("0"), required=True
    )
    cargo_tonnes = serializers.DecimalField(
        max_digits=12, decimal_places=2, min_value=Decimal("1"), required=True
    )
    freight_volatility = serializers.FloatField(
        required=False, min_value=0.0, max_value=1.0, allow_null=True
    )
    base_demurrage_cost = serializers.DecimalField(
        max_digits=14, decimal_places=2, min_value=Decimal("0"),
        required=False, allow_null=True,
    )
    non_freight_cost = serializers.DecimalField(
        max_digits=16, decimal_places=2, min_value=Decimal("0"),
        required=False, allow_null=True,
    )
    congestion_score = serializers.FloatField(
        required=False, min_value=0.0, max_value=100.0, allow_null=True
    )
    currency = serializers.CharField(required=False, default="USD")


class ContractPortfolioRequestSerializer(serializers.Serializer):
    """Inputs to build a diversified contract portfolio for a multi-month need."""

    total_tonnes = serializers.DecimalField(
        max_digits=14, decimal_places=2, min_value=Decimal("1"), required=True
    )
    spot_freight_per_tonne = serializers.DecimalField(
        max_digits=12, decimal_places=2, min_value=Decimal("0"), required=True
    )
    market_pressure_index = serializers.FloatField(
        required=False, min_value=0.0, max_value=100.0, allow_null=True
    )
    freight_volatility = serializers.FloatField(
        required=False, min_value=0.0, max_value=1.0, allow_null=True
    )
    currency = serializers.CharField(required=False, default="USD")

"""Serializers for the alternative-port endpoint (v1)."""
from decimal import Decimal

from rest_framework import serializers


class AlternativePortRequestSerializer(serializers.Serializer):
    """Compare East Coast alternatives for a requested destination."""

    origin = serializers.CharField(required=True)
    requested_destination = serializers.CharField(required=True)
    cargo_tonnes = serializers.DecimalField(
        max_digits=12, decimal_places=2, min_value=Decimal("1"), required=True
    )
    commodity = serializers.CharField(required=True)
    vessel_id = serializers.IntegerField(required=False, allow_null=True)
    bunker_price_per_tonne = serializers.DecimalField(
        max_digits=12, decimal_places=2, min_value=Decimal("0"),
        required=False, allow_null=True,
    )
    freight_rate_per_tonne = serializers.DecimalField(
        max_digits=12, decimal_places=2, min_value=Decimal("0"),
        required=False, allow_null=True,
    )
    currency = serializers.CharField(required=False, default="USD")

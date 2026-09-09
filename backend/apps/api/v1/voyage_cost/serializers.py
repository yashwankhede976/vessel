"""Serializers for the voyage-cost endpoint (v1)."""
from decimal import Decimal

from rest_framework import serializers


class VoyageCostRequestSerializer(serializers.Serializer):
    """Inputs for the voyage economics engine. Optional cost components default
    to 0; either freight_cost or freight_rate_per_tonne may be supplied."""

    distance_nm = serializers.DecimalField(
        max_digits=10, decimal_places=2, min_value=Decimal("0.01"), required=True
    )
    speed_kn = serializers.DecimalField(
        max_digits=6, decimal_places=2, min_value=Decimal("0.01"), required=True
    )
    cargo_tonnes = serializers.DecimalField(
        max_digits=12, decimal_places=2, min_value=Decimal("0"), required=True
    )
    bunker_rate_tpd = serializers.DecimalField(
        max_digits=10, decimal_places=2, min_value=Decimal("0"), required=False
    )
    bunker_price_per_tonne = serializers.DecimalField(
        max_digits=12, decimal_places=2, min_value=Decimal("0"), required=False
    )
    bunker_idle_rate_tpd = serializers.DecimalField(
        max_digits=10, decimal_places=2, min_value=Decimal("0"),
        required=False, allow_null=True,
    )
    port_days = serializers.DecimalField(
        max_digits=8, decimal_places=2, min_value=Decimal("0"), required=False
    )
    port_cost = serializers.DecimalField(
        max_digits=16, decimal_places=2, min_value=Decimal("0"), required=False
    )
    freight_cost = serializers.DecimalField(
        max_digits=16, decimal_places=2, min_value=Decimal("0"),
        required=False, allow_null=True,
    )
    freight_rate_per_tonne = serializers.DecimalField(
        max_digits=12, decimal_places=2, min_value=Decimal("0"),
        required=False, allow_null=True,
    )
    canal_cost = serializers.DecimalField(
        max_digits=16, decimal_places=2, min_value=Decimal("0"), required=False
    )
    misc_cost = serializers.DecimalField(
        max_digits=16, decimal_places=2, min_value=Decimal("0"), required=False
    )
    demurrage_rate_per_day = serializers.DecimalField(
        max_digits=12, decimal_places=2, min_value=Decimal("0"),
        required=False, allow_null=True,
    )
    expected_demurrage_days = serializers.DecimalField(
        max_digits=8, decimal_places=2, min_value=Decimal("0"),
        required=False, allow_null=True,
    )
    estimated_demurrage = serializers.DecimalField(
        max_digits=16, decimal_places=2, min_value=Decimal("0"),
        required=False, allow_null=True,
    )
    currency = serializers.CharField(required=False, default="USD")

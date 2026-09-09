"""Serializers for the landed-cost endpoints (v1)."""
from decimal import Decimal

from rest_framework import serializers

COMPONENT_FIELDS = [
    "commodity_cost", "freight_cost", "bunker_cost", "port_charges",
    "handling_cost", "demurrage_cost", "insurance_other_cost",
]


class CostComponentSerializer(serializers.Serializer):
    """A single cost component in its source currency."""

    amount = serializers.DecimalField(
        max_digits=16, decimal_places=2, min_value=Decimal("0"), allow_null=True
    )
    currency = serializers.CharField(required=False, default="USD")


class LandedCostRequestSerializer(serializers.Serializer):
    """One origin->destination landed-cost request."""

    origin = serializers.CharField(required=True)
    destination = serializers.CharField(required=True)
    cargo_tonnes = serializers.DecimalField(
        max_digits=12, decimal_places=2, min_value=Decimal("1"), required=True
    )

    commodity_cost = CostComponentSerializer(required=False)
    freight_cost = CostComponentSerializer(required=False)
    bunker_cost = CostComponentSerializer(required=False)
    port_charges = CostComponentSerializer(required=False)
    handling_cost = CostComponentSerializer(required=False)
    demurrage_cost = CostComponentSerializer(required=False)
    insurance_other_cost = CostComponentSerializer(required=False)

    target_currency = serializers.CharField(required=False, default="USD")
    # FX rates: {source_currency: rate_to_target}. Missing rate for a non-target
    # currency is an error in the engine (rates are never assumed).
    fx_rates = serializers.DictField(
        child=serializers.DecimalField(max_digits=18, decimal_places=6),
        required=False,
    )


class LandedCostCompareRequestSerializer(serializers.Serializer):
    """Compare several origins for the SAME destination + target currency."""

    inputs = LandedCostRequestSerializer(many=True)

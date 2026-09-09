"""Serializers for the recommendations domain API (v1)."""
from decimal import Decimal

from rest_framework import serializers


class VesselRecommendationRequestSerializer(serializers.Serializer):
    """Validates the body of POST /recommendations/vessels/.

    A chartering requirement: where the cargo comes from and goes to, how much,
    of what, and the delivery (laycan) window.
    """

    origin = serializers.CharField(required=True)
    destination = serializers.CharField(required=True)
    cargo_tonnes = serializers.DecimalField(
        max_digits=12, decimal_places=2, min_value=Decimal("1"), required=True
    )
    commodity = serializers.CharField(required=True)
    laycan_start = serializers.DateField(required=True)
    laycan_end = serializers.DateField(required=True)

    # Optional overrides.
    currency = serializers.CharField(required=False, default="USD")
    bunker_price_per_tonne = serializers.DecimalField(
        max_digits=12, decimal_places=2, min_value=Decimal("0"),
        required=False, allow_null=True,
    )
    # Restrict candidates to currently open/available vessels (default: True).
    only_available = serializers.BooleanField(required=False, default=True)

    def validate(self, attrs):
        if attrs["laycan_end"] < attrs["laycan_start"]:
            raise serializers.ValidationError(
                {"laycan_end": "laycan_end cannot be before laycan_start."}
            )
        return attrs

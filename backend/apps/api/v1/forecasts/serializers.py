"""Serializers for the freight forecast endpoint.

The freight-forecast endpoint returns a composed payload (not a single model),
so these serializers shape the request query params and the nested response
sections rather than mapping one model.
"""
from __future__ import annotations

from rest_framework import serializers

from apps.catalog.models import Vessel
from apps.operations.models import FreightForecast


class FreightForecastQuerySerializer(serializers.Serializer):
    """Validates the query parameters for GET /forecasts/freight/."""

    origin = serializers.CharField(required=True)
    destination = serializers.CharField(required=True)
    vessel_type = serializers.ChoiceField(
        choices=Vessel.VesselType.choices, required=False
    )
    horizon = serializers.ChoiceField(
        choices=FreightForecast.Horizon.choices, required=False
    )
    # How many days of history to include (bounded).
    history_days = serializers.IntegerField(
        required=False, min_value=1, max_value=730, default=180
    )


class HistoricalPointSerializer(serializers.Serializer):
    date = serializers.DateField(source="observed_on")
    rate_per_tonne = serializers.DecimalField(max_digits=12, decimal_places=2)
    currency = serializers.CharField()
    rate_type = serializers.CharField()
    is_estimated = serializers.BooleanField()
    source = serializers.CharField(allow_blank=True)


class ForecastPointSerializer(serializers.Serializer):
    target_date = serializers.DateField()
    horizon = serializers.CharField()
    predicted_rate_per_tonne = serializers.DecimalField(max_digits=12, decimal_places=2)
    lower_bound = serializers.DecimalField(
        max_digits=12, decimal_places=2, allow_null=True
    )
    upper_bound = serializers.DecimalField(
        max_digits=12, decimal_places=2, allow_null=True
    )
    confidence = serializers.DecimalField(
        max_digits=4, decimal_places=3, allow_null=True
    )
    currency = serializers.CharField()

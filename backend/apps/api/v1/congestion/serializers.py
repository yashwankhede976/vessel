"""Serializers for the congestion-forecast endpoint (v1)."""
from rest_framework import serializers

WEATHER_CHOICES = ["none", "low", "moderate", "high", "severe"]


class CongestionForecastRequestSerializer(serializers.Serializer):
    """Current-state congestion signals + optional trend, for the 1/3/7/14-day
    forecast. Any omitted signal is excluded (never fabricated)."""

    vessels_near_port = serializers.IntegerField(
        required=False, min_value=0, allow_null=True
    )
    vessels_waiting = serializers.IntegerField(
        required=False, min_value=0, allow_null=True
    )
    historical_traffic = serializers.FloatField(
        required=False, min_value=0.0, allow_null=True
    )
    expected_arrivals = serializers.IntegerField(
        required=False, min_value=0, allow_null=True
    )
    throughput_utilization = serializers.FloatField(
        required=False, min_value=0.0, max_value=1.0, allow_null=True
    )
    weather_warning = serializers.ChoiceField(
        choices=WEATHER_CHOICES, required=False, allow_null=True
    )
    recent_waiting_time_days = serializers.FloatField(
        required=False, min_value=0.0, allow_null=True
    )
    # Recent per-day change in the congestion score (positive = worsening).
    trend_per_day = serializers.FloatField(required=False, allow_null=True)

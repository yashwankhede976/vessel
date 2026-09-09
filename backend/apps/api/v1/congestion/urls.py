"""Congestion domain API routes (v1)."""
from django.urls import path

from .views import CongestionForecastView

app_name = "congestion"

urlpatterns = [
    path("forecast/", CongestionForecastView.as_view(), name="forecast"),
]

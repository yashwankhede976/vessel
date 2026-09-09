"""Forecasts domain API routes (v1).

- freight/   composed freight forecast for a lane (historical + forecast +
             confidence + model metadata + data freshness)

See docs/API_CONVENTIONS.md. ETA forecast endpoints will be added here later.
"""
from django.urls import path

from .views import FreightForecastView

app_name = "forecasts"

urlpatterns = [
    path("freight/", FreightForecastView.as_view(), name="freight"),
]

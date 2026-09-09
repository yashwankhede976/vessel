"""Market-pressure domain API routes (v1)."""
from django.urls import path

from .views import MarketPressureView

app_name = "market_pressure"

urlpatterns = [
    path("", MarketPressureView.as_view(), name="index"),
]

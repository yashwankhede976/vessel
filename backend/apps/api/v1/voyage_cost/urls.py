"""Voyage-cost domain API routes (v1)."""
from django.urls import path

from .views import VoyageCostView

app_name = "voyage_cost"

urlpatterns = [
    path("", VoyageCostView.as_view(), name="compute"),
]

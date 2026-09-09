"""Landed-cost domain API routes (v1)."""
from django.urls import path

from .views import LandedCostCompareView, LandedCostView

app_name = "landed_cost"

urlpatterns = [
    path("", LandedCostView.as_view(), name="compute"),
    path("compare/", LandedCostCompareView.as_view(), name="compare"),
]

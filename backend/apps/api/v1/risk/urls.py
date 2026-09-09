"""Risk domain API routes (v1)."""
from django.urls import path

from .views import RiskView

app_name = "risk"

urlpatterns = [
    path("", RiskView.as_view(), name="score"),
]

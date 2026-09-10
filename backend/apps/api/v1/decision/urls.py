"""Unified decision domain API routes (v1)."""
from django.urls import path

from .views import DecisionView

app_name = "decision"

urlpatterns = [
    path("", DecisionView.as_view(), name="evaluate"),
]

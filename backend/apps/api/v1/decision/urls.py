"""Unified decision domain API routes (v1)."""
from django.urls import path

from .views import AssistantView, DecisionView

app_name = "decision"

urlpatterns = [
    path("", DecisionView.as_view(), name="evaluate"),
    path("assistant/", AssistantView.as_view(), name="assistant"),
]

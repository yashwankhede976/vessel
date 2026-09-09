"""Idle-vessel domain API routes (v1)."""
from django.urls import path

from .views import IdleVesselView

app_name = "idle_vessel"

urlpatterns = [
    path("", IdleVesselView.as_view(), name="rank"),
]

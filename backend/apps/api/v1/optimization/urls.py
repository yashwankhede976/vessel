"""Optimization domain API routes (v1)."""
from django.urls import path

from .views import MultiVoyageOptimizationView

app_name = "optimization"

urlpatterns = [
    path("multi-voyage/", MultiVoyageOptimizationView.as_view(), name="multi_voyage"),
]

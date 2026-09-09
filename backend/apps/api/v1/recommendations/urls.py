"""Recommendations domain API routes (v1).

Endpoints:
- recommendations/vessels/   POST — rank vessels for a chartering requirement
                             (origin, destination, cargo, commodity, laycan).

See docs/API_CONVENTIONS.md.
"""
from django.urls import path

from .views import VesselRecommendationView

app_name = "recommendations"

urlpatterns = [
    path("vessels/", VesselRecommendationView.as_view(), name="vessels"),
]

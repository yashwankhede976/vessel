"""Recommendations domain API routes (v1).

Scaffold only: the router is intentionally empty. Register ViewSets here as
recommendation endpoints (with explainability payloads) are implemented.
See docs/API_CONVENTIONS.md.
"""
from rest_framework.routers import DefaultRouter

app_name = "recommendations"

router = DefaultRouter()
# router.register("recommendations", RecommendationViewSet, basename="recommendation")

urlpatterns = router.urls

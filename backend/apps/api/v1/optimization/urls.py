"""Optimization domain API routes (v1).

Scaffold only: the router is intentionally empty. Register ViewSets here as
optimization run/result endpoints are implemented. No solver logic in the API
layer. See docs/API_CONVENTIONS.md and docs/ARCHITECTURE.md §6.
"""
from rest_framework.routers import DefaultRouter

app_name = "optimization"

router = DefaultRouter()
# router.register("runs", OptimizationRunViewSet, basename="optimization-run")

urlpatterns = router.urls

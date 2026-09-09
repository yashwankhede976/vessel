"""Forecasts domain API routes (v1).

Scaffold only: the router is intentionally empty. Register ViewSets here as
freight/ETA forecast endpoints are implemented. See docs/API_CONVENTIONS.md.
"""
from rest_framework.routers import DefaultRouter

app_name = "forecasts"

router = DefaultRouter()
# router.register("freight-forecasts", FreightForecastViewSet, basename="freight-forecast")
# router.register("eta-forecasts", ETAForecastViewSet, basename="eta-forecast")

urlpatterns = router.urls

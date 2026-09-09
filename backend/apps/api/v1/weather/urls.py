"""Weather domain API routes (v1).

Scaffold only: the router is intentionally empty. Register ViewSets here as
weather / marine / cyclone endpoints are implemented. See docs/API_CONVENTIONS.md.
"""
from rest_framework.routers import DefaultRouter

app_name = "weather"

router = DefaultRouter()
# router.register("weather-observations", WeatherObservationViewSet, basename="weather-observation")

urlpatterns = router.urls

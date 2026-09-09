"""Alerts domain API routes (v1).

Scaffold only: the router is intentionally empty. Register ViewSets here as
alert endpoints are implemented. See docs/API_CONVENTIONS.md.
"""
from rest_framework.routers import DefaultRouter

app_name = "alerts"

router = DefaultRouter()
# router.register("alerts", AlertViewSet, basename="alert")

urlpatterns = router.urls

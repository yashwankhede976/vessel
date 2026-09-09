"""Alerts domain API routes (v1).

- alerts/                 list alerts (filter by status/alert_type/severity)
- alerts/{id}/            retrieve an alert
- alerts/{id}/acknowledge/  mark ACKNOWLEDGED
- alerts/{id}/resolve/      mark RESOLVED
"""
from rest_framework.routers import DefaultRouter

from .views import AlertViewSet

app_name = "alerts"

router = DefaultRouter()
router.register("", AlertViewSet, basename="alert")

urlpatterns = router.urls

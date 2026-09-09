"""Vessels domain API routes (v1).

Endpoints:
- vessels/                list vessels (filter by type, DWT, draft, position)
- vessels/{id}/           retrieve vessel (with latest position)
- vessels/available/      list currently open/available vessels

See docs/API_CONVENTIONS.md.
"""
from rest_framework.routers import DefaultRouter

from .views import VesselViewSet

app_name = "vessels"

router = DefaultRouter()
router.register("", VesselViewSet, basename="vessel")

urlpatterns = router.urls

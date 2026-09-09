"""Freight domain API routes (v1).

Scaffold only: the router is intentionally empty. Register ViewSets here as
freight observation / historical analytics endpoints are implemented.
See docs/API_CONVENTIONS.md.
"""
from rest_framework.routers import DefaultRouter

app_name = "freight"

router = DefaultRouter()
# router.register("freight-observations", FreightObservationViewSet, basename="freight-observation")

urlpatterns = router.urls

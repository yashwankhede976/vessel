"""Routes (trade lanes) domain API routes (v1).

Endpoints:
- routes/          list trade lanes with resolved endpoint coordinates
- routes/{id}/     retrieve a single trade lane
"""
from rest_framework.routers import DefaultRouter

from .views import RouteViewSet

app_name = "routes"

router = DefaultRouter()
router.register("", RouteViewSet, basename="route")

urlpatterns = router.urls

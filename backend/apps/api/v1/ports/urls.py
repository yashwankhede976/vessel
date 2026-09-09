"""Ports domain API routes (v1).

Endpoints:
- ports/                     list ports
- ports/{id}/                retrieve port (with berths)
- ports/{id}/constraints/    retrieve port constraints
- ports/berths/              list berths
- ports/berths/{id}/         retrieve berth

See docs/API_CONVENTIONS.md.
"""
from rest_framework.routers import DefaultRouter

from .views import BerthViewSet, PortViewSet

app_name = "ports"

router = DefaultRouter()
# Register berths before the port detail route to keep 'berths' as a literal
# path segment rather than a port lookup value.
router.register("berths", BerthViewSet, basename="berth")
router.register("", PortViewSet, basename="port")

urlpatterns = router.urls

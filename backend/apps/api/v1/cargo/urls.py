"""Cargo domain API routes (v1).

Scaffold only: the router is intentionally empty. Register ViewSets here as
cargo-requirement endpoints are implemented. See docs/API_CONVENTIONS.md.
"""
from rest_framework.routers import DefaultRouter

app_name = "cargo"

router = DefaultRouter()
# router.register("cargo-requirements", CargoRequirementViewSet, basename="cargo-requirement")

urlpatterns = router.urls

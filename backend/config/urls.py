"""Root URL configuration for the Vessel backend.

The API is versioned by namespace: everything under /api/v1/ resolves to the
`v1` namespace, which DRF's NamespaceVersioning uses to set request.version.
"""
from django.urls import include, path

urlpatterns = [
    # Versioned API. The "v1" namespace drives NamespaceVersioning.
    path("api/v1/", include(("apps.api.v1.urls", "v1"), namespace="v1")),
]

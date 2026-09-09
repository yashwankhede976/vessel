"""API v1 URL aggregation.

Mounts the health endpoint, the nine domain API modules, and the OpenAPI
schema + documentation under the /api/v1/ namespace. Domain routers are
scaffolds (empty) until their endpoints are implemented.
"""
from django.urls import include, path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)

app_name = "v1"

urlpatterns = [
    # Health / meta.
    path("", include("apps.health.urls")),

    # Domain API modules.
    path("ports/", include("apps.api.v1.ports.urls")),
    path("vessels/", include("apps.api.v1.vessels.urls")),
    path("cargo/", include("apps.api.v1.cargo.urls")),
    path("freight/", include("apps.api.v1.freight.urls")),
    path("weather/", include("apps.api.v1.weather.urls")),
    path("forecasts/", include("apps.api.v1.forecasts.urls")),
    path("optimization/", include("apps.api.v1.optimization.urls")),
    path("recommendations/", include("apps.api.v1.recommendations.urls")),
    path("alerts/", include("apps.api.v1.alerts.urls")),

    # Decision-support / analytics endpoints.
    path("market-pressure/", include("apps.api.v1.market_pressure.urls")),
    path("congestion/", include("apps.api.v1.congestion.urls")),
    path("eta/", include("apps.api.v1.eta.urls")),
    path("voyage-cost/", include("apps.api.v1.voyage_cost.urls")),
    path("landed-cost/", include("apps.api.v1.landed_cost.urls")),
    path("contract-strategy/", include("apps.api.v1.contract_strategy.urls")),
    path("alternative-port/", include("apps.api.v1.alternative_port.urls")),
    path("idle-vessel/", include("apps.api.v1.idle_vessel.urls")),
    path("risk/", include("apps.api.v1.risk.urls")),
    path("fix-wait/", include("apps.api.v1.fix_wait.urls")),

    # OpenAPI schema + interactive documentation.
    path("schema/", SpectacularAPIView.as_view(), name="schema"),
    path(
        "docs/",
        SpectacularSwaggerView.as_view(url_name="v1:schema"),
        name="swagger-ui",
    ),
    path(
        "redoc/",
        SpectacularRedocView.as_view(url_name="v1:schema"),
        name="redoc",
    ),
]

"""Freight forecast endpoint.

GET /api/v1/forecasts/freight/?origin=&destination=&vessel_type=&horizon=

Assembles a composed response from stored ML outputs (the ML layer writes
FreightForecast rows; this endpoint serves them — see ARCHITECTURE §12). It
does NOT run the model inline. Returns historical observations, forecast points
with confidence interval + confidence, the model version and training timestamp,
and data-freshness metadata.

Expensive lookups are cached in Django's cache keyed by the query params.
"""
from __future__ import annotations

import hashlib
from datetime import timedelta

from django.core.cache import cache
from django.db.models import Max
from django.utils import timezone
from drf_spectacular.utils import (
    OpenApiParameter,
    extend_schema,
    inline_serializer,
)
from rest_framework import serializers
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.catalog.models import FreightObservation, Route
from apps.operations.models import FreightForecast

from .serializers import (
    ForecastPointSerializer,
    FreightForecastQuerySerializer,
    HistoricalPointSerializer,
)

CACHE_TTL_SECONDS = 300  # 5 minutes


def _iso(dt) -> str | None:
    return dt.isoformat() if dt else None


class FreightForecastView(APIView):
    """Composed freight forecast for a lane (origin -> destination)."""

    # Public read endpoint for now (no per-user data). Auth/RBAC can be added
    # with the rest of the API surface later.
    authentication_classes: list = []
    permission_classes: list = []

    @extend_schema(
        summary="Freight forecast for a lane",
        parameters=[
            OpenApiParameter("origin", str, required=True, description="Origin name (e.g. Australia)."),
            OpenApiParameter("destination", str, required=True, description="Destination East Coast India port (e.g. Paradip)."),
            OpenApiParameter("vessel_type", str, required=False, description="Vessel class filter (e.g. capesize)."),
            OpenApiParameter("horizon", str, required=False, description="short_term | medium_term."),
            OpenApiParameter("history_days", int, required=False, description="Days of history to include (default 180)."),
        ],
        responses=inline_serializer(
            name="FreightForecastResponse",
            fields={
                "route": serializers.DictField(allow_null=True),
                "historical": HistoricalPointSerializer(many=True),
                "forecast": ForecastPointSerializer(many=True),
                "model": serializers.DictField(allow_null=True),
                "data_freshness": serializers.DictField(allow_null=True),
                "cached": serializers.BooleanField(),
            },
        ),
    )
    def get(self, request: Request) -> Response:
        query = FreightForecastQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        params = query.validated_data

        cache_key = self._cache_key(params)
        cached = cache.get(cache_key)
        if cached is not None:
            cached = {**cached, "cached": True}
            return Response(cached)

        payload = self._build_payload(params)
        # Only cache resolvable lanes (avoid caching "route not found" churn).
        if payload.get("route") is not None:
            cache.set(cache_key, payload, CACHE_TTL_SECONDS)
        return Response({**payload, "cached": False})

    # ------------------------------------------------------------------
    def _cache_key(self, params: dict) -> str:
        raw = "|".join(
            str(params.get(k, ""))
            for k in ("origin", "destination", "vessel_type", "horizon", "history_days")
        )
        digest = hashlib.sha256(raw.encode()).hexdigest()[:24]
        return f"freight_forecast:{digest}"

    def _resolve_route(self, origin: str, destination: str):
        return (
            Route.objects.select_related("origin", "destination_port")
            .filter(
                origin__name__iexact=origin.strip(),
                destination_port__name__iexact=destination.strip(),
            )
            .first()
        )

    def _build_payload(self, params: dict) -> dict:
        origin = params["origin"]
        destination = params["destination"]
        vessel_type = params.get("vessel_type")
        horizon = params.get("horizon")
        history_days = params["history_days"]

        route = self._resolve_route(origin, destination)
        if route is None:
            # Graceful: no such lane. Empty sections + a clear note.
            return {
                "route": None,
                "query": {
                    "origin": origin, "destination": destination,
                    "vessel_type": vessel_type, "horizon": horizon,
                },
                "message": "No route found for the given origin and destination.",
                "historical": [],
                "forecast": [],
                "model": None,
                "data_freshness": None,
            }

        # --- forecasts: latest generation per target_date for this lane ---
        fc_qs = FreightForecast.objects.filter(route=route)
        if vessel_type:
            fc_qs = fc_qs.filter(vessel_type=vessel_type)
        if horizon:
            fc_qs = fc_qs.filter(horizon=horizon)

        # Use only the most recently generated forecast set (a single training run).
        latest_generated = fc_qs.aggregate(m=Max("generated_at"))["m"]
        forecasts = []
        model_meta = None
        if latest_generated is not None:
            current = fc_qs.filter(generated_at=latest_generated).order_by("target_date")
            forecasts = ForecastPointSerializer(current, many=True).data
            sample = current.first()
            if sample is not None:
                model_meta = {
                    "model_name": sample.model_name or None,
                    "model_version": sample.model_version or None,
                    "training_timestamp": _iso(sample.generated_at),
                }

        # --- historical observations ---
        since = timezone.now().date() - timedelta(days=history_days)
        hist_qs = FreightObservation.objects.filter(
            route=route, observed_on__gte=since
        )
        if vessel_type:
            # FreightObservation.vessel_type may be blank; include blanks + match.
            hist_qs = hist_qs.filter(vessel_type__in=[vessel_type, ""])
        hist_qs = hist_qs.order_by("observed_on")
        historical = HistoricalPointSerializer(hist_qs, many=True).data

        # --- data freshness ---
        latest_obs = (
            FreightObservation.objects.filter(route=route)
            .order_by("-observed_on")
            .first()
        )
        latest_obs_date = latest_obs.observed_on if latest_obs else None
        today = timezone.now().date()
        freshness = {
            "latest_observation_date": _iso(latest_obs_date),
            "observation_age_days": (
                (today - latest_obs_date).days if latest_obs_date else None
            ),
            "forecast_generated_at": _iso(latest_generated),
            "historical_count": len(historical),
            "forecast_count": len(forecasts),
        }

        return {
            "route": {
                "id": route.id,
                "origin": route.origin.name,
                "destination": route.destination_port.name,
                "vessel_type": vessel_type,
                "horizon": horizon,
            },
            "historical": historical,
            "forecast": forecasts,
            "model": model_meta,
            "data_freshness": freshness,
        }

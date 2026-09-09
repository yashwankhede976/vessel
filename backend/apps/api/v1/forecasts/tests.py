"""API tests for the freight forecast endpoint."""
from datetime import date, timedelta
from decimal import Decimal

from django.core.cache import cache
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.catalog.models import FreightObservation, Origin, Port, Route
from apps.operations.models import FreightForecast


class FreightForecastApiTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.origin = Origin.objects.create(name="Australia", country="Australia")
        # Paradip is seeded by a migration; reuse it.
        cls.port, _ = Port.objects.get_or_create(
            name="Paradip", country="India",
            defaults={"latitude": "20.26", "longitude": "86.67"},
        )
        cls.route = Route.objects.create(origin=cls.origin, destination_port=cls.port)

        # Historical observations.
        base = date(2026, 6, 1)
        for i in range(10):
            FreightObservation.objects.create(
                route=cls.route, vessel_type="capesize",
                observed_on=base + timedelta(days=i * 3),
                rate_per_tonne=Decimal("18.00") + Decimal(i) / 10,
                rate_type="spot", source="proxy", is_estimated=True,
            )

        # Forecasts from two generations; only the latest should be returned.
        # The natural key includes model_version, so two runs are two versions
        # (a re-train bumps the version); the endpoint picks the most recently
        # generated set via generated_at.
        old_gen = timezone.now() - timedelta(days=2)
        new_gen = timezone.now()
        for gen, rate, ver in [(old_gen, "20.0", "0.1.0"), (new_gen, "21.5", "0.2.0")]:
            for d in range(1, 4):
                FreightForecast.objects.create(
                    route=cls.route, vessel_type="capesize",
                    generated_at=gen, target_date=date(2026, 7, d),
                    horizon=FreightForecast.Horizon.SHORT_TERM,
                    predicted_rate_per_tonne=Decimal(rate),
                    lower_bound=Decimal(rate) - 1, upper_bound=Decimal(rate) + 1,
                    confidence=Decimal("0.82"),
                    model_name="freight_gbm_xgboost", model_version=ver,
                )

    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)

    def _url(self):
        return reverse("v1:forecasts:freight")

    def test_happy_path_returns_all_sections(self):
        resp = self.client.get(self._url(), {
            "origin": "Australia", "destination": "Paradip",
            "vessel_type": "capesize", "horizon": "short_term",
        })
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        body = resp.json()
        self.assertTrue(body["success"])
        data = body["data"]
        # All required sections present.
        self.assertIsNotNone(data["route"])
        self.assertTrue(len(data["historical"]) > 0)
        self.assertTrue(len(data["forecast"]) > 0)
        self.assertIsNotNone(data["model"])
        self.assertIsNotNone(data["data_freshness"])
        # Model metadata: version + training timestamp.
        self.assertEqual(data["model"]["model_version"], "0.2.0")
        self.assertIsNotNone(data["model"]["training_timestamp"])

    def test_forecast_has_confidence_interval_and_score(self):
        resp = self.client.get(self._url(), {
            "origin": "Australia", "destination": "Paradip", "vessel_type": "capesize",
        })
        point = resp.json()["data"]["forecast"][0]
        for f in ("predicted_rate_per_tonne", "lower_bound", "upper_bound", "confidence"):
            self.assertIn(f, point)
        self.assertEqual(Decimal(point["confidence"]), Decimal("0.820"))
        self.assertTrue(Decimal(point["lower_bound"]) <= Decimal(point["predicted_rate_per_tonne"]) <= Decimal(point["upper_bound"]))

    def test_only_latest_generation_returned(self):
        resp = self.client.get(self._url(), {
            "origin": "Australia", "destination": "Paradip", "vessel_type": "capesize",
        })
        data = resp.json()["data"]
        rates = {Decimal(p["predicted_rate_per_tonne"]) for p in data["forecast"]}
        # Latest generation had rate 21.5, older had 20.0 — only latest expected.
        self.assertEqual(rates, {Decimal("21.50")})
        self.assertEqual(len(data["forecast"]), 3)

    def test_data_freshness_reported(self):
        resp = self.client.get(self._url(), {"origin": "Australia", "destination": "Paradip"})
        fresh = resp.json()["data"]["data_freshness"]
        self.assertIn("latest_observation_date", fresh)
        self.assertIn("observation_age_days", fresh)
        self.assertIn("forecast_generated_at", fresh)
        self.assertEqual(fresh["forecast_count"], 3)

    def test_missing_route_is_graceful(self):
        resp = self.client.get(self._url(), {"origin": "Nowhere", "destination": "Paradip"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.json()["data"]
        self.assertIsNone(data["route"])
        self.assertEqual(data["historical"], [])
        self.assertEqual(data["forecast"], [])
        self.assertIn("No route found", data["message"])

    def test_missing_required_params_returns_400(self):
        resp = self.client.get(self._url(), {"origin": "Australia"})  # no destination
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        body = resp.json()
        self.assertFalse(body["success"])
        self.assertTrue(any(e.get("field") == "destination" for e in body["errors"]))

    def test_invalid_vessel_type_returns_400(self):
        resp = self.client.get(self._url(), {
            "origin": "Australia", "destination": "Paradip", "vessel_type": "spaceship",
        })
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_response_is_cached(self):
        url = self._url()
        q = {"origin": "Australia", "destination": "Paradip", "vessel_type": "capesize"}
        first = self.client.get(url, q).json()["data"]
        self.assertFalse(first["cached"])
        second = self.client.get(url, q).json()["data"]
        self.assertTrue(second["cached"])  # served from cache

    def test_horizon_filter(self):
        # Add a medium-term forecast; filtering short_term must exclude it.
        FreightForecast.objects.create(
            route=self.route, vessel_type="capesize",
            generated_at=timezone.now(), target_date=date(2026, 8, 1),
            horizon=FreightForecast.Horizon.MEDIUM_TERM,
            predicted_rate_per_tonne=Decimal("25.0"),
            model_name="m", model_version="0.2.0",
        )
        resp = self.client.get(self._url(), {
            "origin": "Australia", "destination": "Paradip",
            "vessel_type": "capesize", "horizon": "medium_term",
        })
        data = resp.json()["data"]
        self.assertTrue(all(p["horizon"] == "medium_term" for p in data["forecast"]))

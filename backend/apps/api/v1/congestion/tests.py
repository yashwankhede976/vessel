"""API tests for the congestion-forecast endpoint."""
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase


class CongestionForecastApiTests(APITestCase):
    def _url(self):
        return reverse("v1:congestion:forecast")

    def test_happy_path_all_horizons(self):
        resp = self.client.post(self._url(), {
            "vessels_waiting": 10, "recent_waiting_time_days": 4, "trend_per_day": 1.5,
        }, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.json()["data"]
        self.assertEqual([h["horizon_days"] for h in data["horizons"]], [1, 3, 7, 14])
        for h in data["horizons"]:
            self.assertTrue(0 <= h["congestion_score"] <= 100)
            self.assertIn(h["risk_level"], ["LOW", "MEDIUM", "HIGH", "SEVERE"])

    def test_confidence_decays(self):
        resp = self.client.post(self._url(), {
            "vessels_waiting": 8, "trend_per_day": 1.0,
        }, format="json")
        confs = [h["confidence"] for h in resp.json()["data"]["horizons"]]
        self.assertEqual(confs, sorted(confs, reverse=True))

    def test_missing_signals_ok(self):
        resp = self.client.post(self._url(), {"vessels_waiting": 5}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_bad_weather_choice_rejected(self):
        resp = self.client.post(self._url(), {
            "vessels_waiting": 5, "weather_warning": "hurricane",
        }, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

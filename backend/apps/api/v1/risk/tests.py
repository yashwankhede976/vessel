"""API tests for the risk endpoint."""
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase


class RiskApiTests(APITestCase):
    def _url(self):
        return reverse("v1:risk:score")

    def test_happy_path(self):
        resp = self.client.post(self._url(), {
            "freight_volatility": 0.6, "port_congestion": 70, "weather_risk": 0.4,
            "eta_delay_probability": 0.3,
        }, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.json()["data"]
        self.assertTrue(0 <= data["overall_score"] <= 100)
        self.assertIn(data["risk_level"], ["LOW", "MEDIUM", "HIGH"])

    def test_unknown_signals_reported_not_invented(self):
        resp = self.client.post(self._url(), {"freight_volatility": 0.5}, format="json")
        data = resp.json()["data"]
        self.assertIn("weather", data["unknown_factors"])
        self.assertIn("geopolitical", data["unknown_factors"])

    def test_empty_body_all_unknown(self):
        resp = self.client.post(self._url(), {}, format="json")
        data = resp.json()["data"]
        self.assertEqual(data["overall_score"], 0.0)
        self.assertEqual(len(data["unknown_factors"]), 8)

    def test_out_of_range_rejected(self):
        resp = self.client.post(self._url(), {"weather_risk": 2}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

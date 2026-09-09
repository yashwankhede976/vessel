"""API tests for the market-pressure endpoint."""
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase


class MarketPressureApiTests(APITestCase):
    def _url(self):
        return reverse("v1:market_pressure:index")

    def test_happy_path(self):
        resp = self.client.post(self._url(), {
            "vessel_supply": 0.2, "cargo_demand": 0.85, "freight_volatility": 0.6,
            "port_congestion": 80, "ton_mile_demand": 0.8, "bunker": 0.7,
            "seasonality": 0.6,
        }, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        body = resp.json()
        self.assertTrue(body["success"])
        data = body["data"]
        self.assertTrue(0 <= data["index"] <= 100)
        self.assertIn(data["classification"],
                      ["VERY_WEAK", "WEAK", "NEUTRAL", "TIGHT", "EXTREMELY_TIGHT"])
        self.assertEqual(data["missing_factors"], [])

    def test_missing_signals_reported(self):
        resp = self.client.post(self._url(), {"cargo_demand": 0.5}, format="json")
        data = resp.json()["data"]
        self.assertIn("bunker", data["missing_factors"])

    def test_empty_body_zero_index(self):
        resp = self.client.post(self._url(), {}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.json()["data"]["index"], 0.0)

    def test_out_of_range_rejected(self):
        resp = self.client.post(self._url(), {"cargo_demand": 5}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

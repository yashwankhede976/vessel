"""API tests for the voyage-cost endpoint."""
from decimal import Decimal

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase


class VoyageCostApiTests(APITestCase):
    def _url(self):
        return reverse("v1:voyage_cost:compute")

    def test_happy_path_currency_and_units(self):
        resp = self.client.post(self._url(), {
            "distance_nm": "6500", "speed_kn": "13", "cargo_tonnes": "55000",
            "bunker_rate_tpd": "45", "bunker_price_per_tonne": "600",
            "freight_rate_per_tonne": "22", "port_cost": "150000",
        }, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.json()["data"]
        self.assertEqual(data["total_voyage_cost"]["currency"], "USD")
        self.assertEqual(data["total_voyage_cost"]["unit"], "total")
        self.assertEqual(data["cost_per_tonne"]["unit"], "per_tonne")
        self.assertIn("cost_components", data)

    def test_zero_speed_rejected(self):
        resp = self.client.post(self._url(), {
            "distance_nm": "6500", "speed_kn": "0", "cargo_tonnes": "55000",
        }, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

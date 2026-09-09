"""API tests for the landed-cost endpoints."""
from decimal import Decimal

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase


class LandedCostApiTests(APITestCase):
    def _url(self):
        return reverse("v1:landed_cost:compute")

    def _compare_url(self):
        return reverse("v1:landed_cost:compare")

    def test_single_compute(self):
        resp = self.client.post(self._url(), {
            "origin": "Australia", "destination": "Paradip", "cargo_tonnes": "50000",
            "commodity_cost": {"amount": "5000000", "currency": "USD"},
            "freight_cost": {"amount": "1200000", "currency": "USD"},
        }, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.json()["data"]
        self.assertEqual(data["total_landed_cost"]["amount"], "6200000.00")
        self.assertEqual(data["landed_cost_per_tonne"]["unit"], "per_tonne")

    def test_fx_conversion(self):
        resp = self.client.post(self._url(), {
            "origin": "Australia", "destination": "Paradip", "cargo_tonnes": "50000",
            "commodity_cost": {"amount": "1000000", "currency": "AUD"},
            "target_currency": "USD", "fx_rates": {"AUD": "0.65"},
        }, format="json")
        data = resp.json()["data"]
        self.assertEqual(data["components"]["commodity_cost"]["amount"], "650000.00")

    def test_missing_fx_rate_is_error(self):
        resp = self.client.post(self._url(), {
            "origin": "Australia", "destination": "Paradip", "cargo_tonnes": "50000",
            "commodity_cost": {"amount": "1000000", "currency": "AUD"},
        }, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_compare_origins_sorted(self):
        resp = self.client.post(self._compare_url(), {"inputs": [
            {"origin": "Australia", "destination": "Paradip", "cargo_tonnes": "50000",
             "commodity_cost": {"amount": "5000000"}, "freight_cost": {"amount": "1200000"}},
            {"origin": "Indonesia", "destination": "Paradip", "cargo_tonnes": "50000",
             "commodity_cost": {"amount": "4800000"}, "freight_cost": {"amount": "900000"}},
        ]}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        entries = resp.json()["data"]["entries"]
        self.assertEqual(entries[0]["origin"], "Indonesia")   # cheapest first
        self.assertTrue(entries[0]["is_cheapest"])

    def test_zero_cargo_rejected(self):
        resp = self.client.post(self._url(), {
            "origin": "Australia", "destination": "Paradip", "cargo_tonnes": "0",
        }, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

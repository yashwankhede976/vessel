"""API tests for the contract-strategy endpoints."""
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase


class ContractStrategyApiTests(APITestCase):
    def _compare(self):
        return reverse("v1:contract_strategy:compare")

    def _portfolio(self):
        return reverse("v1:contract_strategy:portfolio")

    def test_spot_vs_contract(self):
        resp = self.client.post(self._compare(), {
            "spot_freight_per_tonne": "22", "cargo_tonnes": "55000",
            "freight_volatility": 0.5, "base_demurrage_cost": "40000",
        }, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.json()["data"]
        self.assertIn(data["recommended_strategy"],
                      ["SPOT", "SHORT_TERM", "MEDIUM_TERM", "MULTI_VOYAGE"])
        self.assertEqual(len(data["options"]), 4)

    def test_spot_vs_contract_zero_cargo_rejected(self):
        resp = self.client.post(self._compare(), {
            "spot_freight_per_tonne": "22", "cargo_tonnes": "0",
        }, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_portfolio_allocations_sum_to_total(self):
        resp = self.client.post(self._portfolio(), {
            "total_tonnes": "600000", "spot_freight_per_tonne": "22",
            "market_pressure_index": 67,
        }, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.json()["data"]
        total = sum(float(a["tonnes"]) for a in data["allocations"])
        self.assertAlmostEqual(total, 600000.0, places=1)
        self.assertGreater(data["risk_reduction"], 0.0)

    def test_portfolio_regime(self):
        resp = self.client.post(self._portfolio(), {
            "total_tonnes": "100000", "spot_freight_per_tonne": "20",
            "market_pressure_index": 80,
        }, format="json")
        self.assertEqual(resp.json()["data"]["regime"], "tight")

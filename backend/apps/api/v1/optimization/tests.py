"""API tests for the multi-voyage optimization endpoint."""
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase


class OptimizationApiTests(APITestCase):
    def _url(self):
        return reverse("v1:optimization:multi_voyage")

    def _candidates(self):
        return [
            {"id": "AUS", "origin": "Australia", "destination": "Paradip",
             "vessel_type": "capesize", "cost_per_voyage": "6200000",
             "capacity_tonnes": "160000", "max_voyages": 3},
            {"id": "IDN", "origin": "Indonesia", "destination": "Paradip",
             "vessel_type": "panamax", "cost_per_voyage": "2600000",
             "capacity_tonnes": "75000", "max_voyages": 5},
        ]

    def test_happy_path_optimal(self):
        resp = self.client.post(self._url(), {
            "required_tonnes": "300000", "candidates": self._candidates(),
            "tolerance_pct": "10",
        }, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.json()["data"]
        self.assertIn(data["status"], ["optimal", "feasible"])
        self.assertTrue(len(data["selected_voyages"]) >= 1)
        self.assertIn("origin_allocation", data)
        self.assertIn("contract_strategy_mix", data)

    def test_incompatible_excluded(self):
        cands = self._candidates() + [{
            "id": "BAD", "origin": "Russia", "destination": "Paradip",
            "vessel_type": "capesize", "cost_per_voyage": "1", "capacity_tonnes": "160000",
            "max_voyages": 5, "is_compatible": False,
        }]
        resp = self.client.post(self._url(), {
            "required_tonnes": "150000", "candidates": cands, "tolerance_pct": "10",
        }, format="json")
        self.assertNotIn("Russia", resp.json()["data"]["origin_allocation"])

    def test_infeasible_returns_400(self):
        resp = self.client.post(self._url(), {
            "required_tonnes": "10000000",
            "candidates": [{"id": "IDN", "origin": "Indonesia", "destination": "Paradip",
                            "vessel_type": "panamax", "cost_per_voyage": "2600000",
                            "capacity_tonnes": "75000", "max_voyages": 1}],
        }, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_no_candidates_rejected(self):
        resp = self.client.post(self._url(), {
            "required_tonnes": "150000", "candidates": [],
        }, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

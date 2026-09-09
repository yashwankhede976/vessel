"""API tests for the ETA endpoint."""
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase


class ETAApiTests(APITestCase):
    def _url(self):
        return reverse("v1:eta:predict")

    def test_happy_path_has_percentiles_and_delay_prob(self):
        resp = self.client.post(self._url(), {
            "route_distance_nm": 6500, "speed_kn": 13, "weather_risk": 0.4,
            "destination_congestion": 70, "expected_port_waiting_days": 3,
        }, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.json()["data"]
        for f in ("eta", "eta_p50", "eta_p80", "eta_p95",
                  "delay_probability", "delay_reasons"):
            self.assertIn(f, data)
        self.assertTrue(0.0 <= data["delay_probability"] <= 1.0)

    def test_impossible_speed_rejected(self):
        resp = self.client.post(self._url(), {
            "route_distance_nm": 6500, "speed_kn": 0,
        }, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(resp.json()["success"])

    def test_percentiles_ordered(self):
        resp = self.client.post(self._url(), {
            "route_distance_nm": 5000, "speed_kn": 14,
        }, format="json")
        data = resp.json()["data"]
        self.assertLessEqual(data["eta_p50"], data["eta_p80"])
        self.assertLessEqual(data["eta_p80"], data["eta_p95"])

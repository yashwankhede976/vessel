"""API tests for the fix-wait endpoint."""
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase


class FixWaitApiTests(APITestCase):
    def _url(self):
        return reverse("v1:fix_wait:decision")

    def test_no_forecast_monitors(self):
        resp = self.client.post(self._url(), {"current_rate": "22"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.json()["data"]["decision"], "MONITOR")

    def test_rising_fixes_now(self):
        resp = self.client.post(self._url(), {
            "current_rate": "22", "forecast_7d": "23.5", "confidence_7d": 0.7,
            "days_to_deadline": 40,
        }, format="json")
        self.assertEqual(resp.json()["data"]["decision"], "FIX_NOW")

    def test_strong_confident_fall_waits(self):
        resp = self.client.post(self._url(), {
            "current_rate": "22", "forecast_7d": "20.5", "forecast_14d": "20",
            "confidence_7d": 0.8, "confidence_14d": 0.78, "days_to_deadline": 40,
        }, format="json")
        self.assertEqual(resp.json()["data"]["decision"], "WAIT")

    def test_zero_rate_rejected(self):
        resp = self.client.post(self._url(), {"current_rate": "0"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_thresholds_exposed(self):
        resp = self.client.post(self._url(), {
            "current_rate": "22", "forecast_7d": "20", "confidence_7d": 0.8,
        }, format="json")
        self.assertIn("thresholds", resp.json()["data"]["drivers"])

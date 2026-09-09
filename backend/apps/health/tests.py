"""Test the health-check endpoint and the API response envelope."""
from django.test import TestCase


class HealthCheckTests(TestCase):
    def test_health_returns_ok(self) -> None:
        response = self.client.get("/api/v1/health/")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        # Consistent envelope: success/data/errors.
        self.assertTrue(body["success"])
        self.assertIsNone(body["errors"])
        self.assertEqual(body["data"]["status"], "ok")
        self.assertEqual(body["data"]["service"], "vessel-backend")


class ApiConventionTests(TestCase):
    def test_method_not_allowed_returns_error_envelope(self) -> None:
        # A DRF-handled error (405) flows through the custom exception handler
        # and the consistent error envelope. (A Django-level 404 for an
        # unmatched URL is handled by Django, not DRF, so it is not enveloped.)
        response = self.client.post("/api/v1/health/", {})
        self.assertEqual(response.status_code, 405)
        body = response.json()
        self.assertFalse(body["success"])
        self.assertIsNone(body["data"])
        self.assertIsInstance(body["errors"], list)
        self.assertIn("code", body["errors"][0])

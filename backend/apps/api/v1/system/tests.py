"""API tests for the system observability endpoints."""
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.ingestion.models import IngestionRun


class DataFreshnessApiTests(APITestCase):
    def test_returns_all_datasets(self):
        resp = self.client.get(reverse("v1:system:data_freshness"))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        body = resp.json()
        self.assertTrue(body["success"])
        datasets = {d["dataset"] for d in body["data"]["datasets"]}
        self.assertIn("ais_positions", datasets)
        self.assertIn("trade", datasets)
        # With no data every dataset is UNKNOWN.
        for d in body["data"]["datasets"]:
            self.assertEqual(d["level"], "UNKNOWN")


class ExternalServicesApiTests(APITestCase):
    def test_returns_services_without_keys(self):
        IngestionRun.objects.create(
            source_key="open_meteo", status=IngestionRun.Status.SUCCESS,
        )
        resp = self.client.get(reverse("v1:system:external_services"))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        body = resp.json()
        providers = {s["provider"] for s in body["data"]["services"]}
        self.assertIn("open_meteo", providers)
        self.assertIn("world_bank", providers)
        # Never leak keys.
        payload = str(body).lower()
        self.assertNotIn("api_key", payload)
        self.assertNotIn("aisstream_api_key", payload)

    def test_keyless_provider_configured(self):
        resp = self.client.get(reverse("v1:system:external_services"))
        services = {s["provider"]: s for s in resp.json()["data"]["services"]}
        self.assertTrue(services["open_meteo"]["configured"])
        self.assertFalse(services["open_meteo"]["needs_key"])

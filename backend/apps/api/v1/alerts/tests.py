"""API tests for the alerts endpoints."""
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.alerts.models import Alert, AlertSeverity, AlertStatus, AlertType


class AlertApiTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.a1 = Alert.objects.create(
            alert_type=AlertType.CONGESTION_INCREASE, severity=AlertSeverity.HIGH,
            timestamp="2026-09-01T00:00:00Z", entity="Paradip",
            message="Congestion high", status=AlertStatus.NEW,
        )
        cls.a2 = Alert.objects.create(
            alert_type=AlertType.FREIGHT_INCREASE, severity=AlertSeverity.MEDIUM,
            timestamp="2026-09-02T00:00:00Z", entity="AUS->Paradip",
            message="Freight up", status=AlertStatus.ACKNOWLEDGED,
        )

    def test_list_paginated_envelope(self):
        resp = self.client.get(reverse("v1:alerts:alert-list"))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        body = resp.json()
        self.assertTrue(body["success"])
        self.assertEqual(body["pagination"]["count"], 2)

    def test_filter_by_status(self):
        resp = self.client.get(reverse("v1:alerts:alert-list"), {"status": "new"})
        data = resp.json()["data"]
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["entity"], "Paradip")

    def test_filter_by_type_and_severity(self):
        resp = self.client.get(
            reverse("v1:alerts:alert-list"),
            {"alert_type": "freight_increase", "severity": "medium"},
        )
        self.assertEqual(len(resp.json()["data"]), 1)

    def test_retrieve(self):
        resp = self.client.get(reverse("v1:alerts:alert-detail", args=[self.a1.pk]))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.json()["data"]["message"], "Congestion high")

    def test_acknowledge(self):
        resp = self.client.post(reverse("v1:alerts:alert-acknowledge", args=[self.a1.pk]))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.json()["data"]["status"], "acknowledged")
        self.a1.refresh_from_db()
        self.assertIsNotNone(self.a1.acknowledged_at)

    def test_resolve(self):
        resp = self.client.post(reverse("v1:alerts:alert-resolve", args=[self.a1.pk]))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.json()["data"]["status"], "resolved")

    def test_acknowledge_resolved_rejected(self):
        self.a1.status = AlertStatus.RESOLVED
        self.a1.save()
        resp = self.client.post(reverse("v1:alerts:alert-acknowledge", args=[self.a1.pk]))
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

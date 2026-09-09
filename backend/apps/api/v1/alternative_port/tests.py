"""API tests for the alternative-port endpoint."""
from decimal import Decimal

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.catalog.models import Origin, Port, Route, Vessel


class AlternativePortApiTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.origin, _ = Origin.objects.get_or_create(
            name="Australia", defaults={"country": "Australia"}
        )
        # Two East Coast ports with routes + distances.
        cls.paradip, _ = Port.objects.get_or_create(
            name="Paradip", country="India",
            defaults={"latitude": Decimal("20.26"), "longitude": Decimal("86.67"),
                      "coast": Port.Coast.EAST_COAST_INDIA},
        )
        cls.vizag, _ = Port.objects.get_or_create(
            name="Visakhapatnam", country="India",
            defaults={"latitude": Decimal("17.68"), "longitude": Decimal("83.21"),
                      "coast": Port.Coast.EAST_COAST_INDIA},
        )
        Route.objects.get_or_create(
            origin=cls.origin, destination_port=cls.paradip,
            defaults={"distance_nm": Decimal("6500")},
        )
        Route.objects.get_or_create(
            origin=cls.origin, destination_port=cls.vizag,
            defaults={"distance_nm": Decimal("6200")},
        )

    def _url(self):
        return reverse("v1:alternative_port:compare")

    def test_happy_path_recommends_a_port(self):
        resp = self.client.post(self._url(), {
            "origin": "Australia", "requested_destination": "Paradip",
            "cargo_tonnes": "55000", "commodity": "Coal",
            "freight_rate_per_tonne": "22", "bunker_price_per_tonne": "600",
        }, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.json()["data"]
        self.assertEqual(data["requested_port"], "Paradip")
        self.assertTrue(len(data["alternative_ports"]) >= 1)
        # A recommendation with a computable cost should be present.
        self.assertIsNotNone(data["recommended_port"])

    def test_unknown_destination_returns_400(self):
        resp = self.client.post(self._url(), {
            "origin": "Australia", "requested_destination": "Nowhere",
            "cargo_tonnes": "55000", "commodity": "Coal",
        }, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_zero_cargo_rejected(self):
        resp = self.client.post(self._url(), {
            "origin": "Australia", "requested_destination": "Paradip",
            "cargo_tonnes": "0", "commodity": "Coal",
        }, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

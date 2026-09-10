"""API tests for the routes (trade lanes) domain endpoint."""
from decimal import Decimal

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.catalog.models import Origin, Port, Route


class RouteApiTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.load_port = Port.objects.create(
            name="Newcastle (AU)", country="Australia", coast="overseas",
            latitude=Decimal("-32.927"), longitude=Decimal("151.78"),
        )
        # Paradip may be seeded by a migration; reuse it to avoid the
        # unique (name, country) collision.
        cls.dest, _ = Port.objects.get_or_create(
            name="Paradip", country="India",
            defaults={"latitude": Decimal("20.264"), "longitude": Decimal("86.67")},
        )
        cls.origin_with_port = Origin.objects.create(
            name="Australia", country="Australia", load_port=cls.load_port
        )
        cls.origin_no_port = Origin.objects.create(
            name="Indonesia", country="Indonesia", load_port=None
        )
        cls.route_drawable = Route.objects.create(
            origin=cls.origin_with_port, destination_port=cls.dest,
            distance_nm=Decimal("6500"), typical_transit_days=Decimal("20"),
        )
        cls.route_no_origin_coord = Route.objects.create(
            origin=cls.origin_no_port, destination_port=cls.dest,
            distance_nm=Decimal("3100"),
        )

    def _url(self):
        return reverse("v1:routes:route-list")

    def test_list_returns_resolved_endpoint_coordinates(self):
        resp = self.client.get(self._url(), {"origin": "Australia"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.json()["data"]
        self.assertEqual(len(data), 1)
        r = data[0]
        self.assertEqual(r["origin_name"], "Australia")
        self.assertEqual(r["origin_port_name"], "Newcastle (AU)")
        self.assertEqual(Decimal(r["origin_latitude"]), Decimal("-32.927000"))
        self.assertEqual(Decimal(r["destination_latitude"]), self.dest.latitude)
        self.assertEqual(r["destination_name"], "Paradip")
        self.assertEqual(r["distance_nm"], "6500.00")
        self.assertTrue(r["drawable"])

    def test_route_without_origin_coordinates_is_not_drawable(self):
        """An origin with no load port yields null coords and drawable=false —
        the coordinate is never invented."""
        resp = self.client.get(self._url(), {"origin": "Indonesia"})
        r = resp.json()["data"][0]
        self.assertIsNone(r["origin_latitude"])
        self.assertIsNone(r["origin_port_name"])
        self.assertFalse(r["drawable"])

    def test_filter_by_destination(self):
        resp = self.client.get(self._url(), {"destination": "Paradip"})
        self.assertEqual(resp.json()["pagination"]["count"], 2)

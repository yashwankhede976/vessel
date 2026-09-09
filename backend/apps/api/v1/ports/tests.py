"""API tests for the ports domain endpoints.

Covers: list/retrieve ports, list/retrieve berths, filter by coast, filter by
commodity, retrieve port constraints, and berth-dimension validation. Every
response is checked against the consistent envelope (success/data/errors).
"""
from decimal import Decimal

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.api.v1.ports.serializers import BerthSerializer
from apps.catalog.models import Berth, Commodity, Port


class PortsApiTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        # East Coast port (seeded ports also exist from the data migration).
        cls.coal = Commodity.objects.create(
            name="Thermal Coal", category=Commodity.Category.COAL_THERMAL
        )
        cls.iron = Commodity.objects.create(
            name="Iron Ore", category=Commodity.Category.IRON_ORE
        )
        cls.east = Port.objects.create(
            name="Test East Port",
            country="India",
            coast=Port.Coast.EAST_COAST_INDIA,
            latitude=Decimal("20.0"),
            longitude=Decimal("86.0"),
        )
        cls.west = Port.objects.create(
            name="Test West Port",
            country="India",
            coast=Port.Coast.WEST_COAST_INDIA,
            latitude=Decimal("19.0"),
            longitude=Decimal("72.0"),
        )
        cls.berth = Berth.objects.create(
            port=cls.east,
            berth_name="CQ-1",
            max_loa=Decimal("290.00"),
            max_beam=Decimal("45.00"),
            max_draft=Decimal("18.50"),
            handling_rate=Decimal("35000.00"),
        )
        cls.berth.supported_commodities.add(cls.coal)

    # ---- list / retrieve ports ----
    def test_list_ports(self):
        resp = self.client.get(reverse("v1:ports:port-list"))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        body = resp.json()
        self.assertTrue(body["success"])
        self.assertIsNone(body["errors"])
        self.assertIn("pagination", body)
        names = [p["name"] for p in body["data"]]
        # Includes our test ports and the seeded East Coast ports.
        self.assertIn("Test East Port", names)
        self.assertIn("Paradip", names)

    def test_retrieve_port_includes_berths(self):
        resp = self.client.get(reverse("v1:ports:port-detail", args=[self.east.id]))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.json()["data"]
        self.assertEqual(data["name"], "Test East Port")
        self.assertEqual(data["coast"], "east_coast_india")
        self.assertEqual(len(data["berths"]), 1)
        self.assertEqual(data["berths"][0]["berth_name"], "CQ-1")

    def test_retrieve_missing_port_returns_error_envelope(self):
        resp = self.client.get(reverse("v1:ports:port-detail", args=[999999]))
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
        body = resp.json()
        self.assertFalse(body["success"])
        self.assertIsInstance(body["errors"], list)

    # ---- filter ports by coast ----
    def test_filter_ports_by_coast_east(self):
        resp = self.client.get(reverse("v1:ports:port-list"), {"coast": "east_coast_india"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        coasts = {p["coast"] for p in resp.json()["data"]}
        self.assertEqual(coasts, {"east_coast_india"})

    def test_filter_ports_by_coast_west_excludes_east(self):
        resp = self.client.get(reverse("v1:ports:port-list"), {"coast": "west_coast_india"})
        names = [p["name"] for p in resp.json()["data"]]
        self.assertIn("Test West Port", names)
        self.assertNotIn("Test East Port", names)

    # ---- filter ports by commodity ----
    def test_filter_ports_by_commodity(self):
        resp = self.client.get(reverse("v1:ports:port-list"), {"commodity": "Thermal Coal"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        names = [p["name"] for p in resp.json()["data"]]
        self.assertIn("Test East Port", names)  # has a coal berth
        self.assertNotIn("Test West Port", names)  # no berths

    def test_filter_ports_by_commodity_no_match(self):
        resp = self.client.get(reverse("v1:ports:port-list"), {"commodity": "Iron Ore"})
        names = [p["name"] for p in resp.json()["data"]]
        self.assertNotIn("Test East Port", names)

    # ---- list / retrieve berths ----
    def test_list_berths(self):
        resp = self.client.get(reverse("v1:ports:berth-list"))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        body = resp.json()
        self.assertTrue(body["success"])
        berth_names = [b["berth_name"] for b in body["data"]]
        self.assertIn("CQ-1", berth_names)
        # Clean JSON: commodities as names, port name present.
        cq1 = next(b for b in body["data"] if b["berth_name"] == "CQ-1")
        self.assertEqual(cq1["supported_commodities"], ["Thermal Coal"])
        self.assertEqual(cq1["port_name"], "Test East Port")

    def test_retrieve_berth(self):
        resp = self.client.get(reverse("v1:ports:berth-detail", args=[self.berth.id]))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.json()["data"]
        self.assertEqual(data["berth_name"], "CQ-1")
        self.assertEqual(Decimal(data["max_draft"]), Decimal("18.50"))

    def test_filter_berths_by_commodity(self):
        resp = self.client.get(reverse("v1:ports:berth-list"), {"commodity": "Thermal Coal"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(all("CQ-1" == b["berth_name"] for b in resp.json()["data"]))

    # ---- port constraints ----
    def test_retrieve_port_constraints(self):
        resp = self.client.get(reverse("v1:ports:port-constraints", args=[self.east.id]))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.json()["data"]
        self.assertEqual(data["name"], "Test East Port")
        self.assertEqual(Decimal(data["max_loa"]), Decimal("290.00"))
        self.assertEqual(Decimal(data["max_draft"]), Decimal("18.50"))
        self.assertEqual(data["supported_commodities"], ["Thermal Coal"])
        self.assertEqual(data["berth_count"], 1)

    def test_constraints_empty_port(self):
        resp = self.client.get(reverse("v1:ports:port-constraints", args=[self.west.id]))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.json()["data"]
        self.assertIsNone(data["max_loa"])
        self.assertEqual(data["supported_commodities"], [])
        self.assertEqual(data["berth_count"], 0)


class BerthValidationTests(APITestCase):
    """Serializer-level validation for LOA, beam, draft, handling rate."""

    def _serializer(self, **overrides):
        data = {
            "berth_name": "V-1",
            "max_loa": "250.00",
            "max_beam": "40.00",
            "max_draft": "16.00",
            "handling_rate": "20000.00",
        }
        data.update(overrides)
        return BerthSerializer(data=data)

    def test_valid_dimensions(self):
        self.assertTrue(self._serializer().is_valid())

    def test_zero_loa_rejected(self):
        s = self._serializer(max_loa="0")
        self.assertFalse(s.is_valid())
        self.assertIn("max_loa", s.errors)

    def test_negative_draft_rejected(self):
        s = self._serializer(max_draft="-1")
        self.assertFalse(s.is_valid())
        self.assertIn("max_draft", s.errors)

    def test_absurd_beam_rejected(self):
        s = self._serializer(max_beam="9999")
        self.assertFalse(s.is_valid())
        self.assertIn("max_beam", s.errors)

    def test_negative_handling_rate_rejected(self):
        s = self._serializer(handling_rate="-5")
        self.assertFalse(s.is_valid())
        self.assertIn("handling_rate", s.errors)

    def test_zero_handling_rate_allowed(self):
        # Zero means "unknown" and is permitted.
        self.assertTrue(self._serializer(handling_rate="0").is_valid())

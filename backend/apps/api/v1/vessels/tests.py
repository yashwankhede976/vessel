"""API tests for the vessels domain endpoints.

Covers: list, detail, filter by vessel type, DWT, draft, current position
(bounding box), and availability. Verifies pagination and the consistent
response envelope.
"""
from datetime import date, timedelta
from decimal import Decimal

from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.catalog.models import Vessel
from apps.operations.models import AISPosition


class VesselApiTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        # A representative vessel of each required class.
        cls.handy = Vessel.objects.create(
            imo="1000001", name="Handy One", vessel_type=Vessel.VesselType.HANDYSIZE,
            dwt=Decimal("35000"), loa=Decimal("180"), beam=Decimal("28"),
            draft=Decimal("10.5"), availability_status=Vessel.AvailabilityStatus.OPEN,
            open_date=date(2026, 9, 20),
        )
        cls.supra = Vessel.objects.create(
            imo="1000002", name="Supra Two", vessel_type=Vessel.VesselType.SUPRAMAX,
            dwt=Decimal("58000"), loa=Decimal("200"), beam=Decimal("32"),
            draft=Decimal("12.8"), availability_status=Vessel.AvailabilityStatus.LADEN,
        )
        cls.pana = Vessel.objects.create(
            imo="1000003", name="Pana Three", vessel_type=Vessel.VesselType.PANAMAX,
            dwt=Decimal("82000"), loa=Decimal("229"), beam=Decimal("32.2"),
            draft=Decimal("14.4"), availability_status=Vessel.AvailabilityStatus.OPEN,
            open_date=date(2026, 10, 5),
            metadata={
                "class_society": {
                    "value": "DNV", "source": "Owner particulars",
                    "source_date": "2026-01-15",
                },
                "gear": {
                    "value": "gearless", "source": "Owner particulars",
                    "source_date": "2026-01-15",
                },
                "ice_class": {
                    "value": "UNKNOWN", "source": "UNKNOWN", "source_date": "UNKNOWN",
                },
            },
        )
        cls.cape = Vessel.objects.create(
            imo="1000004", name="Cape Four", vessel_type=Vessel.VesselType.CAPESIZE,
            dwt=Decimal("180000"), loa=Decimal("292"), beam=Decimal("45"),
            draft=Decimal("18.1"), availability_status=Vessel.AvailabilityStatus.FIXED,
        )
        # Latest positions: Panamax in the Bay of Bengal box, Cape far away.
        now = timezone.now()
        AISPosition.objects.create(
            vessel=cls.pana, timestamp=now, latitude=Decimal("15.0"),
            longitude=Decimal("85.0"), sog=Decimal("12.0"), nav_status="under way",
        )
        # An older position for the same vessel (should be ignored as non-latest).
        AISPosition.objects.create(
            vessel=cls.pana, timestamp=now - timedelta(days=2),
            latitude=Decimal("5.0"), longitude=Decimal("100.0"),
        )
        AISPosition.objects.create(
            vessel=cls.cape, timestamp=now, latitude=Decimal("-20.0"),
            longitude=Decimal("15.0"),
        )

    # ---- list ----
    def test_list_vessels_paginated_envelope(self):
        resp = self.client.get(reverse("v1:vessels:vessel-list"))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        body = resp.json()
        self.assertTrue(body["success"])
        self.assertIsNone(body["errors"])
        self.assertIn("pagination", body)
        self.assertEqual(body["pagination"]["count"], 4)
        self.assertEqual(len(body["data"]), 4)

    def test_list_includes_latest_position(self):
        resp = self.client.get(reverse("v1:vessels:vessel-list"))
        by_name = {v["name"]: v for v in resp.json()["data"]}
        # Panamax latest position is the recent one (15, 85), not the older one.
        pos = by_name["Pana Three"]["latest_position"]
        self.assertIsNotNone(pos)
        self.assertEqual(Decimal(pos["latitude"]), Decimal("15.000000"))
        self.assertEqual(Decimal(pos["longitude"]), Decimal("85.000000"))
        # Handysize has no position.
        self.assertIsNone(by_name["Handy One"]["latest_position"])

    # ---- detail ----
    def test_retrieve_vessel(self):
        resp = self.client.get(reverse("v1:vessels:vessel-detail", args=[self.cape.id]))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.json()["data"]
        self.assertEqual(data["name"], "Cape Four")
        self.assertEqual(data["vessel_type"], "capesize")
        self.assertEqual(data["vessel_type_display"], "Capesize")

    def test_retrieve_missing_vessel_error_envelope(self):
        resp = self.client.get(reverse("v1:vessels:vessel-detail", args=[999999]))
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
        self.assertFalse(resp.json()["success"])

    # ---- metadata (curated, source-referenced particulars) ----
    def test_detail_returns_sourced_metadata(self):
        """A vessel's curated metadata is exposed with per-field provenance
        (value/source/source_date), and UNKNOWN is preserved, not estimated."""
        resp = self.client.get(reverse("v1:vessels:vessel-detail", args=[self.pana.id]))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        meta = resp.json()["data"]["metadata"]
        self.assertEqual(meta["class_society"]["value"], "DNV")
        self.assertEqual(meta["class_society"]["source"], "Owner particulars")
        self.assertEqual(meta["class_society"]["source_date"], "2026-01-15")
        self.assertEqual(meta["gear"]["value"], "gearless")
        # Unavailable particulars are recorded as UNKNOWN rather than guessed.
        self.assertEqual(meta["ice_class"]["value"], "UNKNOWN")

    def test_metadata_defaults_to_empty_dict(self):
        """A vessel created without metadata returns an empty object, not null."""
        resp = self.client.get(reverse("v1:vessels:vessel-detail", args=[self.handy.id]))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.json()["data"]["metadata"], {})

    def test_list_includes_metadata_field(self):
        resp = self.client.get(reverse("v1:vessels:vessel-list"))
        by_name = {v["name"]: v for v in resp.json()["data"]}
        self.assertIn("metadata", by_name["Pana Three"])
        self.assertEqual(by_name["Pana Three"]["metadata"]["class_society"]["value"], "DNV")

    # ---- availability summary (by vessel type) ----
    def test_availability_summary_aggregates_by_type(self):
        """Counts per vessel type x availability status are real DB aggregates.
        Fixture: handysize=open, supramax=laden, panamax=open, capesize=fixed."""
        resp = self.client.get(reverse("v1:vessels:vessel-availability-summary"))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.json()["data"]
        by_type = {r["vessel_type"]: r for r in data["by_type"]}

        self.assertEqual(by_type["handysize"]["total"], 1)
        self.assertEqual(by_type["handysize"]["open"], 1)
        self.assertEqual(by_type["supramax"]["laden"], 1)
        self.assertEqual(by_type["supramax"]["open"], 0)
        self.assertEqual(by_type["panamax"]["open"], 1)
        self.assertEqual(by_type["capesize"]["fixed"], 1)
        # open_dwt sums only the OPEN vessels of that type.
        self.assertEqual(by_type["panamax"]["open_dwt"], "82000.00")
        # Totals across all types.
        self.assertEqual(data["totals"]["total"], 4)
        self.assertEqual(data["totals"]["open"], 2)
        self.assertEqual(data["totals"]["laden"], 1)
        self.assertEqual(data["totals"]["fixed"], 1)

    def test_availability_summary_respects_filters(self):
        """A list filter (dwt_min) narrows the summary too."""
        resp = self.client.get(
            reverse("v1:vessels:vessel-availability-summary"), {"dwt_min": "100000"}
        )
        data = resp.json()["data"]
        # Only the capesize (180k DWT) qualifies.
        self.assertEqual(data["totals"]["total"], 1)
        by_type = {r["vessel_type"]: r for r in data["by_type"]}
        self.assertIn("capesize", by_type)
        self.assertNotIn("panamax", by_type)

    # ---- filter by vessel type ----
    def test_filter_by_vessel_type(self):
        for vtype, name in [
            ("handysize", "Handy One"),
            ("supramax", "Supra Two"),
            ("panamax", "Pana Three"),
            ("capesize", "Cape Four"),
        ]:
            resp = self.client.get(
                reverse("v1:vessels:vessel-list"), {"vessel_type": vtype}
            )
            names = [v["name"] for v in resp.json()["data"]]
            self.assertEqual(names, [name], f"vessel_type={vtype}")

    # ---- filter by DWT ----
    def test_filter_by_dwt_range(self):
        resp = self.client.get(
            reverse("v1:vessels:vessel-list"), {"dwt_min": "50000", "dwt_max": "100000"}
        )
        names = {v["name"] for v in resp.json()["data"]}
        self.assertEqual(names, {"Supra Two", "Pana Three"})

    # ---- filter by draft ----
    def test_filter_by_draft_max(self):
        resp = self.client.get(
            reverse("v1:vessels:vessel-list"), {"draft_max": "13"}
        )
        names = {v["name"] for v in resp.json()["data"]}
        self.assertEqual(names, {"Handy One", "Supra Two"})

    # ---- filter by current position (bounding box) ----
    def test_filter_by_current_position_bbox(self):
        # Bay of Bengal box captures the Panamax's latest position only.
        resp = self.client.get(
            reverse("v1:vessels:vessel-list"),
            {"min_lat": "10", "max_lat": "22", "min_lon": "80", "max_lon": "95"},
        )
        names = [v["name"] for v in resp.json()["data"]]
        self.assertEqual(names, ["Pana Three"])

    def test_position_bbox_excludes_far_vessel(self):
        resp = self.client.get(
            reverse("v1:vessels:vessel-list"),
            {"min_lat": "10", "max_lat": "22", "min_lon": "80", "max_lon": "95"},
        )
        names = [v["name"] for v in resp.json()["data"]]
        self.assertNotIn("Cape Four", names)

    # ---- availability ----
    def test_availability_endpoint_returns_only_open(self):
        resp = self.client.get(reverse("v1:vessels:vessel-available"))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        body = resp.json()
        names = {v["name"] for v in body["data"]}
        self.assertEqual(names, {"Handy One", "Pana Three"})
        self.assertTrue(
            all(v["availability_status"] == "open" for v in body["data"])
        )

    def test_filter_by_availability_status(self):
        resp = self.client.get(
            reverse("v1:vessels:vessel-list"), {"availability_status": "fixed"}
        )
        names = [v["name"] for v in resp.json()["data"]]
        self.assertEqual(names, ["Cape Four"])

    def test_available_combined_with_type_filter(self):
        resp = self.client.get(
            reverse("v1:vessels:vessel-available"), {"vessel_type": "panamax"}
        )
        names = [v["name"] for v in resp.json()["data"]]
        self.assertEqual(names, ["Pana Three"])

    # ---- pagination ----
    def test_pagination_page_size(self):
        resp = self.client.get(reverse("v1:vessels:vessel-list"), {"page_size": "2"})
        body = resp.json()
        self.assertEqual(len(body["data"]), 2)
        self.assertEqual(body["pagination"]["page_size"], 2)
        self.assertEqual(body["pagination"]["num_pages"], 2)

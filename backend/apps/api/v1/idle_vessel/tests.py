"""API tests for the idle-vessel employment endpoint."""
from decimal import Decimal

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.catalog.models import Vessel


class IdleVesselApiTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.vessel = Vessel.objects.create(
            imo="3000001", name="Idle One", vessel_type=Vessel.VesselType.SUPRAMAX,
            dwt=Decimal("58000"), loa=Decimal("200"), beam=Decimal("32"),
            draft=Decimal("12.5"), speed=Decimal("13.0"),
            availability_status=Vessel.AvailabilityStatus.OPEN,
        )

    def _url(self):
        return reverse("v1:idle_vessel:rank")

    def _body(self, **overrides):
        body = {
            "vessel_id": self.vessel.pk,
            "opportunities": [
                {"name": "Near cargo", "laden_distance_nm": "2000",
                 "cargo_tonnes": "55000", "freight_rate_per_tonne": "18",
                 "ballast_distance_nm": "300", "bunker_price_per_tonne": "600"},
                {"name": "Far cargo", "laden_distance_nm": "6000",
                 "cargo_tonnes": "55000", "freight_rate_per_tonne": "18",
                 "ballast_distance_nm": "2500", "bunker_price_per_tonne": "600"},
            ],
        }
        body.update(overrides)
        return body

    def test_happy_path_ranks_by_margin(self):
        resp = self.client.post(self._url(), self._body(), format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.json()["data"]
        self.assertTrue(len(data["ranked_opportunities"]) >= 1)
        # Nearer, cheaper-to-serve cargo should out-rank the far one (higher margin/day).
        names = [o["name"] for o in data["ranked_opportunities"]]
        self.assertEqual(names[0], "Near cargo")
        for o in data["ranked_opportunities"]:
            for f in ("expected_revenue", "expected_cost", "expected_margin", "currency"):
                self.assertIn(f, o)

    def test_unknown_vessel_returns_400(self):
        resp = self.client.post(self._url(), self._body(vessel_id=999999), format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_no_opportunities_rejected(self):
        resp = self.client.post(self._url(), self._body(opportunities=[]), format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

"""API tests for the vessel recommendations endpoint.

Covers: ranked output shape + per-candidate fields (compatibility, estimated
freight, ETA, demurrage, risk, suitability score, estimated total cost),
automatic exclusion of incompatible vessels, ranking order (suitability desc),
vessel-type roll-up, input validation, graceful missing-route handling, and the
consistent response envelope.
"""
from datetime import date, datetime, timezone as dt_timezone
from decimal import Decimal

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.catalog.models import Origin, Port, Route, Vessel
from apps.operations.models import FreightForecast


class VesselRecommendationApiTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.origin, _ = Origin.objects.get_or_create(
            name="Australia", defaults={"country": "Australia"}
        )
        # Paradip is seeded by a migration; reuse it and set a documented max
        # draft limit (metadata) so the deep-draft capesize is incompatible.
        cls.port, _ = Port.objects.get_or_create(
            name="Paradip", country="India",
            defaults={"latitude": Decimal("20.26"), "longitude": Decimal("86.67")},
        )
        cls.port.metadata = {"max_draft_m": {"value": "16.0", "source": "test"}}
        cls.port.save(update_fields=["metadata"])
        cls.route = Route.objects.create(
            origin=cls.origin, destination_port=cls.port,
            distance_nm=Decimal("6500"),
        )

        # A market freight band for supramax on this lane (latest forecast).
        FreightForecast.objects.create(
            route=cls.route, vessel_type=Vessel.VesselType.SUPRAMAX,
            generated_at=datetime(2026, 9, 1, tzinfo=dt_timezone.utc),
            target_date=date(2026, 10, 1),
            horizon=FreightForecast.Horizon.SHORT_TERM,
            predicted_rate_per_tonne=Decimal("22.00"),
            lower_bound=Decimal("18.00"), upper_bound=Decimal("26.00"),
            confidence=Decimal("0.80"),
            model_name="test", model_version="0.1.0",
        )

        # --- candidate vessels (all OPEN so they are considered) ---
        # A well-fitting supramax (feasible draft, has service speed).
        cls.supra = Vessel.objects.create(
            imo="2000001", name="Supra Fit", vessel_type=Vessel.VesselType.SUPRAMAX,
            dwt=Decimal("58000"), loa=Decimal("200"), beam=Decimal("32"),
            draft=Decimal("12.5"), speed=Decimal("13.0"),
            availability_status=Vessel.AvailabilityStatus.OPEN,
        )
        # A panamax, also feasible.
        cls.pana = Vessel.objects.create(
            imo="2000002", name="Pana Fit", vessel_type=Vessel.VesselType.PANAMAX,
            dwt=Decimal("82000"), loa=Decimal("229"), beam=Decimal("32.2"),
            draft=Decimal("14.4"), speed=Decimal("12.5"),
            availability_status=Vessel.AvailabilityStatus.OPEN,
        )
        # A capesize whose draft (18.1) EXCEEDS the port's 16.0 limit ->
        # INCOMPATIBLE -> must be excluded automatically.
        cls.cape = Vessel.objects.create(
            imo="2000003", name="Cape Deep", vessel_type=Vessel.VesselType.CAPESIZE,
            dwt=Decimal("180000"), loa=Decimal("292"), beam=Decimal("45"),
            draft=Decimal("18.1"), speed=Decimal("12.0"),
            availability_status=Vessel.AvailabilityStatus.OPEN,
        )
        # A LADEN vessel that should be ignored when only_available (default).
        cls.laden = Vessel.objects.create(
            imo="2000004", name="Busy Boat", vessel_type=Vessel.VesselType.SUPRAMAX,
            dwt=Decimal("57000"), loa=Decimal("199"), beam=Decimal("32"),
            draft=Decimal("12.4"), speed=Decimal("13.0"),
            availability_status=Vessel.AvailabilityStatus.LADEN,
        )

    def _url(self):
        return reverse("v1:recommendations:vessels")

    def _body(self, **overrides):
        body = {
            "origin": "Australia",
            "destination": "Paradip",
            "cargo_tonnes": "55000",
            "commodity": "Coal",
            "laycan_start": "2026-10-01",
            "laycan_end": "2026-10-10",
            "bunker_price_per_tonne": "600",
        }
        body.update(overrides)
        return body

    # ------------------------------------------------------------------
    def test_happy_path_returns_ranked_candidates_with_all_fields(self):
        resp = self.client.post(self._url(), self._body(), format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        body = resp.json()
        self.assertTrue(body["success"])
        self.assertIsNone(body["errors"])
        data = body["data"]

        self.assertTrue(data["route_resolved"])
        self.assertTrue(len(data["ranked_vessels"]) >= 1)

        # Every candidate exposes the required fields.
        for cand in data["ranked_vessels"]:
            for f in (
                "vessel_id", "vessel_name", "imo", "vessel_type",
                "suitability_score", "compatibility", "estimated_freight",
                "eta", "demurrage", "risk", "estimated_total_cost",
                "suitability",
            ):
                self.assertIn(f, cand)
            # Suitability score is bounded 0..100.
            self.assertGreaterEqual(cand["suitability_score"], 0.0)
            self.assertLessEqual(cand["suitability_score"], 100.0)
            # Explainable suitability breakdown present.
            self.assertIn("factors", cand["suitability"])

    def test_incompatible_vessel_is_excluded_automatically(self):
        resp = self.client.post(self._url(), self._body(), format="json")
        data = resp.json()["data"]

        ranked_imos = {c["imo"] for c in data["ranked_vessels"]}
        excluded_imos = {e["imo"] for e in data["excluded_vessels"]}

        # The deep-draft capesize (18.1m > 16.0m limit) is excluded, not ranked.
        self.assertIn("2000003", excluded_imos)
        self.assertNotIn("2000003", ranked_imos)
        # The exclusion carries a reason + compatibility breakdown.
        cape = next(e for e in data["excluded_vessels"] if e["imo"] == "2000003")
        self.assertTrue(cape["reason"])
        self.assertEqual(
            cape["compatibility"]["status"].lower(), "incompatible"
        )

    def test_only_available_excludes_laden_vessel(self):
        resp = self.client.post(self._url(), self._body(), format="json")
        data = resp.json()["data"]
        all_imos = {c["imo"] for c in data["ranked_vessels"]} | {
            e["imo"] for e in data["excluded_vessels"]
        }
        # LADEN vessel is not even considered by default.
        self.assertNotIn("2000004", all_imos)

    def test_only_available_false_considers_all_vessels(self):
        resp = self.client.post(
            self._url(), self._body(only_available=False), format="json"
        )
        data = resp.json()["data"]
        all_imos = {c["imo"] for c in data["ranked_vessels"]} | {
            e["imo"] for e in data["excluded_vessels"]
        }
        self.assertIn("2000004", all_imos)  # LADEN now considered

    def test_ranked_vessels_sorted_by_suitability_desc(self):
        resp = self.client.post(self._url(), self._body(), format="json")
        scores = [c["suitability_score"] for c in resp.json()["data"]["ranked_vessels"]]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_vessel_type_rollup_present_and_ranked(self):
        resp = self.client.post(self._url(), self._body(), format="json")
        types = resp.json()["data"]["ranked_vessel_types"]
        self.assertTrue(len(types) >= 1)
        for row in types:
            for f in ("vessel_type", "candidate_count",
                      "best_suitability_score", "avg_suitability_score"):
                self.assertIn(f, row)
        best = [t["best_suitability_score"] for t in types]
        self.assertEqual(best, sorted(best, reverse=True))

    def test_estimated_freight_and_total_cost_carry_currency(self):
        resp = self.client.post(self._url(), self._body(), format="json")
        # The supramax has a market freight band + speed -> voyage economics run.
        supra = next(
            c for c in resp.json()["data"]["ranked_vessels"] if c["imo"] == "2000001"
        )
        self.assertIsNotNone(supra["estimated_total_cost"])
        self.assertEqual(supra["estimated_total_cost"]["currency"], "USD")
        self.assertEqual(supra["estimated_total_cost"]["unit"], "total")
        self.assertIsNotNone(supra["estimated_freight"])
        self.assertEqual(supra["estimated_freight"]["currency"], "USD")
        # ETA computed (route has distance + vessel has speed).
        self.assertIsNotNone(supra["eta"])
        for f in ("eta", "eta_p50", "eta_p80", "eta_p95"):
            self.assertIn(f, supra["eta"])

    def test_missing_route_is_graceful(self):
        resp = self.client.post(
            self._url(), self._body(destination="Kolkata"), format="json"
        )
        # Kolkata has no port/route here -> 200 with a note, no ranked vessels
        # excluded on compatibility (port unknown).
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.json()["data"]
        self.assertFalse(data["route_resolved"])
        self.assertTrue(any("route" in n.lower() for n in data["notes"]))

    def test_bad_laycan_returns_400(self):
        resp = self.client.post(
            self._url(),
            self._body(laycan_start="2026-10-10", laycan_end="2026-10-01"),
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        body = resp.json()
        self.assertFalse(body["success"])
        self.assertTrue(any(e.get("field") == "laycan_end" for e in body["errors"]))

    def test_missing_required_field_returns_400(self):
        body = self._body()
        del body["destination"]
        resp = self.client.post(self._url(), body, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        errors = resp.json()["errors"]
        self.assertTrue(any(e.get("field") == "destination" for e in errors))

    def test_zero_cargo_returns_400(self):
        resp = self.client.post(
            self._url(), self._body(cargo_tonnes="0"), format="json"
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_deterministic(self):
        r1 = self.client.post(self._url(), self._body(), format="json").json()["data"]
        r2 = self.client.post(self._url(), self._body(), format="json").json()["data"]
        s1 = [(c["imo"], c["suitability_score"]) for c in r1["ranked_vessels"]]
        s2 = [(c["imo"], c["suitability_score"]) for c in r2["ranked_vessels"]]
        self.assertEqual(s1, s2)

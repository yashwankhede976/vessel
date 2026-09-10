"""API tests for the unified decision endpoint + assistant.

Exercises the full flow: cargo input -> forecast -> vessel -> port -> cost ->
contract -> recommendation, plus explainability, scenario overrides, the
assistant intents, and validation.
"""
from datetime import date, timedelta
from decimal import Decimal

from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.catalog.models import Origin, Port, Route, Vessel
from apps.operations.models import FreightForecast


class DecisionApiTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.origin, _ = Origin.objects.get_or_create(
            name="Australia", defaults={"country": "Australia"}
        )
        # Paradip is seeded by a migration; reuse it.
        cls.port, _ = Port.objects.get_or_create(
            name="Paradip", country="India",
            defaults={"latitude": Decimal("20.26"), "longitude": Decimal("86.67")},
        )
        cls.route, _ = Route.objects.get_or_create(
            origin=cls.origin, destination_port=cls.port,
            defaults={"distance_nm": Decimal("6500")},
        )
        # A compatible open panamax (draft comfortably within any port limit).
        cls.vessel = Vessel.objects.create(
            imo="4200001", name="Pana Fit", vessel_type=Vessel.VesselType.PANAMAX,
            dwt=Decimal("80000"), loa=Decimal("229"), beam=Decimal("32"),
            draft=Decimal("13.5"), speed=Decimal("13.0"),
            availability_status=Vessel.AvailabilityStatus.OPEN,
        )
        # A stored freight forecast so the forecast band + model version populate.
        FreightForecast.objects.create(
            route=cls.route, vessel_type=Vessel.VesselType.PANAMAX,
            generated_at=timezone.now(), target_date=date.today() + timedelta(days=10),
            horizon=FreightForecast.Horizon.SHORT_TERM,
            predicted_rate_per_tonne=Decimal("22.00"),
            lower_bound=Decimal("20.00"), upper_bound=Decimal("24.00"),
            confidence=Decimal("0.80"), model_name="freight_gbm_xgboost",
            model_version="0.2.0",
        )

    def _url(self):
        return reverse("v1:decision:evaluate")

    def _body(self, **over):
        body = {
            "commodity": "Coal", "cargo_quantity": "75000",
            "origin": "Australia", "destination": "Paradip",
            "laycan_start": "2026-10-01", "laycan_end": "2026-10-15",
            "required_arrival": "2026-10-20",
        }
        body.update(over)
        return body

    def test_full_flow_returns_all_sections(self):
        resp = self.client.post(self._url(), self._body(), format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        body = resp.json()
        self.assertTrue(body["success"])
        data = body["data"]
        for section in (
            "market", "freight_forecast", "recommended_vessel", "compatibility",
            "congestion", "eta", "demurrage", "total_landed_cost",
            "recommended_contract", "risk", "timing_decision", "expected_savings",
            "confidence", "explainability",
        ):
            self.assertIn(section, data)
        # A vessel was recommended and the timing decision is one of the four.
        self.assertEqual(data["recommended_vessel"]["vessel_name"], "Pana Fit")
        self.assertIn(data["timing_decision"], ["FIX_NOW", "WAIT", "PARTIAL_FIX", "MONITOR"])

    def test_explainability_present(self):
        data = self.client.post(self._url(), self._body(), format="json").json()["data"]
        ex = data["explainability"]
        for f in ("reasons", "positive_factors", "negative_factors", "model_version", "data_freshness"):
            self.assertIn(f, ex)
        self.assertTrue(len(ex["reasons"]) > 0)
        # Freight model version flows through from the stored forecast.
        self.assertEqual(ex["model_version"]["freight_model_version"], "0.2.0")

    def test_forecast_band_from_stored_forecast(self):
        data = self.client.post(self._url(), self._body(), format="json").json()["data"]
        band = data["freight_forecast"]["band"]
        self.assertEqual(band["mid"], "22.00")
        self.assertEqual(data["freight_forecast"]["source"], "FreightForecast")

    def test_scenario_freight_change_shifts_working_rate(self):
        base = self.client.post(self._url(), self._body(), format="json").json()["data"]
        scen = self.client.post(
            self._url(), self._body(scenario={"freight_change_pct": 10}), format="json"
        ).json()["data"]
        # +10% on the 22.00 working rate -> 24.20.
        self.assertEqual(scen["freight_forecast"]["working_rate"], "24.20")
        self.assertNotEqual(base["freight_forecast"]["working_rate"], scen["freight_forecast"]["working_rate"])
        self.assertEqual(scen["scenario"]["freight_change_pct"], 10)

    def test_scenario_congestion_tightens_market(self):
        scen = self.client.post(
            self._url(), self._body(scenario={"congestion_score": 90}), format="json"
        ).json()["data"]
        self.assertEqual(scen["congestion"]["score"], 90.0)

    def test_bad_laycan_returns_400(self):
        resp = self.client.post(
            self._url(), self._body(laycan_start="2026-10-15", laycan_end="2026-10-01"),
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(resp.json()["success"])

    def test_zero_cargo_returns_400(self):
        resp = self.client.post(self._url(), self._body(cargo_quantity="0"), format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_lane_freight_band_fallback_when_type_mismatch(self):
        """Regression: a forecast for a DIFFERENT vessel type than the one
        recommended must still populate the band + a non-zero total cost via the
        lane-wide fallback (was silently dropping to the planning default)."""
        # The only forecast in setUp is panamax and the recommended open vessel
        # is the panamax "Pana Fit" — add a capesize-only forecast lane check by
        # recommending against a fresh lane where the forecast type differs.
        # Here: delete the panamax forecast and add a kamsarmax one; the
        # recommended vessel is still panamax, so only the lane fallback can
        # supply the band.
        FreightForecast.objects.all().delete()
        FreightForecast.objects.create(
            route=self.route, vessel_type=Vessel.VesselType.KAMSARMAX,
            generated_at=timezone.now(), target_date=date.today() + timedelta(days=10),
            horizon=FreightForecast.Horizon.SHORT_TERM,
            predicted_rate_per_tonne=Decimal("16.50"),
            lower_bound=Decimal("15.00"), upper_bound=Decimal("18.00"),
            confidence=Decimal("0.78"), model_name="freight_gbm_xgboost",
            model_version="0.2.0",
        )
        data = self.client.post(self._url(), self._body(), format="json").json()["data"]
        self.assertEqual(data["freight_forecast"]["source"], "FreightForecast")
        self.assertEqual(data["freight_forecast"]["band"]["mid"], "16.50")
        # Total cost is grounded in the working rate, not zero.
        self.assertNotEqual(data["total_landed_cost"]["amount"], "0.00")


class AssistantApiTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.origin, _ = Origin.objects.get_or_create(
            name="Australia", defaults={"country": "Australia"}
        )
        cls.port, _ = Port.objects.get_or_create(
            name="Paradip", country="India",
            defaults={"latitude": Decimal("20.26"), "longitude": Decimal("86.67")},
        )
        Route.objects.get_or_create(
            origin=cls.origin, destination_port=cls.port,
            defaults={"distance_nm": Decimal("6500")},
        )
        Vessel.objects.create(
            imo="4200002", name="Pana Fit", vessel_type=Vessel.VesselType.PANAMAX,
            dwt=Decimal("80000"), loa=Decimal("229"), beam=Decimal("32"),
            draft=Decimal("13.5"), speed=Decimal("13.0"),
            availability_status=Vessel.AvailabilityStatus.OPEN,
        )

    def _url(self):
        return reverse("v1:decision:assistant")

    def _ask(self, q):
        resp = self.client.post(self._url(), {"question": q}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        return resp.json()["data"]

    def test_fix_or_wait_intent(self):
        d = self._ask("Should I fix Australia to Paradip?")
        self.assertEqual(d["intent"], "fix_or_wait")
        self.assertTrue(d["grounded"])
        self.assertTrue(len(d["answer"]) > 0)

    def test_best_vessel_intent(self):
        d = self._ask("Which vessel is best?")
        self.assertEqual(d["intent"], "best_vessel")

    def test_compare_ports_intent(self):
        d = self._ask("Is Dhamra better than Paradip?")
        self.assertEqual(d["intent"], "compare_ports")

    def test_contract_intent(self):
        d = self._ask("Spot or multi-voyage?")
        self.assertEqual(d["intent"], "contract_choice")

    def test_freight_scenario_intent(self):
        d = self._ask("What happens if freight increases 10%?")
        self.assertEqual(d["intent"], "freight_scenario")
        self.assertEqual(d["data"]["scenario"]["freight_change_pct"], 10.0)

    def test_missing_question_returns_400(self):
        resp = self.client.post(self._url(), {}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

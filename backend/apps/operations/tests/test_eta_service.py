"""Integration tests for the ETA service adapter (models -> engine)."""
from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from apps.catalog.models import Origin, Port, Route, Vessel
from apps.operations.models import AISPosition
from apps.operations.services.eta import ETAValidationError
from apps.operations.services.eta_service import build_eta_input, predict_vessel_eta


class ETAServiceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.port, _ = Port.objects.get_or_create(
            name="Paradip", country="India",
            defaults={"latitude": "20.26", "longitude": "86.67"},
        )
        cls.origin = Origin.objects.create(name="Australia", country="Australia")
        cls.route = Route.objects.create(
            origin=cls.origin, destination_port=cls.port,
            distance_nm=Decimal("5200.00"),
        )
        cls.vessel = Vessel.objects.create(
            imo="9700001", name="V-ETA", dwt=Decimal("180000"),
            loa=Decimal("290"), beam=Decimal("45"), draft=Decimal("17"),
            speed=Decimal("14.0"),
        )

    def test_uses_ais_sog_for_speed(self):
        AISPosition.objects.create(
            vessel=self.vessel, mmsi="412000001", timestamp=timezone.now(),
            latitude=Decimal("12.5"), longitude=Decimal("84.0"),
            sog=Decimal("11.5"),
        )
        inp = build_eta_input(self.vessel, self.route)
        self.assertEqual(inp.speed_kn, 11.5)          # SOG preferred
        self.assertEqual(inp.route_distance_nm, 5200.0)
        self.assertEqual(inp.latitude, 12.5)

    def test_falls_back_to_service_speed(self):
        # No AIS position -> use the vessel's service speed.
        inp = build_eta_input(self.vessel, self.route)
        self.assertEqual(inp.speed_kn, 14.0)

    def test_end_to_end_prediction(self):
        result = predict_vessel_eta(self.vessel, self.route)
        d = result.to_dict()
        self.assertLessEqual(d["eta_p50"], d["eta_p80"])
        self.assertLessEqual(d["eta_p80"], d["eta_p95"])
        self.assertTrue(d["total_hours"] > 0)

    def test_missing_distance_and_speed_raises(self):
        route = Route.objects.create(
            origin=Origin.objects.create(name="Indonesia", country="Indonesia"),
            destination_port=self.port,  # no distance_nm
        )
        vessel = Vessel.objects.create(
            imo="9700002", name="No-Speed", dwt=Decimal("80000"),
            loa=Decimal("225"), beam=Decimal("32"), draft=Decimal("14"),
        )  # no service speed, no AIS
        with self.assertRaises(ETAValidationError):
            predict_vessel_eta(vessel, route)

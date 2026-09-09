"""Integration tests for the compatibility service adapter (ORM -> engine)."""
from decimal import Decimal

from django.test import TestCase

from apps.catalog.models import Berth, Commodity, Port, Vessel
from apps.catalog.services.compatibility import Status
from apps.catalog.services.service import evaluate_compatibility


class CompatibilityServiceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.coal = Commodity.objects.create(
            name="Thermal Coal", category=Commodity.Category.COAL_THERMAL
        )
        cls.port = Port.objects.create(
            name="Test Port",
            country="India",
            coast=Port.Coast.EAST_COAST_INDIA,
            latitude=Decimal("20"),
            longitude=Decimal("86"),
            metadata={
                "max_dwt_t": {"value": "120000", "source": "test", "source_date": "2026-09-08"},
                "operational_constraints": {
                    "value": "Daytime berthing only for large vessels.",
                    "source": "test",
                    "source_date": "2026-09-08",
                },
            },
        )
        cls.berth = Berth.objects.create(
            port=cls.port,
            berth_name="B1",
            max_loa=Decimal("230"),
            max_beam=Decimal("40"),
            max_draft=Decimal("14.5"),
            handling_rate=Decimal("0"),  # unknown per seed convention
        )
        cls.berth.supported_commodities.add(cls.coal)

        cls.vessel = Vessel.objects.create(
            imo="9600001",
            name="Test Vessel",
            vessel_type=Vessel.VesselType.PANAMAX,
            dwt=Decimal("82000"),
            loa=Decimal("225"),
            beam=Decimal("32.2"),
            draft=Decimal("13.5"),
        )

    def test_compatible_vessel_with_documented_restriction_is_conditional(self):
        # The port has a documented operational restriction, which the adapter
        # surfaces as a conditional caveat.
        result = evaluate_compatibility(
            self.vessel, self.port, self.berth, cargo="Thermal Coal"
        )
        self.assertEqual(result.status, Status.CONDITIONAL)
        self.assertTrue(any("operational restriction" in r.lower() for r in result.reasons))

    def test_oversized_vessel_is_incompatible(self):
        big = Vessel.objects.create(
            imo="9600002",
            name="Big Cape",
            vessel_type=Vessel.VesselType.CAPESIZE,
            dwt=Decimal("180000"),
            loa=Decimal("290"),
            beam=Decimal("45"),
            draft=Decimal("18"),
        )
        result = evaluate_compatibility(big, self.port, self.berth, cargo="Thermal Coal")
        self.assertEqual(result.status, Status.INCOMPATIBLE)
        self.assertTrue(any("LOA" in r for r in result.reasons))

    def test_wrong_cargo_is_incompatible(self):
        result = evaluate_compatibility(
            self.vessel, self.port, self.berth, cargo="Crude Oil"
        )
        self.assertEqual(result.status, Status.INCOMPATIBLE)

    def test_port_only_uses_metadata_limits(self):
        # No berth given: adapter falls back to port metadata (which has no
        # LOA/beam/draft here) -> those become UNKNOWN, DWT is known.
        result = evaluate_compatibility(self.vessel, self.port, None, cargo="Thermal Coal")
        # DWT passes; dimensions unknown; restriction conditional.
        self.assertIn(result.status, {Status.CONDITIONAL})
        self.assertTrue(any("could not be evaluated" in r for r in result.reasons))

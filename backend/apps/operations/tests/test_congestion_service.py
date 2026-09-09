"""Integration tests for the congestion service adapter (models -> engine)."""
from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from apps.catalog.models import Port, Vessel
from apps.operations.models import (
    MarineObservation,
    PortCall,
    PortCongestionObservation,
)
from apps.operations.services.congestion_service import (
    build_congestion_input,
    score_port_congestion,
)


class CongestionServiceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.port, _ = Port.objects.get_or_create(
            name="Paradip", country="India",
            defaults={"latitude": "20.26", "longitude": "86.67"},
        )

    def test_reads_latest_congestion_observation(self):
        now = timezone.now()
        # Older then newer observation; the newer should be used.
        PortCongestionObservation.objects.create(
            port=self.port, observed_at=now - timedelta(days=2),
            vessels_waiting=2, avg_wait_days=Decimal("1.0"),
        )
        PortCongestionObservation.objects.create(
            port=self.port, observed_at=now,
            vessels_waiting=12, avg_wait_days=Decimal("5.5"),
        )
        inp = build_congestion_input(self.port)
        self.assertEqual(inp.vessels_waiting, 12)
        self.assertEqual(inp.recent_waiting_time_days, 5.5)

    def test_expected_arrivals_from_port_calls(self):
        now = timezone.now()
        v1 = Vessel.objects.create(
            imo="9800001", name="V1", dwt=Decimal("80000"), loa=Decimal("225"),
            beam=Decimal("32"), draft=Decimal("14"),
        )
        v2 = Vessel.objects.create(
            imo="9800002", name="V2", dwt=Decimal("80000"), loa=Decimal("225"),
            beam=Decimal("32"), draft=Decimal("14"),
        )
        # One future arrival (counts), one past (does not).
        PortCall.objects.create(port=self.port, vessel=v1, arrival_at=now + timedelta(days=2))
        PortCall.objects.create(port=self.port, vessel=v2, arrival_at=now - timedelta(days=2))
        inp = build_congestion_input(self.port)
        self.assertEqual(inp.expected_arrivals, 1)

    def test_missing_signals_are_none(self):
        # No observations for this port -> all model-derived signals None.
        empty_port, _ = Port.objects.get_or_create(
            name="Gopalpur", country="India",
            defaults={"latitude": "19.29", "longitude": "84.96"},
        )
        inp = build_congestion_input(empty_port)
        self.assertIsNone(inp.vessels_waiting)
        self.assertIsNone(inp.recent_waiting_time_days)
        self.assertIsNone(inp.expected_arrivals)
        self.assertIsNone(inp.historical_traffic)

    def test_weather_severity_mapped(self):
        MarineObservation.objects.create(
            port=self.port, timestamp=timezone.now(), severity="high",
            warning_type="port_warning",
        )
        inp = build_congestion_input(self.port)
        self.assertEqual(inp.weather_warning, "high")

    def test_score_port_congestion_end_to_end(self):
        PortCongestionObservation.objects.create(
            port=self.port, observed_at=timezone.now(),
            vessels_waiting=14, avg_wait_days=Decimal("6.0"),
        )
        result = score_port_congestion(self.port)
        self.assertGreater(result.congestion_score, 0)
        self.assertIn(result.classification, {"LOW", "MEDIUM", "HIGH", "SEVERE"})
        # Explainability: inputs recorded.
        self.assertEqual(result.inputs["vessels_waiting"], 14)

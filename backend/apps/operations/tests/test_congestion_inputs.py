"""Tests for automatic congestion-input derivation."""
from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from apps.catalog.models import Port
from apps.operations.models import (
    AISPosition,
    PortCongestionObservation,
    PortTraffic,
)
from apps.operations.services.congestion_inputs import (
    derive_congestion_input,
    score_port_congestion_enriched,
)


class DeriveCongestionInputTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.port, _ = Port.objects.get_or_create(
            name="Paradip", country="India",
            defaults={"latitude": Decimal("20.26"), "longitude": Decimal("86.67")},
        )

    def test_derives_vessels_near_port_from_ais(self):
        now = timezone.now()
        for i in range(3):
            AISPosition.objects.create(
                mmsi=f"80000000{i}", timestamp=now,
                latitude=Decimal("20.30"), longitude=Decimal("86.70"),
            )
        result = derive_congestion_input(self.port, now=now)
        self.assertEqual(result.derived["vessels_near_port"], 3)
        self.assertEqual(result.congestion_input.vessels_near_port, 3)

    def test_derives_throughput_utilization_from_port_traffic(self):
        now = timezone.now()
        PortTraffic.objects.create(
            port=self.port, period=now.date(), direction="import",
            throughput_tonnes=Decimal("1000000"), source="test",
        )
        result = derive_congestion_input(
            self.port, throughput_capacity_tonnes=2_000_000, now=now
        )
        self.assertAlmostEqual(
            result.congestion_input.throughput_utilization, 0.5, places=3
        )

    def test_missing_signals_stay_none(self):
        # No AIS, no traffic -> those signals are None (excluded, not fabricated).
        result = derive_congestion_input(self.port)
        self.assertIsNone(result.congestion_input.throughput_utilization)
        # vessels_near_port is 0 (port has coords, just no vessels) — that's a
        # real count, not missing.
        self.assertEqual(result.congestion_input.vessels_near_port, 0)

    def test_reuses_waiting_from_congestion_observation(self):
        PortCongestionObservation.objects.create(
            port=self.port, observed_at=timezone.now(),
            vessels_waiting=7, avg_wait_days=Decimal("3.5"), source="test",
        )
        result = derive_congestion_input(self.port)
        self.assertEqual(result.congestion_input.vessels_waiting, 7)

    def test_score_enriched_returns_result(self):
        now = timezone.now()
        AISPosition.objects.create(
            mmsi="810000000", timestamp=now,
            latitude=Decimal("20.30"), longitude=Decimal("86.70"),
        )
        res = score_port_congestion_enriched(self.port, now=now)
        self.assertTrue(0 <= res.congestion_score <= 100)

"""Unit/integration tests for derived AIS features."""
from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from apps.catalog.models import Port, Vessel
from apps.operations.models import AISPosition
from apps.operations.services.ais_features import (
    arrival_probability,
    distance_to_port,
    haversine_nm,
    nearest_port,
    speed_trend,
    traffic_density,
)


class HaversineTests(TestCase):
    def test_zero_distance(self):
        self.assertAlmostEqual(haversine_nm(20, 86, 20, 86), 0.0, places=3)

    def test_known_pair(self):
        # Paradip ~ Visakhapatnam ~ 250 nm.
        d = haversine_nm(20.26, 86.67, 17.68, 83.21)
        self.assertTrue(240 < d < 260)


class PortFeatureTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.paradip, _ = Port.objects.get_or_create(
            name="Paradip", country="India",
            defaults={"latitude": Decimal("20.26"), "longitude": Decimal("86.67")},
        )
        cls.vizag, _ = Port.objects.get_or_create(
            name="Visakhapatnam", country="India",
            defaults={"latitude": Decimal("17.68"), "longitude": Decimal("83.21")},
        )

    def test_distance_to_port(self):
        d = distance_to_port(Decimal("20.30"), Decimal("86.70"), self.paradip)
        self.assertIsNotNone(d)
        self.assertTrue(d < 5)  # very close

    def test_nearest_port(self):
        np = nearest_port(Decimal("20.30"), Decimal("86.70"))
        self.assertIsNotNone(np)
        self.assertEqual(np.port_name, "Paradip")

    def test_nearest_port_none_for_bad_coords(self):
        self.assertIsNone(nearest_port(None, None))

    def test_traffic_density_counts_nearby_vessels(self):
        now = timezone.now()
        for i, (lat, lon) in enumerate([(20.3, 86.7), (20.4, 86.6), (5.0, 60.0)]):
            AISPosition.objects.create(
                mmsi=f"10000000{i}", timestamp=now,
                latitude=Decimal(str(lat)), longitude=Decimal(str(lon)),
            )
        # Two within ~50nm of Paradip, one far away.
        self.assertEqual(traffic_density(self.paradip, radius_nm=50, now=now), 2)

    def test_traffic_density_none_without_coords(self):
        p = Port.objects.create(name="NoCoord", country="X",
                                latitude=Decimal("0"), longitude=Decimal("0"))
        # 0,0 is valid but far from any vessel -> count 0, not None.
        self.assertEqual(traffic_density(p, now=timezone.now()), 0)


class SpeedTrendTests(TestCase):
    def test_slowing_trend_negative(self):
        now = timezone.now()
        for i, sog in enumerate([14, 12, 10, 8]):
            AISPosition.objects.create(
                mmsi="500000000", timestamp=now - timedelta(hours=3 - i),
                latitude=Decimal("20"), longitude=Decimal("86"),
                sog=Decimal(str(sog)),
            )
        trend = speed_trend("500000000", now=now)
        self.assertIsNotNone(trend)
        self.assertLess(trend, 0)  # decelerating

    def test_none_with_insufficient_samples(self):
        AISPosition.objects.create(
            mmsi="600000000", timestamp=timezone.now(),
            latitude=Decimal("20"), longitude=Decimal("86"), sog=Decimal("10"),
        )
        self.assertIsNone(speed_trend("600000000"))


class ArrivalProbabilityTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.port, _ = Port.objects.get_or_create(
            name="Paradip", country="India",
            defaults={"latitude": Decimal("20.26"), "longitude": Decimal("86.67")},
        )

    def test_close_and_moving_high_probability(self):
        pos = AISPosition(
            mmsi="700000000", timestamp=timezone.now(),
            latitude=Decimal("20.30"), longitude=Decimal("86.70"),
            sog=Decimal("11"), cog=Decimal("225"),
        )
        p = arrival_probability(pos, self.port)
        self.assertIsNotNone(p)
        self.assertGreater(p, 0.5)

    def test_far_and_heading_away_low_probability(self):
        # Far from Paradip (NE) and steaming away (south-west) at near-zero speed:
        # all three signals (proximity, heading alignment, making way) are low.
        pos = AISPosition(
            mmsi="700000001", timestamp=timezone.now(),
            latitude=Decimal("5"), longitude=Decimal("60"),
            sog=Decimal("0.1"), cog=Decimal("225"),
        )
        p = arrival_probability(pos, self.port)
        self.assertLess(p, 0.5)

    def test_far_is_lower_than_near(self):
        near = AISPosition(
            mmsi="a", timestamp=timezone.now(),
            latitude=Decimal("20.30"), longitude=Decimal("86.70"),
            sog=Decimal("11"), cog=Decimal("225"),
        )
        far = AISPosition(
            mmsi="b", timestamp=timezone.now(),
            latitude=Decimal("5"), longitude=Decimal("60"),
            sog=Decimal("11"), cog=Decimal("0"),
        )
        self.assertGreater(
            arrival_probability(near, self.port), arrival_probability(far, self.port)
        )

    def test_none_without_coords(self):
        pos = AISPosition(mmsi="x", timestamp=timezone.now(),
                          latitude=None, longitude=None)
        self.assertIsNone(arrival_probability(pos, self.port))

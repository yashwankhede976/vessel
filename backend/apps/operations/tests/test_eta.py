"""Unit tests for deterministic vessel ETA prediction."""
from datetime import datetime, timedelta, timezone

from django.test import SimpleTestCase

from apps.operations.services.eta import (
    ETAInput,
    ETAValidationError,
    HOURS_PER_DAY,
    predict_eta,
)

DEP = datetime(2026, 9, 1, tzinfo=timezone.utc)


def _iso_to_dt(s: str) -> datetime:
    return datetime.fromisoformat(s)


class BaseTransitTests(SimpleTestCase):
    def test_clean_voyage_base_transit_is_distance_over_speed(self):
        # 1000 nm at 10 kn, no delays -> 100 h; point ETA = departure + 100h.
        r = predict_eta(ETAInput(route_distance_nm=1000, speed_kn=10, departure_time=DEP))
        self.assertAlmostEqual(r.total_hours, 100.0, places=1)
        self.assertAlmostEqual(r.total_delay_hours, 0.0, places=2)
        eta = _iso_to_dt(r.eta)
        self.assertAlmostEqual((eta - DEP).total_seconds() / 3600.0, 100.0, places=1)

    def test_no_delay_p50_equals_point(self):
        r = predict_eta(ETAInput(route_distance_nm=1000, speed_kn=10, departure_time=DEP))
        self.assertEqual(r.eta, r.eta_p50)


class DelayCauseTests(SimpleTestCase):
    def _hours(self, **over):
        base = dict(route_distance_nm=1000, speed_kn=10, departure_time=DEP)
        base.update(over)
        return predict_eta(ETAInput(**base)).total_hours

    def test_weather_increases_eta(self):
        self.assertGreater(self._hours(weather_risk=0.5), self._hours(weather_risk=0.0))

    def test_congestion_increases_eta(self):
        self.assertGreater(self._hours(destination_congestion=80),
                           self._hours(destination_congestion=0))

    def test_port_waiting_increases_eta(self):
        # 3 days waiting adds exactly 72 h.
        base = self._hours()
        with_wait = self._hours(expected_port_waiting_days=3)
        self.assertAlmostEqual(with_wait - base, 3 * HOURS_PER_DAY, places=2)

    def test_delay_causes_breakdown_present(self):
        r = predict_eta(ETAInput(
            route_distance_nm=1000, speed_kn=10, weather_risk=0.4,
            destination_congestion=50, expected_port_waiting_days=1,
            departure_time=DEP,
        ))
        causes = {c.cause: c.delay_hours for c in r.delay_causes}
        self.assertEqual(set(causes), {"weather", "destination_congestion", "port_waiting"})
        # All three contribute positive delay here.
        self.assertTrue(all(v > 0 for v in causes.values()))
        # Sum of cause hours == total delay hours.
        self.assertAlmostEqual(sum(causes.values()), r.total_delay_hours, places=1)


class PercentileTests(SimpleTestCase):
    def test_percentiles_are_ordered(self):
        r = predict_eta(ETAInput(
            route_distance_nm=2000, speed_kn=12, weather_risk=0.3,
            destination_congestion=40, expected_port_waiting_days=2,
            departure_time=DEP,
        ))
        self.assertLessEqual(r.eta_p50, r.eta_p80)
        self.assertLessEqual(r.eta_p80, r.eta_p95)

    def test_more_delay_widens_interval(self):
        clean = predict_eta(ETAInput(route_distance_nm=2000, speed_kn=12, departure_time=DEP))
        delayed = predict_eta(ETAInput(
            route_distance_nm=2000, speed_kn=12, weather_risk=0.6,
            destination_congestion=70, expected_port_waiting_days=4,
            departure_time=DEP,
        ))
        # P95 - P50 spread (uncertainty) should be larger when there is more delay.
        clean_spread = _iso_to_dt(clean.eta_p95) - _iso_to_dt(clean.eta_p50)
        delayed_spread = _iso_to_dt(delayed.eta_p95) - _iso_to_dt(delayed.eta_p50)
        self.assertGreater(delayed_spread, clean_spread)


class ValidationTests(SimpleTestCase):
    def test_zero_speed_rejected(self):
        with self.assertRaises(ETAValidationError):
            predict_eta(ETAInput(route_distance_nm=1000, speed_kn=0))

    def test_negative_distance_rejected(self):
        with self.assertRaises(ETAValidationError):
            predict_eta(ETAInput(route_distance_nm=-5, speed_kn=10))

    def test_absurd_speed_rejected(self):
        with self.assertRaises(ETAValidationError):
            predict_eta(ETAInput(route_distance_nm=1000, speed_kn=100))

    def test_negative_waiting_rejected(self):
        with self.assertRaises(ETAValidationError):
            predict_eta(ETAInput(route_distance_nm=1000, speed_kn=10,
                                 expected_port_waiting_days=-1))

    def test_out_of_range_weather_rejected(self):
        with self.assertRaises(ETAValidationError):
            predict_eta(ETAInput(route_distance_nm=1000, speed_kn=10, weather_risk=2.0))

    def test_out_of_range_congestion_rejected(self):
        with self.assertRaises(ETAValidationError):
            predict_eta(ETAInput(route_distance_nm=1000, speed_kn=10,
                                 destination_congestion=150))

    def test_bad_coordinates_rejected(self):
        with self.assertRaises(ETAValidationError):
            predict_eta(ETAInput(route_distance_nm=1000, speed_kn=10, latitude=999))

    def test_impossible_total_eta_rejected(self):
        # Slow speed + huge (but in-bounds) distance -> ETA beyond the cap.
        # 14000 nm at 0.2 kn = 70000 h ~ 2916 days > 120-day cap.
        with self.assertRaises(ETAValidationError):
            predict_eta(ETAInput(route_distance_nm=14000, speed_kn=0.2))


class DeterminismTests(SimpleTestCase):
    def test_deterministic(self):
        inp = ETAInput(route_distance_nm=3000, speed_kn=13, weather_risk=0.2,
                       destination_congestion=30, expected_port_waiting_days=1,
                       departure_time=DEP)
        a = predict_eta(inp).to_dict()
        b = predict_eta(inp).to_dict()
        self.assertEqual(a, b)

    def test_result_is_json_serializable_shape(self):
        import json
        r = predict_eta(ETAInput(route_distance_nm=1000, speed_kn=10, departure_time=DEP))
        # to_dict must be JSON-serializable (no raw datetimes).
        json.dumps(r.to_dict())
        d = r.to_dict()
        for field in ("eta", "eta_p50", "eta_p80", "eta_p95",
                      "total_hours", "delay_causes", "inputs"):
            self.assertIn(field, d)

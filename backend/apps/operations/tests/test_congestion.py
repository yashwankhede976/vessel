"""Unit tests for the deterministic port congestion score."""
from django.test import SimpleTestCase

from apps.operations.services.congestion import (
    Classification,
    CongestionInput,
    THRESHOLD_HIGH,
    THRESHOLD_MEDIUM,
    THRESHOLD_SEVERE,
    classify,
    score_congestion,
)


class ScoreRangeTests(SimpleTestCase):
    def test_all_zero_inputs_score_zero_low(self):
        r = score_congestion(CongestionInput(
            vessels_near_port=0, vessels_waiting=0, historical_traffic=0,
            expected_arrivals=0, throughput_utilization=0.0,
            weather_warning="none", recent_waiting_time_days=0,
        ))
        self.assertEqual(r.congestion_score, 0.0)
        self.assertEqual(r.classification, Classification.LOW.value)

    def test_all_maxed_inputs_score_100_severe(self):
        r = score_congestion(CongestionInput(
            vessels_near_port=30, vessels_waiting=15, historical_traffic=40,
            expected_arrivals=20, throughput_utilization=1.0,
            weather_warning="severe", recent_waiting_time_days=7,
        ))
        self.assertEqual(r.congestion_score, 100.0)
        self.assertEqual(r.classification, Classification.SEVERE.value)

    def test_score_bounded_0_100(self):
        # Over-reference inputs saturate, not exceed.
        r = score_congestion(CongestionInput(
            vessels_waiting=999, recent_waiting_time_days=999,
            vessels_near_port=999, expected_arrivals=999,
            throughput_utilization=5.0, weather_warning="severe",
            historical_traffic=999,
        ))
        self.assertLessEqual(r.congestion_score, 100.0)
        self.assertGreaterEqual(r.congestion_score, 0.0)
        self.assertEqual(r.congestion_score, 100.0)


class ClassificationThresholdTests(SimpleTestCase):
    def test_classify_boundaries(self):
        self.assertEqual(classify(0), Classification.LOW)
        self.assertEqual(classify(THRESHOLD_MEDIUM - 0.01), Classification.LOW)
        self.assertEqual(classify(THRESHOLD_MEDIUM), Classification.MEDIUM)
        self.assertEqual(classify(THRESHOLD_HIGH - 0.01), Classification.MEDIUM)
        self.assertEqual(classify(THRESHOLD_HIGH), Classification.HIGH)
        self.assertEqual(classify(THRESHOLD_SEVERE - 0.01), Classification.HIGH)
        self.assertEqual(classify(THRESHOLD_SEVERE), Classification.SEVERE)
        self.assertEqual(classify(100), Classification.SEVERE)


class MonotonicityTests(SimpleTestCase):
    def _base(self, **over):
        data = dict(
            vessels_near_port=5, vessels_waiting=3, historical_traffic=10,
            expected_arrivals=4, throughput_utilization=0.3,
            weather_warning="none", recent_waiting_time_days=1,
        )
        data.update(over)
        return score_congestion(CongestionInput(**data)).congestion_score

    def test_more_waiting_increases_score(self):
        self.assertGreater(self._base(vessels_waiting=12), self._base(vessels_waiting=3))

    def test_longer_wait_increases_score(self):
        self.assertGreater(self._base(recent_waiting_time_days=6),
                           self._base(recent_waiting_time_days=1))

    def test_worse_weather_increases_score(self):
        self.assertGreater(self._base(weather_warning="severe"),
                           self._base(weather_warning="none"))

    def test_higher_throughput_utilization_increases_score(self):
        self.assertGreater(self._base(throughput_utilization=0.95),
                           self._base(throughput_utilization=0.1))


class MissingInputTests(SimpleTestCase):
    def test_missing_inputs_excluded_and_reported(self):
        # Only vessels_waiting provided; others missing.
        r = score_congestion(CongestionInput(vessels_waiting=15))
        # With only one available factor, its renormalized weight is 1.0, and
        # a maxed value => score 100.
        self.assertEqual(r.congestion_score, 100.0)
        available = [f for f in r.factors if f.available]
        self.assertEqual(len(available), 1)
        self.assertEqual(available[0].factor, "vessels_waiting")
        self.assertEqual(len(r.missing_factors), 6)

    def test_missing_inputs_do_not_deflate_score(self):
        # Same waiting level, but with vs without other (zero) factors present.
        only_waiting = score_congestion(CongestionInput(vessels_waiting=8)).congestion_score
        # Providing extra factors at zero pressure should LOWER the score
        # (they dilute), confirming missing != zero.
        with_zeros = score_congestion(CongestionInput(
            vessels_waiting=8, weather_warning="none", expected_arrivals=0,
        )).congestion_score
        self.assertGreater(only_waiting, with_zeros)

    def test_no_inputs_scores_zero(self):
        r = score_congestion(CongestionInput())
        self.assertEqual(r.congestion_score, 0.0)
        self.assertEqual(len(r.missing_factors), 7)


class ExplainabilityTests(SimpleTestCase):
    def test_breakdown_and_inputs_stored(self):
        inp = CongestionInput(
            vessels_waiting=10, recent_waiting_time_days=3.5,
            weather_warning="high",
        )
        r = score_congestion(inp)
        d = r.to_dict()
        # Inputs preserved for audit.
        self.assertEqual(d["inputs"]["vessels_waiting"], 10)
        self.assertEqual(d["inputs"]["weather_warning"], "high")
        # Per-factor breakdown present with contributions summing ~ to score.
        contribs = sum(f["contribution"] for f in d["factors"] if f["available"])
        self.assertAlmostEqual(contribs, d["congestion_score"], places=1)
        # Each available factor exposes raw_value, normalized, weight.
        for f in d["factors"]:
            if f["available"]:
                self.assertIn("normalized", f)
                self.assertIn("weight", f)
                self.assertIsNotNone(f["raw_value"])

    def test_deterministic(self):
        inp = CongestionInput(vessels_waiting=7, recent_waiting_time_days=2,
                              weather_warning="moderate", expected_arrivals=5)
        a = score_congestion(inp).congestion_score
        b = score_congestion(inp).congestion_score
        self.assertEqual(a, b)

    def test_unknown_weather_string_treated_as_missing(self):
        # An unrecognized weather label maps to None pressure -> excluded.
        r = score_congestion(CongestionInput(vessels_waiting=5, weather_warning="foo"))
        weather = next(f for f in r.factors if f.factor == "weather_warning")
        self.assertFalse(weather.available)

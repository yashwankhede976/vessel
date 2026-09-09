"""Unit tests for the deterministic vessel suitability score."""
import json

from django.test import SimpleTestCase

from apps.decisions.services.vessel_suitability import (
    SuitabilityInput,
    score_vessel_suitability,
)


def _strong(**over):
    data = dict(
        port_compatible=True,
        vessel_draft=14, max_draft=16,
        vessel_loa=225, max_loa=290,
        vessel_beam=32, max_beam=45,
        vessel_dwt=82000, required_tonnes=75000,
        estimated_freight_per_tonne=15, market_freight_low=14, market_freight_high=20,
        eta_reliability=0.9, congestion_score=20, weather_risk=0.1,
        expected_demurrage_cost=20000, fuel_efficiency=0.8,
    )
    data.update(over)
    return score_vessel_suitability(SuitabilityInput(**data))


class ScoreRangeTests(SimpleTestCase):
    def test_strong_vessel_scores_high(self):
        self.assertGreater(_strong().score, 85)

    def test_score_bounded_0_100(self):
        r = _strong()
        self.assertGreaterEqual(r.score, 0.0)
        self.assertLessEqual(r.score, 100.0)

    def test_empty_input_scores_zero_all_missing(self):
        r = score_vessel_suitability(SuitabilityInput())
        self.assertEqual(r.score, 0.0)
        self.assertEqual(len(r.missing_factors), len(r.factors))


class HardConstraintTests(SimpleTestCase):
    def test_incompatible_port_penalizes(self):
        self.assertLess(_strong(port_compatible=False).score, _strong().score)

    def test_over_draft_zeroes_draft_factor(self):
        r = _strong(vessel_draft=18, max_draft=16)
        draft = next(f for f in r.factors if f.factor == "draft_suitability")
        self.assertEqual(draft.normalized, 0.0)
        self.assertLess(r.score, _strong().score)

    def test_over_loa_zeroes_loa_factor(self):
        r = _strong(vessel_loa=300, max_loa=290)
        loa = next(f for f in r.factors if f.factor == "loa_suitability")
        self.assertEqual(loa.normalized, 0.0)

    def test_over_beam_zeroes_beam_factor(self):
        r = _strong(vessel_beam=50, max_beam=45)
        beam = next(f for f in r.factors if f.factor == "beam_suitability")
        self.assertEqual(beam.normalized, 0.0)

    def test_insufficient_dwt_zeroes_capacity(self):
        r = _strong(vessel_dwt=50000, required_tonnes=75000)
        cap = next(f for f in r.factors if f.factor == "cargo_capacity")
        self.assertEqual(cap.normalized, 0.0)


class GradedFactorTests(SimpleTestCase):
    def test_cheaper_freight_scores_better(self):
        cheap = _strong(estimated_freight_per_tonne=14).score
        pricey = _strong(estimated_freight_per_tonne=20).score
        self.assertGreater(cheap, pricey)

    def test_higher_congestion_lowers_score(self):
        self.assertLess(_strong(congestion_score=90).score,
                        _strong(congestion_score=10).score)

    def test_worse_weather_lowers_score(self):
        self.assertLess(_strong(weather_risk=0.9).score,
                        _strong(weather_risk=0.0).score)

    def test_higher_demurrage_lowers_score(self):
        self.assertLess(_strong(expected_demurrage_cost=400000).score,
                        _strong(expected_demurrage_cost=0).score)

    def test_higher_eta_reliability_raises_score(self):
        self.assertGreater(_strong(eta_reliability=1.0).score,
                           _strong(eta_reliability=0.2).score)

    def test_better_fuel_efficiency_raises_score(self):
        self.assertGreater(_strong(fuel_efficiency=1.0).score,
                           _strong(fuel_efficiency=0.1).score)


class MissingDataTests(SimpleTestCase):
    def test_missing_factors_excluded_not_zero(self):
        # Provide only reliability at 1.0; single available factor -> 100.
        r = score_vessel_suitability(SuitabilityInput(eta_reliability=1.0))
        available = [f for f in r.factors if f.available]
        self.assertEqual(len(available), 1)
        self.assertEqual(r.score, 100.0)

    def test_missing_is_not_the_same_as_zero(self):
        # A vessel with reliability 1.0 and nothing else vs one with reliability
        # 1.0 plus a zero-scoring factor present: the latter should be lower.
        only = score_vessel_suitability(SuitabilityInput(eta_reliability=1.0)).score
        with_zero = score_vessel_suitability(
            SuitabilityInput(eta_reliability=1.0, weather_risk=1.0)  # weather -> 0
        ).score
        self.assertGreater(only, with_zero)

    def test_partial_inputs_still_scores(self):
        r = score_vessel_suitability(SuitabilityInput(
            port_compatible=True, vessel_draft=14, max_draft=16,
        ))
        self.assertGreater(r.score, 0.0)
        self.assertTrue(len(r.missing_factors) > 0)


class ExplainabilityTests(SimpleTestCase):
    def test_breakdown_sums_to_score(self):
        r = _strong()
        contribs = sum(f.contribution for f in r.factors if f.available)
        self.assertAlmostEqual(contribs, r.score, places=1)

    def test_breakdown_fields_present(self):
        r = _strong()
        for f in r.factors:
            if f.available:
                self.assertIsNotNone(f.normalized)
                self.assertGreaterEqual(f.weight, 0.0)
                self.assertTrue(f.note)

    def test_available_weights_sum_to_one(self):
        r = _strong()  # all factors available
        # Weights are stored rounded to 4dp, so the reported sum is ~1.0 (a
        # hair under due to rounding); check to 2 places.
        total_w = sum(f.weight for f in r.factors if f.available)
        self.assertAlmostEqual(total_w, 1.0, places=2)

    def test_to_dict_json_serializable(self):
        json.dumps(_strong().to_dict())

    def test_deterministic(self):
        self.assertEqual(_strong().to_dict(), _strong().to_dict())

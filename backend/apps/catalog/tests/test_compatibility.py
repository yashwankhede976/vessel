"""Unit tests for the deterministic compatibility engine.

Focus on boundary cases: exact limits, marginal over/under, tidal-conditional
draft, unknown data, cargo mismatch, and full incompatibility.
"""
from decimal import Decimal

from django.test import SimpleTestCase

from apps.catalog.services.compatibility import (
    CompatibilityInput,
    Status,
    CheckOutcome,
    evaluate,
)


def base_input(**overrides) -> CompatibilityInput:
    """A fully-known, comfortably-compatible baseline; override per test."""
    data = dict(
        vessel_loa=Decimal("200"),
        vessel_beam=Decimal("32"),
        vessel_draft=Decimal("12"),
        vessel_dwt=Decimal("75000"),
        vessel_cargo="Thermal Coal",
        max_loa=Decimal("230"),
        max_beam=Decimal("40"),
        max_draft=Decimal("14.5"),
        max_dwt=Decimal("120000"),
        supported_commodities={"Thermal Coal", "Iron Ore"},
    )
    data.update(overrides)
    return CompatibilityInput(**data)


class CompatibleCases(SimpleTestCase):
    def test_all_within_limits_is_compatible(self):
        result = evaluate(base_input())
        self.assertEqual(result.status, Status.COMPATIBLE)
        self.assertEqual(result.score, 100)
        self.assertEqual(result.reasons, [])


class BoundaryDimensionCases(SimpleTestCase):
    def test_draft_exactly_at_limit_passes(self):
        result = evaluate(base_input(vessel_draft=Decimal("14.5"), max_draft=Decimal("14.5")))
        self.assertEqual(result.status, Status.COMPATIBLE)

    def test_draft_just_over_limit_fails(self):
        result = evaluate(base_input(vessel_draft=Decimal("14.51"), max_draft=Decimal("14.5")))
        self.assertEqual(result.status, Status.INCOMPATIBLE)
        self.assertEqual(result.score, 0)
        self.assertTrue(any("Draft" in r for r in result.reasons))

    def test_loa_exactly_at_limit_passes(self):
        result = evaluate(base_input(vessel_loa=Decimal("230"), max_loa=Decimal("230")))
        self.assertEqual(result.status, Status.COMPATIBLE)

    def test_loa_over_limit_is_incompatible(self):
        result = evaluate(base_input(vessel_loa=Decimal("240"), max_loa=Decimal("230")))
        self.assertEqual(result.status, Status.INCOMPATIBLE)

    def test_beam_over_limit_is_incompatible(self):
        result = evaluate(base_input(vessel_beam=Decimal("45"), max_beam=Decimal("40")))
        self.assertEqual(result.status, Status.INCOMPATIBLE)


class TidalConditionalCases(SimpleTestCase):
    def test_draft_over_normal_but_within_tide_is_conditional(self):
        result = evaluate(
            base_input(
                vessel_draft=Decimal("15.0"),
                max_draft=Decimal("14.5"),
                tidal_draft_allowance=Decimal("1.0"),
            )
        )
        self.assertEqual(result.status, Status.CONDITIONAL)
        self.assertLess(result.score, 100)
        self.assertTrue(any("tide" in r.lower() for r in result.reasons))

    def test_draft_over_even_with_tide_is_incompatible(self):
        result = evaluate(
            base_input(
                vessel_draft=Decimal("16.0"),
                max_draft=Decimal("14.5"),
                tidal_draft_allowance=Decimal("1.0"),
            )
        )
        self.assertEqual(result.status, Status.INCOMPATIBLE)

    def test_draft_exactly_at_tidal_edge_is_conditional(self):
        # 14.5 + 1.0 = 15.5 exactly -> within allowance (conditional), not fail.
        result = evaluate(
            base_input(
                vessel_draft=Decimal("15.5"),
                max_draft=Decimal("14.5"),
                tidal_draft_allowance=Decimal("1.0"),
            )
        )
        self.assertEqual(result.status, Status.CONDITIONAL)


class CargoCases(SimpleTestCase):
    def test_cargo_not_supported_is_incompatible(self):
        result = evaluate(base_input(vessel_cargo="Crude Oil"))
        self.assertEqual(result.status, Status.INCOMPATIBLE)
        self.assertTrue(any("Crude Oil" in r for r in result.reasons))

    def test_cargo_case_insensitive_match(self):
        result = evaluate(base_input(vessel_cargo="thermal coal"))
        self.assertEqual(result.status, Status.COMPATIBLE)

    def test_unknown_supported_commodities_is_not_a_fail(self):
        result = evaluate(base_input(supported_commodities=None))
        # Cargo can't be confirmed, but nothing fails -> still compatible via
        # other passes, with a reduced score for the unknown.
        self.assertEqual(result.status, Status.COMPATIBLE)
        self.assertLess(result.score, 100)


class UnknownDataCases(SimpleTestCase):
    def test_all_limits_unknown_yields_unknown(self):
        result = evaluate(
            CompatibilityInput(
                vessel_loa=Decimal("200"),
                vessel_beam=Decimal("32"),
                vessel_draft=Decimal("12"),
                vessel_dwt=Decimal("75000"),
                vessel_cargo="Thermal Coal",
                # No limits, no supported commodities -> everything UNKNOWN.
            )
        )
        self.assertEqual(result.status, Status.UNKNOWN)
        self.assertTrue(result.reasons)

    def test_partial_unknown_reduces_score_but_stays_compatible(self):
        result = evaluate(base_input(max_dwt=None))  # DWT limit unknown
        self.assertEqual(result.status, Status.COMPATIBLE)
        self.assertLess(result.score, 100)

    def test_unknown_draft_limit_does_not_fail(self):
        result = evaluate(base_input(max_draft=None))
        self.assertEqual(result.status, Status.COMPATIBLE)
        self.assertTrue(any("Draft" in r for r in result.reasons))


class RestrictionCases(SimpleTestCase):
    def test_documented_restriction_makes_conditional(self):
        result = evaluate(
            base_input(operational_restrictions=[(True, "Daytime berthing only.")])
        )
        self.assertEqual(result.status, Status.CONDITIONAL)
        self.assertIn("Daytime berthing only.", result.reasons)

    def test_restriction_not_applying_is_ignored(self):
        result = evaluate(
            base_input(operational_restrictions=[(False, "Some rule that doesn't apply.")])
        )
        self.assertEqual(result.status, Status.COMPATIBLE)

    def test_fail_dominates_conditional(self):
        # A hard fail plus a conditional restriction -> INCOMPATIBLE overall.
        result = evaluate(
            base_input(
                vessel_loa=Decimal("300"),
                max_loa=Decimal("230"),
                operational_restrictions=[(True, "Daytime berthing only.")],
            )
        )
        self.assertEqual(result.status, Status.INCOMPATIBLE)


class OutcomeShapeCases(SimpleTestCase):
    def test_to_dict_shape_matches_contract(self):
        result = evaluate(
            base_input(
                vessel_draft=Decimal("15.0"),
                max_draft=Decimal("14.5"),
                tidal_draft_allowance=Decimal("1.0"),
            )
        )
        d = result.to_dict()
        self.assertIn(d["status"], {s.value for s in Status})
        self.assertIsInstance(d["score"], int)
        self.assertIsInstance(d["reasons"], list)
        self.assertTrue(all("outcome" in c for c in d["checks"]))

    def test_conditional_only_never_exceeds_100_or_below_1(self):
        result = evaluate(base_input(operational_restrictions=[(True, "x")]))
        self.assertGreaterEqual(result.score, 1)
        self.assertLessEqual(result.score, 100)

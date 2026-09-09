"""Unit tests for the voyage economics engine."""
import json
from decimal import Decimal

from django.test import SimpleTestCase

from apps.decisions.services.voyage_economics import (
    NM_TO_KM,
    VoyageEconomicsError,
    VoyageEconomicsInput,
    compute_voyage_economics,
)


def _base(**over):
    data = dict(
        distance_nm=5200, speed_kn=13, cargo_tonnes=150000,
        bunker_rate_tpd=55, bunker_price_per_tonne=600, port_days=4,
        port_cost=120000, freight_cost=900000,
        demurrage_rate_per_day=25000, expected_demurrage_days=3,
        misc_cost=40000,
    )
    data.update(over)
    return compute_voyage_economics(VoyageEconomicsInput(**data))


class PhysicalTests(SimpleTestCase):
    def test_sailing_duration_is_distance_over_speed(self):
        r = _base()
        # 5200 / 13 = 400 h = 16.666.. days
        self.assertEqual(r.sailing_days, Decimal("16.67"))
        self.assertEqual(r.total_days, Decimal("20.67"))  # + 4 port days

    def test_distance_km_conversion(self):
        r = _base()
        self.assertEqual(r.distance_km, (Decimal("5200") * NM_TO_KM).quantize(Decimal("0.01")))

    def test_bunker_consumption(self):
        r = _base()
        # 55 t/day * 16.67 sailing days (idle rate 0) = 916.85 t
        self.assertEqual(r.bunker_consumption_tonnes, Decimal("916.8500"))


class CostMathTests(SimpleTestCase):
    def test_bunker_cost(self):
        r = _base()
        self.assertEqual(r.cost_components["bunker_cost"].amount, Decimal("550110.00"))

    def test_estimated_demurrage_from_rate_and_days(self):
        r = _base()
        self.assertEqual(r.cost_components["estimated_demurrage"].amount, Decimal("75000.00"))

    def test_total_is_sum_of_components(self):
        r = _base()
        s = sum(c.amount for c in r.cost_components.values())
        self.assertEqual(r.total_voyage_cost.amount, s)
        self.assertEqual(r.total_voyage_cost.amount, Decimal("1685110.00"))

    def test_freight_from_rate_when_cost_absent(self):
        r = _base(freight_cost=None, freight_rate_per_tonne=6)
        # 6 * 150000 = 900000
        self.assertEqual(r.cost_components["freight_cost"].amount, Decimal("900000.00"))

    def test_explicit_estimated_demurrage_overrides_rate(self):
        r = _base(estimated_demurrage=10000, demurrage_rate_per_day=25000,
                  expected_demurrage_days=3)
        self.assertEqual(r.cost_components["estimated_demurrage"].amount, Decimal("10000.00"))

    def test_idle_bunker_consumption_added(self):
        r = _base(bunker_idle_rate_tpd=5)
        # sailing 55*16.67 + idle 5*4 = 916.85 + 20 = 936.85
        self.assertEqual(r.bunker_consumption_tonnes, Decimal("936.8500"))


class PerUnitTests(SimpleTestCase):
    def test_cost_per_tonne(self):
        r = _base()
        self.assertEqual(r.cost_per_tonne.amount, Decimal("11.23"))
        self.assertEqual(r.cost_per_tonne.unit, "per_tonne")

    def test_cost_per_day(self):
        r = _base()
        expected = (Decimal("1685110.00") / Decimal("20.67")).quantize(Decimal("0.01"))
        self.assertEqual(r.cost_per_day.amount, expected)
        self.assertEqual(r.cost_per_day.unit, "per_day")

    def test_cost_per_tonne_km_labelled(self):
        r = _base()
        self.assertEqual(r.cost_per_tonne_km.unit, "per_tonne_km")
        self.assertGreater(r.cost_per_tonne_km.amount, Decimal("0"))

    def test_zero_cargo_yields_no_per_tonne(self):
        r = _base(cargo_tonnes=0, freight_rate_per_tonne=None)
        self.assertIsNone(r.cost_per_tonne)
        self.assertIsNone(r.cost_per_tonne_km)
        # per_day still defined.
        self.assertIsNotNone(r.cost_per_day)


class CurrencyUnitTests(SimpleTestCase):
    def test_every_money_value_has_currency_and_unit(self):
        r = _base(currency="USD")
        d = r.to_dict()
        for comp in d["cost_components"].values():
            self.assertEqual(comp["currency"], "USD")
            self.assertIn("unit", comp)
        self.assertEqual(d["total_voyage_cost"]["currency"], "USD")
        self.assertEqual(d["total_voyage_cost"]["unit"], "total")
        for k in ("cost_per_tonne", "cost_per_day", "cost_per_tonne_km"):
            self.assertEqual(d[k]["currency"], "USD")

    def test_currency_is_respected(self):
        r = _base(currency="INR")
        self.assertEqual(r.total_voyage_cost.currency, "INR")
        self.assertEqual(r.cost_per_tonne.currency, "INR")

    def test_to_dict_is_json_serializable(self):
        json.dumps(_base().to_dict())  # must not raise (Decimals -> str)


class MissingComponentTests(SimpleTestCase):
    def test_optional_components_default_zero(self):
        # Only the mandatory physical + bunker inputs; costs omitted.
        r = compute_voyage_economics(VoyageEconomicsInput(
            distance_nm=1000, speed_kn=10, cargo_tonnes=50000,
            bunker_rate_tpd=40, bunker_price_per_tonne=500,
        ))
        self.assertEqual(r.cost_components["port_cost"].amount, Decimal("0.00"))
        self.assertEqual(r.cost_components["freight_cost"].amount, Decimal("0.00"))
        self.assertEqual(r.cost_components["canal_cost"].amount, Decimal("0.00"))
        self.assertEqual(r.cost_components["estimated_demurrage"].amount, Decimal("0.00"))
        # Total = bunker only: 40 * (1000/10/24=4.17) days * 500
        self.assertEqual(r.total_voyage_cost.amount, r.cost_components["bunker_cost"].amount)


class ValidationTests(SimpleTestCase):
    def test_zero_speed_rejected(self):
        with self.assertRaises(VoyageEconomicsError):
            compute_voyage_economics(VoyageEconomicsInput(
                distance_nm=1000, speed_kn=0, cargo_tonnes=1000))

    def test_negative_distance_rejected(self):
        with self.assertRaises(VoyageEconomicsError):
            compute_voyage_economics(VoyageEconomicsInput(
                distance_nm=-1, speed_kn=10, cargo_tonnes=1000))

    def test_negative_cost_rejected(self):
        with self.assertRaises(VoyageEconomicsError):
            compute_voyage_economics(VoyageEconomicsInput(
                distance_nm=1000, speed_kn=10, cargo_tonnes=1000, port_cost=-5))


class DeterminismTests(SimpleTestCase):
    def test_deterministic(self):
        a = _base().to_dict()
        b = _base().to_dict()
        self.assertEqual(a, b)

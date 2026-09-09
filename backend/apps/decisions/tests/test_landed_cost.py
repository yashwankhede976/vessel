"""Unit tests for the deterministic total landed-cost engine."""
from decimal import Decimal

import pytest

from apps.decisions.services.landed_cost import (
    CostComponent,
    LandedCostError,
    LandedCostInput,
    Money,
    PROJECT_ORIGINS,
    compare_origins,
    compute_landed_cost,
)


def _usd(amount) -> CostComponent:
    return CostComponent(amount=amount, currency="USD")


def _full_input(**overrides) -> LandedCostInput:
    """A fully-specified USD input; overrides replace individual fields."""
    base = dict(
        origin="Australia",
        destination="Paradip",
        cargo_tonnes=Decimal("50000"),
        commodity_cost=_usd("5000000"),
        freight_cost=_usd("1200000"),
        bunker_cost=_usd("400000"),
        port_charges=_usd("150000"),
        handling_cost=_usd("100000"),
        demurrage_cost=_usd("50000"),
        insurance_other_cost=_usd("30000"),
        target_currency="USD",
        fx_rates={},
    )
    base.update(overrides)
    return LandedCostInput(**base)


# ---------------------------------------------------------------------------
# Component sum + per-tonne
# ---------------------------------------------------------------------------
def test_total_is_sum_of_components():
    res = compute_landed_cost(_full_input())
    expected = Decimal("5000000") + Decimal("1200000") + Decimal("400000") \
        + Decimal("150000") + Decimal("100000") + Decimal("50000") + Decimal("30000")
    assert res.total_landed_cost.amount == expected  # 6,930,000


def test_per_tonne_is_total_over_cargo():
    res = compute_landed_cost(_full_input())
    assert res.landed_cost_per_tonne.amount == (res.total_landed_cost.amount
                                                 / Decimal("50000")).quantize(Decimal("0.01"))
    # 6,930,000 / 50,000 = 138.60
    assert res.landed_cost_per_tonne.amount == Decimal("138.60")


def test_components_breakdown_present_and_ordered():
    res = compute_landed_cost(_full_input())
    assert list(res.components.keys()) == [
        "commodity_cost", "freight_cost", "bunker_cost", "port_charges",
        "handling_cost", "demurrage_cost", "insurance_other_cost",
    ]
    assert res.components["commodity_cost"].amount == Decimal("5000000.00")


# ---------------------------------------------------------------------------
# FX conversion
# ---------------------------------------------------------------------------
def test_fx_conversion_applies_rate():
    # commodity is 1,000,000 AUD; rate AUD->USD = 0.65 -> 650,000 USD
    inp = _full_input(
        commodity_cost=CostComponent("1000000", "AUD"),
        freight_cost=None, bunker_cost=None, port_charges=None,
        handling_cost=None, demurrage_cost=None, insurance_other_cost=None,
        fx_rates={"AUD": "0.65"},
    )
    res = compute_landed_cost(inp)
    assert res.components["commodity_cost"].amount == Decimal("650000.00")
    assert res.total_landed_cost.amount == Decimal("650000.00")
    assert res.fx_rates_used == {"AUD": Decimal("0.65")}


def test_same_currency_rate_is_one_and_not_recorded():
    res = compute_landed_cost(_full_input())
    assert res.fx_rates_used == {}


def test_missing_fx_rate_raises():
    inp = _full_input(commodity_cost=CostComponent("1000000", "AUD"), fx_rates={})
    with pytest.raises(LandedCostError):
        compute_landed_cost(inp)


def test_mixed_currency_conversion_sums_correctly():
    inp = LandedCostInput(
        origin="Russia", destination="Paradip", cargo_tonnes=Decimal("10000"),
        commodity_cost=CostComponent("2000000", "RUB"),   # * 0.011 = 22,000
        freight_cost=CostComponent("500000", "USD"),      # 500,000
        target_currency="USD",
        fx_rates={"RUB": "0.011"},
    )
    res = compute_landed_cost(inp)
    assert res.components["commodity_cost"].amount == Decimal("22000.00")
    assert res.total_landed_cost.amount == Decimal("522000.00")


# ---------------------------------------------------------------------------
# Currency + unit on every value
# ---------------------------------------------------------------------------
def test_currency_and_units_present_everywhere():
    res = compute_landed_cost(_full_input())
    assert res.total_landed_cost.currency == "USD"
    assert res.total_landed_cost.unit == "total"
    assert res.landed_cost_per_tonne.currency == "USD"
    assert res.landed_cost_per_tonne.unit == "per_tonne"
    for comp in res.components.values():
        assert isinstance(comp, Money)
        assert comp.currency == "USD"
        assert comp.unit == "total"


def test_to_dict_is_json_serializable():
    import json
    res = compute_landed_cost(_full_input())
    d = res.to_dict()
    json.dumps(d)  # must not raise
    assert d["total_landed_cost"]["currency"] == "USD"
    assert d["total_landed_cost"]["unit"] == "total"
    assert d["landed_cost_per_tonne"]["unit"] == "per_tonne"


# ---------------------------------------------------------------------------
# Missing components
# ---------------------------------------------------------------------------
def test_missing_components_contribute_zero_and_are_listed():
    inp = _full_input(
        demurrage_cost=None, insurance_other_cost=None,
    )
    res = compute_landed_cost(inp)
    assert "demurrage_cost" in res.missing_components
    assert "insurance_other_cost" in res.missing_components
    assert res.components["demurrage_cost"].amount == Decimal("0.00")
    # total excludes the missing components
    expected = Decimal("5000000") + Decimal("1200000") + Decimal("400000") \
        + Decimal("150000") + Decimal("100000")
    assert res.total_landed_cost.amount == expected


def test_component_with_none_amount_is_missing():
    inp = _full_input(bunker_cost=CostComponent(None, "USD"))
    res = compute_landed_cost(inp)
    assert "bunker_cost" in res.missing_components


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------
def test_zero_cargo_raises():
    with pytest.raises(LandedCostError):
        compute_landed_cost(_full_input(cargo_tonnes=Decimal("0")))


def test_negative_cargo_raises():
    with pytest.raises(LandedCostError):
        compute_landed_cost(_full_input(cargo_tonnes=Decimal("-1")))


def test_negative_component_raises():
    with pytest.raises(LandedCostError):
        compute_landed_cost(_full_input(freight_cost=_usd("-100")))


# ---------------------------------------------------------------------------
# compare_origins: 5-origin ordering + deltas
# ---------------------------------------------------------------------------
def _origin_input(origin, commodity, freight):
    return LandedCostInput(
        origin=origin, destination="Paradip", cargo_tonnes=Decimal("50000"),
        commodity_cost=_usd(commodity), freight_cost=_usd(freight),
        target_currency="USD",
    )


def test_compare_origins_sorted_cheapest_first_with_deltas():
    inputs = [
        _origin_input("Australia", "5000000", "1200000"),   # 6,200,000
        _origin_input("Indonesia", "4800000", "900000"),    # 5,700,000  <- cheapest
        _origin_input("Mozambique", "5100000", "1400000"),  # 6,500,000
        _origin_input("USA", "5300000", "1800000"),         # 7,100,000
        _origin_input("Russia", "4900000", "1300000"),      # 6,200,000
    ]
    cmp = compare_origins(inputs)
    origins = [e.origin for e in cmp.entries]
    totals = [e.total_landed_cost.amount for e in cmp.entries]

    assert origins[0] == "Indonesia"
    assert totals == sorted(totals)
    assert cmp.entries[0].is_cheapest is True
    assert cmp.entries[0].delta_vs_cheapest.amount == Decimal("0.00")
    # second-cheapest delta = its total - cheapest total
    assert cmp.entries[1].delta_vs_cheapest.amount == totals[1] - totals[0]
    assert all(e.delta_vs_cheapest.currency == "USD" for e in cmp.entries)
    assert set(origins) == set(PROJECT_ORIGINS)


def test_compare_origins_only_one_is_cheapest():
    inputs = [
        _origin_input("Australia", "5000000", "1200000"),
        _origin_input("Indonesia", "4800000", "900000"),
    ]
    cmp = compare_origins(inputs)
    assert sum(1 for e in cmp.entries if e.is_cheapest) == 1


def test_compare_origins_rejects_mixed_destination():
    a = _origin_input("Australia", "5000000", "1200000")
    b = LandedCostInput(
        origin="Indonesia", destination="Kolkata", cargo_tonnes=Decimal("50000"),
        commodity_cost=_usd("4800000"),
    )
    with pytest.raises(LandedCostError):
        compare_origins([a, b])


def test_compare_origins_rejects_mixed_target_currency():
    a = _origin_input("Australia", "5000000", "1200000")
    b = LandedCostInput(
        origin="Indonesia", destination="Paradip", cargo_tonnes=Decimal("50000"),
        commodity_cost=_usd("4800000"), target_currency="INR",
    )
    with pytest.raises(LandedCostError):
        compare_origins([a, b])


def test_compare_origins_empty_raises():
    with pytest.raises(LandedCostError):
        compare_origins([])


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------
def test_deterministic():
    r1 = compute_landed_cost(_full_input()).to_dict()
    r2 = compute_landed_cost(_full_input()).to_dict()
    assert r1 == r2

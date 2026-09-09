"""Unit tests for the spot-vs-contract comparison engine."""
from decimal import Decimal

import pytest

from apps.decisions.services.spot_vs_contract import (
    STRATEGIES,
    SpotVsContractError,
    SpotVsContractInput,
    compare_strategies,
)


def _inp(**kw):
    base = dict(spot_freight_per_tonne="22", cargo_tonnes="55000",
                freight_volatility=0.5, base_demurrage_cost="40000",
                non_freight_cost="300000", congestion_score=60)
    base.update(kw)
    return SpotVsContractInput(**base)


def test_all_four_strategies_returned():
    r = compare_strategies(_inp())
    assert {o.strategy for o in r.options} == set(STRATEGIES)


def test_committed_strategies_cheaper_freight_than_spot():
    r = compare_strategies(_inp())
    spot = next(o for o in r.options if o.strategy == "SPOT")
    multi = next(o for o in r.options if o.strategy == "MULTI_VOYAGE")
    assert multi.expected_freight_per_tonne < spot.expected_freight_per_tonne


def test_committed_strategies_lower_volatility_exposure():
    r = compare_strategies(_inp())
    spot = next(o for o in r.options if o.strategy == "SPOT")
    multi = next(o for o in r.options if o.strategy == "MULTI_VOYAGE")
    assert multi.volatility_exposure < spot.volatility_exposure


def test_options_sorted_by_risk_adjusted_cost():
    r = compare_strategies(_inp())
    costs = [o.risk_adjusted_cost for o in r.options]
    assert costs == sorted(costs)


def test_savings_non_negative_and_currency_present():
    r = compare_strategies(_inp())
    assert r.expected_savings >= Decimal("0")
    assert r.currency == "USD"
    assert r.reason


def test_zero_cargo_raises():
    with pytest.raises(SpotVsContractError):
        compare_strategies(_inp(cargo_tonnes="0"))


def test_bad_volatility_raises():
    with pytest.raises(SpotVsContractError):
        compare_strategies(_inp(freight_volatility=1.5))


def test_missing_optional_inputs_ok():
    r = compare_strategies(
        SpotVsContractInput(spot_freight_per_tonne="20", cargo_tonnes="10000")
    )
    assert r.recommended_strategy in STRATEGIES

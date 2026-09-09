"""Unit tests for the Freight Market Pressure Index engine."""
import pytest

from apps.decisions.services.market_pressure import (
    BAND_TIGHT,
    MarketPressureInput,
    PressureBand,
    classify,
    compute_market_pressure,
)


def test_all_signals_tight_market():
    r = compute_market_pressure(
        MarketPressureInput(
            vessel_supply=0.2, cargo_demand=0.85, freight_volatility=0.6,
            port_congestion=80, ton_mile_demand=0.8, bunker=0.7, seasonality=0.6,
        )
    )
    assert 0 <= r.index <= 100
    assert r.classification in (PressureBand.TIGHT.value, PressureBand.EXTREMELY_TIGHT.value)
    assert r.missing_factors == []


def test_vessel_supply_is_inverted():
    # Abundant supply (high availability) => LOW pressure from that factor.
    abundant = compute_market_pressure(MarketPressureInput(vessel_supply=1.0))
    scarce = compute_market_pressure(MarketPressureInput(vessel_supply=0.0))
    assert scarce.index > abundant.index


def test_missing_signals_excluded_not_zero():
    # Only one signal provided; index should equal that signal * 100 (its weight
    # renormalizes to 1.0), not be diluted by treating missing as zero.
    r = compute_market_pressure(MarketPressureInput(cargo_demand=0.5))
    assert r.index == pytest.approx(50.0, abs=0.01)
    assert set(r.missing_factors) == {
        "vessel_supply", "freight_volatility", "port_congestion",
        "ton_mile_demand", "bunker", "seasonality",
    }


def test_empty_input_zero_index():
    r = compute_market_pressure(MarketPressureInput())
    assert r.index == 0.0
    assert len(r.missing_factors) == 7


@pytest.mark.parametrize("index,band", [
    (0, "VERY_WEAK"), (24.9, "VERY_WEAK"), (25, "WEAK"), (44.9, "WEAK"),
    (45, "NEUTRAL"), (59.9, "NEUTRAL"), (60, "TIGHT"), (74.9, "TIGHT"),
    (75, "EXTREMELY_TIGHT"), (100, "EXTREMELY_TIGHT"),
])
def test_classification_bands(index, band):
    assert classify(index).value == band


def test_deterministic():
    kw = dict(vessel_supply=0.3, cargo_demand=0.7, port_congestion=55)
    assert (
        compute_market_pressure(MarketPressureInput(**kw)).to_dict()
        == compute_market_pressure(MarketPressureInput(**kw)).to_dict()
    )


def test_to_dict_shape():
    d = compute_market_pressure(MarketPressureInput(cargo_demand=0.5)).to_dict()
    assert set(d) == {"index", "classification", "factors", "inputs", "missing_factors"}
    assert all({"factor", "normalized", "weight", "contribution", "available"} <= set(f)
               for f in d["factors"])

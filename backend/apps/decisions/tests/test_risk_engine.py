"""Unit tests for the unified risk engine."""
import pytest

from apps.decisions.services.risk_engine import (
    RiskInput,
    RiskLevel,
    level_for,
    score_risk,
)


def test_all_signals_scored():
    r = score_risk(
        RiskInput(
            freight_volatility=0.6, port_congestion=70, weather_risk=0.5,
            eta_delay_probability=0.4, expected_demurrage_cost=250000,
            commodity_volatility=0.3, fx_volatility=0.2, geopolitical_risk=0.1,
        )
    )
    assert 0 <= r.overall_score <= 100
    assert r.unknown_factors == []


def test_unknown_factors_stay_unknown_not_zero():
    # Only freight provided; the score must equal that factor's normalized*100
    # (weight renormalized to 1), NOT be dragged down by treating unknowns as 0.
    r = score_risk(RiskInput(freight_volatility=0.8))
    assert r.overall_score == pytest.approx(80.0, abs=0.01)
    assert "weather" in r.unknown_factors
    # Unknown factors are reported with normalized=None and available=False.
    factors = r.to_dict()["factors"]
    weather = next(f for f in factors if f["factor"] == "weather")
    assert weather["available"] is False
    assert weather["normalized"] is None


def test_negative_demurrage_is_unknown_not_used():
    r = score_risk(RiskInput(expected_demurrage_cost=-5))
    assert "demurrage" in r.unknown_factors


def test_no_signals_all_unknown():
    r = score_risk(RiskInput())
    assert r.overall_score == 0.0
    assert len(r.unknown_factors) == 8


@pytest.mark.parametrize("score,level", [
    (0, "LOW"), (32.9, "LOW"), (33, "MEDIUM"), (65.9, "MEDIUM"),
    (66, "HIGH"), (100, "HIGH"),
])
def test_levels(score, level):
    assert level_for(score).value == level


def test_higher_signals_higher_score():
    low = score_risk(RiskInput(freight_volatility=0.1, port_congestion=10))
    high = score_risk(RiskInput(freight_volatility=0.9, port_congestion=90))
    assert high.overall_score > low.overall_score

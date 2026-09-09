"""Unit tests for the multi-horizon congestion forecast."""
from apps.operations.services.congestion import CongestionInput
from apps.operations.services.congestion_forecast import (
    HORIZONS,
    CongestionForecastInput,
    forecast_congestion,
)


def _inp(**kw):
    current = CongestionInput(
        vessels_waiting=kw.pop("vessels_waiting", 10),
        recent_waiting_time_days=kw.pop("recent_waiting_time_days", 4),
    )
    return CongestionForecastInput(current=current, **kw)


def test_produces_all_horizons():
    r = forecast_congestion(_inp(trend_per_day=1.0))
    assert [h.horizon_days for h in r.horizons] == HORIZONS


def test_scores_and_waits_bounded():
    r = forecast_congestion(_inp(trend_per_day=2.0))
    for h in r.horizons:
        assert 0.0 <= h.congestion_score <= 100.0
        assert h.expected_waiting_time_days >= 0.0
        assert h.risk_level in ("LOW", "MEDIUM", "HIGH", "SEVERE")


def test_confidence_decays_with_horizon():
    r = forecast_congestion(_inp(trend_per_day=1.0))
    confs = [h.confidence for h in r.horizons]
    assert confs == sorted(confs, reverse=True)   # non-increasing with horizon


def test_missing_trend_lowers_confidence():
    with_trend = forecast_congestion(_inp(trend_per_day=1.0))
    no_trend = forecast_congestion(_inp(trend_per_day=None))
    # Same horizon, no-trend should be no more confident.
    assert no_trend.horizons[0].confidence <= with_trend.horizons[0].confidence


def test_worsening_trend_raises_near_horizon_score():
    rising = forecast_congestion(_inp(vessels_waiting=8, trend_per_day=3.0))
    flat = forecast_congestion(_inp(vessels_waiting=8, trend_per_day=0.0))
    assert rising.horizons[0].congestion_score >= flat.horizons[0].congestion_score


def test_deterministic():
    a = forecast_congestion(_inp(trend_per_day=1.5)).to_dict()
    b = forecast_congestion(_inp(trend_per_day=1.5)).to_dict()
    assert a == b


def test_missing_signals_reported():
    r = forecast_congestion(
        CongestionForecastInput(current=CongestionInput(vessels_waiting=5))
    )
    assert isinstance(r.missing_signals, list)

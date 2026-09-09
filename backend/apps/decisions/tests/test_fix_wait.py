"""Unit tests for the fix/wait decision engine."""
from decimal import Decimal

import pytest

from apps.decisions.services.fix_wait import (
    DEADLINE_URGENT_DAYS,
    FixWaitError,
    FixWaitInput,
    decide_fix_wait,
)


def test_no_forecast_monitors():
    r = decide_fix_wait(FixWaitInput(current_rate="22"))
    assert r.decision == "MONITOR"
    assert r.expected_move_pct is None


def test_strong_confident_fall_with_time_waits():
    r = decide_fix_wait(FixWaitInput(
        current_rate="22", forecast_7d="20.5", forecast_14d="20", forecast_30d="19.5",
        confidence_7d=0.8, confidence_14d=0.78, confidence_30d=0.72,
        days_to_deadline=40,
    ))
    assert r.decision == "WAIT"
    assert r.expected_move_pct < 0


def test_rising_rates_fix_now():
    r = decide_fix_wait(FixWaitInput(
        current_rate="22", forecast_7d="23.5", confidence_7d=0.7, days_to_deadline=40,
    ))
    assert r.decision == "FIX_NOW"


def test_urgent_deadline_forces_fix_now_even_if_falling():
    r = decide_fix_wait(FixWaitInput(
        current_rate="22", forecast_7d="19", confidence_7d=0.9,
        days_to_deadline=DEADLINE_URGENT_DAYS - 1,
    ))
    assert r.decision == "FIX_NOW"


def test_tight_supply_fixes_now():
    r = decide_fix_wait(FixWaitInput(
        current_rate="22", forecast_7d="22", confidence_7d=0.6,
        days_to_deadline=40, vessel_availability=0.2,
    ))
    assert r.decision == "FIX_NOW"


def test_high_volatility_fall_partial_fix():
    r = decide_fix_wait(FixWaitInput(
        current_rate="22", forecast_7d="20.5", forecast_14d="20",
        confidence_7d=0.75, confidence_14d=0.72, days_to_deadline=40,
        freight_volatility=0.8,
    ))
    assert r.decision == "PARTIAL_FIX"


def test_flat_outlook_monitors():
    r = decide_fix_wait(FixWaitInput(
        current_rate="22", forecast_7d="22.1", confidence_7d=0.7, days_to_deadline=40,
    ))
    assert r.decision == "MONITOR"


def test_thresholds_reported_in_drivers():
    r = decide_fix_wait(FixWaitInput(current_rate="22", forecast_7d="20", confidence_7d=0.8))
    assert "thresholds" in r.drivers
    assert "material_move_pct" in r.drivers["thresholds"]


def test_zero_rate_raises():
    with pytest.raises(FixWaitError):
        decide_fix_wait(FixWaitInput(current_rate="0"))

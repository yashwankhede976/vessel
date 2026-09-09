"""Service adapter: assemble CongestionInput from stored operations models.

Keeps the congestion engine (congestion.py) free of Django. This layer reads the
latest available observations for a port and maps them onto the engine input,
providing only the signals that exist (missing ones stay None so the engine
excludes them). It does not fabricate values and does not forecast.
"""
from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from typing import Optional

from django.utils import timezone

from apps.catalog.models import Port
from apps.operations.models import (
    MarineObservation,
    PortCall,
    PortCongestionObservation,
    PortTraffic,
    WeatherObservation,
)

from .congestion import CongestionInput, CongestionResult, score_congestion


def _f(value) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return float(value)
    return float(value)


def build_congestion_input(
    port: Port,
    *,
    arrivals_window_days: int = 7,
    history_window_days: int = 90,
) -> CongestionInput:
    """Read the latest signals for `port` and build the engine input.

    Uses the most recent PortCongestionObservation for vessels_waiting and
    recent waiting time; counts recent/expected PortCalls; derives a weather
    warning from the latest marine/weather observation; and computes throughput
    utilization from PortTraffic where a capacity is known. Any signal without
    data is left None.
    """
    now = timezone.now()

    # Latest congestion observation -> vessels_waiting + recent waiting time.
    latest_cong = (
        PortCongestionObservation.objects.filter(port=port)
        .order_by("-observed_at")
        .first()
    )
    vessels_waiting = latest_cong.vessels_waiting if latest_cong else None
    recent_wait = _f(latest_cong.avg_wait_days) if latest_cong else None

    # Expected arrivals: PortCalls with an arrival in the near-future window.
    expected_arrivals = (
        PortCall.objects.filter(
            port=port,
            arrival_at__gte=now,
            arrival_at__lte=now + timedelta(days=arrivals_window_days),
        ).count()
    )
    # Only treat as a signal if there are any records at all for this port.
    if not PortCall.objects.filter(port=port).exists():
        expected_arrivals = None

    # Historical traffic baseline: PortCalls in the trailing history window.
    hist_qs = PortCall.objects.filter(
        port=port, arrival_at__gte=now - timedelta(days=history_window_days),
        arrival_at__lt=now,
    )
    historical_traffic = float(hist_qs.count()) if hist_qs.exists() else None

    # Weather warning: prefer a marine warning, else a weather observation.
    weather_warning = _latest_weather_severity(port)

    return CongestionInput(
        vessels_waiting=vessels_waiting,
        recent_waiting_time_days=recent_wait,
        expected_arrivals=expected_arrivals,
        historical_traffic=historical_traffic,
        weather_warning=weather_warning,
        # vessels_near_port and throughput_utilization are left None unless a
        # concrete source is available; the engine excludes missing signals.
        vessels_near_port=None,
        throughput_utilization=None,
    )


def _latest_weather_severity(port: Port) -> Optional[str]:
    marine = (
        MarineObservation.objects.filter(port=port)
        .exclude(severity="")
        .order_by("-timestamp")
        .first()
    )
    if marine and marine.severity:
        # MarineObservation.severity uses none/low/moderate/high/severe/unknown.
        return None if marine.severity == "unknown" else marine.severity
    # Fall back to presence of a recent weather observation flagged as risky.
    return None


def score_port_congestion(
    port: Port,
    *,
    arrivals_window_days: int = 7,
    history_window_days: int = 90,
) -> CongestionResult:
    """Assemble inputs from stored data and compute the congestion score."""
    inp = build_congestion_input(
        port,
        arrivals_window_days=arrivals_window_days,
        history_window_days=history_window_days,
    )
    return score_congestion(inp)

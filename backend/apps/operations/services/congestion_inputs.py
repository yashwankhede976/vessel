"""Automatic derivation of congestion-model inputs from ingested data.

Builds a fully-populated CongestionInput for a port by deriving every signal the
Prompt-1 congestion model consumes from the stored observation tables:

    vessels_near_port      from AIS positions (traffic_density within a radius)
    vessels_waiting        from the latest PortCongestionObservation
    arrival_density        expected arrivals in a near-future window (PortCall)
    recent_throughput      recent PortTraffic throughput (also -> utilization)
    weather_risk           latest marine warning severity for the port
    historical_waiting     trailing PortCall count as a baseline

This EXTENDS the existing congestion_service.build_congestion_input (which
leaves vessels_near_port and throughput_utilization as None) by filling those
from AIS + PortTraffic. Every signal is derived only where data exists; missing
signals stay None so the engine excludes them (never fabricated).

The result feeds score_congestion() unchanged (the Prompt-1 model).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
from decimal import Decimal
from typing import Optional

from django.db.models import Sum
from django.utils import timezone

from apps.catalog.models import Port
from apps.operations.models import PortTraffic
from apps.operations.services.ais_features import NEAR_PORT_RADIUS_NM, traffic_density
from apps.operations.services.congestion import CongestionInput, score_congestion
from apps.operations.services.congestion_service import build_congestion_input

# Documented default: throughput (tonnes) over a recent window at which a port is
# treated as fully utilized (utilization 1.0). Deliberately generic; a port can
# override. Used only to derive a 0..1 utilization proxy from PortTraffic.
DEFAULT_THROUGHPUT_CAPACITY_TONNES = 2_000_000.0
THROUGHPUT_WINDOW_DAYS = 30


def _f(value) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return float(value)
    return float(value)


@dataclass
class DerivedCongestionInputs:
    """The derived CongestionInput plus a provenance note of what was available."""

    congestion_input: CongestionInput
    derived: dict = field(default_factory=dict)  # signal -> value (or None)

    def to_dict(self) -> dict:
        return {"derived": self.derived}


def derive_congestion_input(
    port: Port,
    *,
    near_radius_nm: float = NEAR_PORT_RADIUS_NM,
    arrivals_window_days: int = 7,
    history_window_days: int = 90,
    throughput_capacity_tonnes: float = DEFAULT_THROUGHPUT_CAPACITY_TONNES,
    now=None,
) -> DerivedCongestionInputs:
    """Derive a fully-populated CongestionInput for `port` from ingested data."""
    now = now or timezone.now()

    # Start from the existing adapter (vessels_waiting, expected_arrivals,
    # historical_traffic, weather_warning) so we reuse that logic verbatim.
    base = build_congestion_input(
        port,
        arrivals_window_days=arrivals_window_days,
        history_window_days=history_window_days,
    )

    # Enrich: vessels_near_port from AIS traffic density (None if no AIS/coords).
    vessels_near = traffic_density(port, radius_nm=near_radius_nm, now=now)

    # Enrich: throughput utilization from recent PortTraffic (None if no data).
    throughput_utilization = None
    recent_throughput = None
    since = now - timedelta(days=THROUGHPUT_WINDOW_DAYS)
    agg = (
        PortTraffic.objects.filter(port=port, period__gte=since.date())
        .aggregate(total=Sum("throughput_tonnes"))
    )
    total = _f(agg.get("total"))
    if total is not None:
        recent_throughput = total
        if throughput_capacity_tonnes > 0:
            throughput_utilization = max(0.0, min(total / throughput_capacity_tonnes, 1.0))

    enriched = CongestionInput(
        vessels_waiting=base.vessels_waiting,
        recent_waiting_time_days=base.recent_waiting_time_days,
        expected_arrivals=base.expected_arrivals,
        historical_traffic=base.historical_traffic,
        weather_warning=base.weather_warning,
        vessels_near_port=vessels_near,
        throughput_utilization=throughput_utilization,
    )

    derived = {
        "vessels_near_port": vessels_near,
        "vessels_waiting": base.vessels_waiting,
        "arrival_density": base.expected_arrivals,
        "recent_throughput": recent_throughput,
        "throughput_utilization": throughput_utilization,
        "weather_risk": base.weather_warning,
        "historical_waiting": base.historical_traffic,
        "recent_waiting_time_days": base.recent_waiting_time_days,
    }
    return DerivedCongestionInputs(congestion_input=enriched, derived=derived)


def score_port_congestion_enriched(port: Port, **kwargs):
    """Derive the fuller input (AIS + PortTraffic enriched) and score it.

    A drop-in richer alternative to congestion_service.score_port_congestion
    that additionally uses AIS traffic density and PortTraffic utilization.
    """
    derived = derive_congestion_input(port, **kwargs)
    return score_congestion(derived.congestion_input)

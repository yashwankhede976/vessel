"""Service adapter: assemble ETAInput from stored ORM models.

Keeps the ETA engine (eta.py) free of Django. Reads the vessel's latest AIS
position and speed, the route's remaining distance, and destination conditions
(congestion score + expected waiting + a weather-risk proxy), then calls the
engine. Only signals that exist are supplied; the engine's own validation
rejects anything impossible.

Does NOT compute demurrage.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Optional

from apps.catalog.models import Route, Vessel

from .congestion_service import score_port_congestion
from .eta import ETAInput, ETAResult, predict_eta


def _f(value) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return float(value)
    return float(value)


def build_eta_input(
    vessel: Vessel,
    route: Route,
    *,
    route_distance_nm: Optional[float] = None,
    speed_kn: Optional[float] = None,
    weather_risk: float = 0.0,
    expected_port_waiting_days: float = 0.0,
) -> ETAInput:
    """Assemble an ETAInput for a vessel on a route from stored data.

    Speed: prefer an explicit override, else the vessel's latest AIS SOG, else
    the vessel's service speed. Distance: explicit override, else the route's
    stored distance. Destination congestion is derived from the congestion
    engine on the route's destination port.
    """
    # Speed: latest AIS position SOG -> service speed -> override.
    if speed_kn is None:
        latest_pos = vessel.positions.order_by("-timestamp").first()
        if latest_pos is not None and latest_pos.sog is not None:
            speed_kn = _f(latest_pos.sog)
        elif vessel.speed is not None:
            speed_kn = _f(vessel.speed)

    # Position (for validation/provenance) from the latest AIS report.
    lat = lon = None
    latest_pos = vessel.positions.order_by("-timestamp").first()
    if latest_pos is not None:
        lat, lon = _f(latest_pos.latitude), _f(latest_pos.longitude)

    # Distance: override else route's stored distance.
    if route_distance_nm is None:
        route_distance_nm = _f(route.distance_nm)

    # Destination congestion score (0..100) from the congestion engine.
    congestion_score = 0.0
    try:
        congestion_score = score_port_congestion(route.destination_port).congestion_score
    except Exception:
        congestion_score = 0.0

    return ETAInput(
        route_distance_nm=route_distance_nm if route_distance_nm is not None else 0.0,
        speed_kn=speed_kn if speed_kn is not None else 0.0,
        latitude=lat,
        longitude=lon,
        weather_risk=weather_risk,
        destination_congestion=congestion_score,
        expected_port_waiting_days=expected_port_waiting_days,
    )


def predict_vessel_eta(
    vessel: Vessel,
    route: Route,
    **kwargs,
) -> ETAResult:
    """Assemble inputs from stored data and predict the ETA (raises
    ETAValidationError if the assembled inputs are impossible)."""
    return predict_eta(build_eta_input(vessel, route, **kwargs))

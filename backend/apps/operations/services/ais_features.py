"""Derived AIS features (transparent, deterministic).

Computes navigational/spatial features from stored AIS positions and the port
catalogue, without requiring PostGIS: all distances use the haversine formula on
the portable latitude/longitude decimals every position and port already carry.

Features:
    nearest_port          the closest catalogue port to a position
    distance_to_port      great-circle distance (nautical miles) to a port
    speed_trend           recent SOG slope (kn/hour) for a vessel/MMSI
    traffic_density       count of distinct vessels within a radius of a port
    arrival_probability   heuristic 0..1 that a vessel is approaching a port

Everything is a deterministic function of the inputs. Missing inputs yield
None (never a fabricated value). No ML.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal
from typing import Iterable, Optional

from django.utils import timezone

from apps.catalog.models import Port
from apps.operations.models import AISPosition

EARTH_RADIUS_NM = 3440.065  # mean Earth radius in nautical miles

# Documented defaults.
NEAR_PORT_RADIUS_NM = 50.0       # "near a port" search radius for traffic density
APPROACH_MAX_RANGE_NM = 200.0    # beyond this, arrival probability ~ 0
SPEED_TREND_WINDOW_HOURS = 6.0   # window for the recent SOG slope
MIN_MAKING_WAY_KN = 0.5          # below this a vessel is effectively stationary


def _f(value) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return float(value)
    return float(value)


def haversine_nm(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance between two lat/lon points, in nautical miles."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = (
        math.sin(dphi / 2) ** 2
        + math.cos(p1) * math.cos(p2) * math.sin(dlambda / 2) ** 2
    )
    return 2 * EARTH_RADIUS_NM * math.asin(min(1.0, math.sqrt(a)))


def _bearing_deg(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Initial bearing (degrees, 0..360) from point 1 to point 2."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dl = math.radians(lon2 - lon1)
    x = math.sin(dl) * math.cos(p2)
    y = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dl)
    return (math.degrees(math.atan2(x, y)) + 360.0) % 360.0


@dataclass
class NearestPort:
    port_id: int
    port_name: str
    distance_nm: float

    def to_dict(self) -> dict:
        return {
            "port_id": self.port_id,
            "port_name": self.port_name,
            "distance_nm": round(self.distance_nm, 2),
        }


def distance_to_port(lat, lon, port: Port) -> Optional[float]:
    """Great-circle distance (nm) from a position to a port, or None if unknown."""
    plat, plon = _f(port.latitude), _f(port.longitude)
    flat, flon = _f(lat), _f(lon)
    if None in (plat, plon, flat, flon):
        return None
    return round(haversine_nm(flat, flon, plat, plon), 2)


def nearest_port(lat, lon, *, ports: Optional[Iterable[Port]] = None) -> Optional[NearestPort]:
    """Return the closest catalogue port to a position, or None if none/invalid."""
    flat, flon = _f(lat), _f(lon)
    if flat is None or flon is None:
        return None
    if ports is None:
        ports = Port.objects.all()
    best: Optional[NearestPort] = None
    for port in ports:
        plat, plon = _f(port.latitude), _f(port.longitude)
        if plat is None or plon is None:
            continue
        d = haversine_nm(flat, flon, plat, plon)
        if best is None or d < best.distance_nm:
            best = NearestPort(port_id=port.pk, port_name=port.name, distance_nm=d)
    return best


def speed_trend(
    mmsi: str = "",
    *,
    vessel_id: Optional[int] = None,
    window_hours: float = SPEED_TREND_WINDOW_HOURS,
    now=None,
) -> Optional[float]:
    """Recent SOG slope (knots per hour) for a vessel over `window_hours`.

    Positive => accelerating, negative => slowing (e.g. approaching a berth).
    Returns None when fewer than two SOG samples exist in the window.
    Least-squares slope over (hours_since_start, sog).
    """
    now = now or timezone.now()
    since = now - timedelta(hours=window_hours)
    qs = AISPosition.objects.filter(timestamp__gte=since, timestamp__lte=now)
    if vessel_id is not None:
        qs = qs.filter(vessel_id=vessel_id)
    elif mmsi:
        qs = qs.filter(mmsi=mmsi)
    else:
        return None
    samples = [
        (p.timestamp, _f(p.sog))
        for p in qs.order_by("timestamp")
        if p.sog is not None
    ]
    if len(samples) < 2:
        return None

    t0 = samples[0][0]
    xs = [(t - t0).total_seconds() / 3600.0 for t, _ in samples]
    ys = [s for _, s in samples]
    n = len(xs)
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    denom = sum((x - mean_x) ** 2 for x in xs)
    if denom == 0:
        return None
    slope = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys)) / denom
    return round(slope, 4)


def traffic_density(
    port: Port,
    *,
    radius_nm: float = NEAR_PORT_RADIUS_NM,
    window_hours: float = 6.0,
    now=None,
) -> Optional[int]:
    """Count of DISTINCT vessels whose latest recent position lies within
    `radius_nm` of the port. None if the port has no coordinates."""
    plat, plon = _f(port.latitude), _f(port.longitude)
    if plat is None or plon is None:
        return None
    now = now or timezone.now()
    since = now - timedelta(hours=window_hours)

    latest_by_key: dict[str, AISPosition] = {}
    for pos in AISPosition.objects.filter(
        timestamp__gte=since, timestamp__lte=now
    ).order_by("-timestamp"):
        key = pos.mmsi or f"v{pos.vessel_id}"
        latest_by_key.setdefault(key, pos)

    count = 0
    for pos in latest_by_key.values():
        plat_, plon_ = _f(pos.latitude), _f(pos.longitude)
        if plat_ is None or plon_ is None:
            continue
        if haversine_nm(plat_, plon_, plat, plon) <= radius_nm:
            count += 1
    return count


def arrival_probability(
    position: AISPosition,
    port: Port,
    *,
    max_range_nm: float = APPROACH_MAX_RANGE_NM,
) -> Optional[float]:
    """Heuristic probability (0..1) that a vessel is approaching a port.

    Combines three deterministic signals, each 0..1, then averages:
      * proximity: closer => higher (linear over max_range_nm)
      * heading alignment: COG/heading pointing toward the port => higher
      * making way: moving (SOG above a threshold) => higher

    Returns None if the position or port lacks coordinates. This is a transparent
    heuristic, NOT a trained model.
    """
    flat, flon = _f(position.latitude), _f(position.longitude)
    plat, plon = _f(port.latitude), _f(port.longitude)
    if None in (flat, flon, plat, plon):
        return None

    dist = haversine_nm(flat, flon, plat, plon)
    proximity = max(0.0, 1.0 - dist / max_range_nm)

    # Heading alignment: compare COG (or heading) to the bearing to the port.
    course = _f(position.cog)
    if course is None:
        course = _f(position.heading)
    if course is not None:
        bearing = _bearing_deg(flat, flon, plat, plon)
        diff = abs((course - bearing + 180.0) % 360.0 - 180.0)  # 0..180
        alignment = max(0.0, 1.0 - diff / 180.0)
    else:
        alignment = 0.5  # unknown heading -> neutral

    sog = _f(position.sog)
    if sog is None:
        making_way = 0.5
    else:
        making_way = 1.0 if sog >= MIN_MAKING_WAY_KN else 0.0

    prob = (proximity + alignment + making_way) / 3.0
    return round(max(0.0, min(1.0, prob)), 4)

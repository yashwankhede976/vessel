"""Deterministic vessel ETA prediction.

A transparent, rule-based ETA estimator — NOT a machine-learning model. Given a
vessel's position, speed, remaining route distance, and the conditions along the
way and at the destination (weather, congestion, expected port waiting), it
computes:

- a point ETA,
- probabilistic ETAs at P50 / P80 / P95 (later percentiles are later dates,
  reflecting downside delay risk), and
- an explainable breakdown of the estimated delay causes (hours per cause).

Impossible or nonsensical inputs are rejected (see ETAValidationError).

This module does NOT compute demurrage. It is pure Python (no Django) so it is
easy to unit-test; a thin service adapter maps ORM models onto ETAInput.
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Optional

# ---------------------------------------------------------------------------
# Tunable, documented constants (the model is deterministic given these).
# ---------------------------------------------------------------------------
# Sanity bounds for validation.
MIN_SPEED_KN = 0.1          # a vessel making way must have positive speed
MAX_SPEED_KN = 40.0         # no bulk carrier sustains > ~40 kn; reject as bad data
MAX_DISTANCE_NM = 15000.0   # longest plausible single voyage leg
MAX_TOTAL_ETA_DAYS = 120.0  # an ETA beyond ~4 months is treated as impossible

# Weather slowdown: a 0..1 weather-risk reduces effective speed by up to this
# fraction (e.g. risk 1.0 => 35% slower steaming).
MAX_WEATHER_SPEED_PENALTY = 0.35

# Congestion at destination adds waiting time. `destination_congestion` is a
# 0..100 score (see congestion engine); it maps to up to this many extra days.
MAX_CONGESTION_DELAY_DAYS = 6.0

# Uncertainty: the spread of the ETA distribution grows with the amount of
# delay in the voyage. Base relative sigma plus a component proportional to the
# delay fraction. These produce the P50/P80/P95 spread.
BASE_REL_SIGMA = 0.05       # >=5% timing uncertainty even on a clean voyage
DELAY_REL_SIGMA = 0.60      # additional sigma scaled by the delay fraction

# Delay-probability threshold: the voyage is considered "materially late" if it
# arrives more than this fraction beyond the clean (delay-free) transit time.
# delay_probability is P(actual > clean_transit * (1 + LATE_THRESHOLD_FRACTION))
# under the same Normal(total_hours, sigma_hours) model used for the percentiles.
LATE_THRESHOLD_FRACTION = 0.10   # >10% over clean transit == a meaningful delay
# Delay causes contributing at least this many hours are surfaced as reasons.
MATERIAL_DELAY_HOURS = 1.0

# Standard-normal z-scores for the requested percentiles (one-sided, later).
Z_P50 = 0.0
Z_P80 = 0.8416
Z_P95 = 1.6449

HOURS_PER_DAY = 24.0


class ETAValidationError(ValueError):
    """Raised when inputs are impossible/nonsensical and no ETA can be made."""


@dataclass
class ETAInput:
    """Inputs for an ETA estimate."""

    # Remaining distance to destination (nautical miles).
    route_distance_nm: float
    # Current speed over ground (knots).
    speed_kn: float
    # Optional current position (for validation/provenance).
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    # Weather/marine risk along the route, 0..1 (0 = clear, 1 = severe).
    weather_risk: float = 0.0
    # Destination port congestion score, 0..100 (see congestion engine).
    destination_congestion: float = 0.0
    # Expected port waiting time in days (e.g. queue for a berth).
    expected_port_waiting_days: float = 0.0
    # When the estimate is anchored; defaults to now (UTC) at compute time.
    departure_time: Optional[datetime] = None


@dataclass
class DelayCause:
    cause: str
    delay_hours: float
    detail: str


@dataclass
class ETAResult:
    eta: str                 # point ETA (ISO-8601)
    eta_p50: str
    eta_p80: str
    eta_p95: str
    total_hours: float       # point estimate, hours from departure
    base_transit_hours: float
    total_delay_hours: float
    delay_causes: list[DelayCause]
    inputs: dict
    # Probability (0..1) the voyage arrives materially late vs a clean transit
    # (see LATE_THRESHOLD_FRACTION). Deterministic from the same ETA
    # distribution used for the percentiles. Defaults keep older callers valid.
    delay_probability: float = 0.0
    # The material delay causes (>= MATERIAL_DELAY_HOURS), highest first.
    delay_reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        d = asdict(self)
        return d


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ETAValidationError(message)


def _validate(inp: ETAInput) -> None:
    _require(inp.route_distance_nm is not None and inp.route_distance_nm > 0,
             "route_distance_nm must be positive.")
    _require(inp.route_distance_nm <= MAX_DISTANCE_NM,
             f"route_distance_nm {inp.route_distance_nm} exceeds the maximum "
             f"plausible voyage distance ({MAX_DISTANCE_NM} nm).")
    _require(inp.speed_kn is not None and inp.speed_kn >= MIN_SPEED_KN,
             f"speed_kn must be at least {MIN_SPEED_KN} (a stationary/near-zero "
             "speed gives no finite ETA).")
    _require(inp.speed_kn <= MAX_SPEED_KN,
             f"speed_kn {inp.speed_kn} exceeds the maximum plausible speed "
             f"({MAX_SPEED_KN} kn).")
    _require(0.0 <= inp.weather_risk <= 1.0,
             "weather_risk must be within [0, 1].")
    _require(0.0 <= inp.destination_congestion <= 100.0,
             "destination_congestion must be within [0, 100].")
    _require(inp.expected_port_waiting_days >= 0.0,
             "expected_port_waiting_days cannot be negative.")
    if inp.latitude is not None:
        _require(-90.0 <= inp.latitude <= 90.0, "latitude out of range.")
    if inp.longitude is not None:
        _require(-180.0 <= inp.longitude <= 180.0, "longitude out of range.")


def predict_eta(inp: ETAInput) -> ETAResult:
    """Compute a deterministic ETA with P50/P80/P95 and delay causes.

    Raises ETAValidationError for impossible inputs (before and after
    computing, so an absurd total ETA is also rejected).
    """
    _validate(inp)

    departure = inp.departure_time or datetime.now(timezone.utc)
    if departure.tzinfo is None:
        departure = departure.replace(tzinfo=timezone.utc)

    # --- base transit: distance / speed, adjusted for weather slowdown ---
    weather_penalty = MAX_WEATHER_SPEED_PENALTY * inp.weather_risk
    effective_speed = inp.speed_kn * (1.0 - weather_penalty)
    _require(effective_speed >= MIN_SPEED_KN,
             "Effective speed after weather slowdown is too low for an ETA.")

    clean_transit_hours = inp.route_distance_nm / inp.speed_kn
    base_transit_hours = inp.route_distance_nm / effective_speed
    weather_delay_hours = base_transit_hours - clean_transit_hours

    # --- destination congestion delay (0..100 -> up to MAX_CONGESTION_DELAY_DAYS) ---
    congestion_delay_hours = (
        (inp.destination_congestion / 100.0) * MAX_CONGESTION_DELAY_DAYS * HOURS_PER_DAY
    )

    # --- explicit expected port waiting ---
    port_waiting_hours = inp.expected_port_waiting_days * HOURS_PER_DAY

    delay_causes = [
        DelayCause(
            cause="weather",
            delay_hours=round(weather_delay_hours, 2),
            detail=f"weather_risk={inp.weather_risk}: effective speed reduced "
                   f"{weather_penalty * 100:.0f}% ({inp.speed_kn}->"
                   f"{effective_speed:.1f} kn).",
        ),
        DelayCause(
            cause="destination_congestion",
            delay_hours=round(congestion_delay_hours, 2),
            detail=f"congestion score {inp.destination_congestion}/100.",
        ),
        DelayCause(
            cause="port_waiting",
            delay_hours=round(port_waiting_hours, 2),
            detail=f"expected waiting {inp.expected_port_waiting_days} day(s).",
        ),
    ]

    total_delay_hours = weather_delay_hours + congestion_delay_hours + port_waiting_hours
    total_hours = clean_transit_hours + total_delay_hours

    # Reject impossible/absurd totals.
    _require(total_hours <= MAX_TOTAL_ETA_DAYS * HOURS_PER_DAY,
             f"Computed ETA of {total_hours / HOURS_PER_DAY:.1f} days exceeds the "
             f"maximum plausible ({MAX_TOTAL_ETA_DAYS} days); rejecting.")

    # --- uncertainty: sigma grows with the delay fraction of the voyage ---
    delay_fraction = total_delay_hours / total_hours if total_hours > 0 else 0.0
    rel_sigma = BASE_REL_SIGMA + DELAY_REL_SIGMA * delay_fraction
    sigma_hours = total_hours * rel_sigma

    def at_percentile(z: float) -> datetime:
        return departure + timedelta(hours=total_hours + z * sigma_hours)

    point_eta = departure + timedelta(hours=total_hours)

    # --- delay probability: P(actual > clean_transit * (1 + threshold)) ---
    # Model actual arrival as Normal(total_hours, sigma_hours) (the same
    # distribution the percentiles come from). The "late" threshold is a
    # documented fraction over the clean (delay-free) transit time.
    late_threshold_hours = clean_transit_hours * (1.0 + LATE_THRESHOLD_FRACTION)
    if sigma_hours > 0:
        # Standard-normal upper-tail: 1 - CDF(z), CDF via erf.
        z = (late_threshold_hours - total_hours) / sigma_hours
        delay_probability = 0.5 * math.erfc(z / math.sqrt(2.0))
    else:
        delay_probability = 1.0 if total_hours > late_threshold_hours else 0.0
    delay_probability = max(0.0, min(1.0, delay_probability))

    # --- delay reasons: the material contributors, largest first ---
    delay_reasons = [
        c.cause
        for c in sorted(delay_causes, key=lambda c: c.delay_hours, reverse=True)
        if c.delay_hours >= MATERIAL_DELAY_HOURS
    ]

    return ETAResult(
        eta=point_eta.isoformat(),
        eta_p50=at_percentile(Z_P50).isoformat(),
        eta_p80=at_percentile(Z_P80).isoformat(),
        eta_p95=at_percentile(Z_P95).isoformat(),
        total_hours=round(total_hours, 2),
        base_transit_hours=round(base_transit_hours, 2),
        total_delay_hours=round(total_delay_hours, 2),
        delay_causes=delay_causes,
        inputs=asdict(inp) | {"departure_time": departure.isoformat()},
        delay_probability=round(delay_probability, 4),
        delay_reasons=delay_reasons,
    )

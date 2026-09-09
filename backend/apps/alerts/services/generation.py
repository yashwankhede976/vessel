"""Alert-generation service (deterministic, documented thresholds).

Detects the decision-relevant conditions listed in the spec and records an Alert
(deduped on a stable fingerprint) plus notifications. Detectors accept already-
computed inputs (freight moves, congestion scores, warnings, market pressure,
ETA delay probability, availability, compatibility) so this service composes the
existing engines/observations without re-deriving them — and stays easy to test.

EVERY threshold is a NAMED, DOCUMENTED constant below (per the platform rule
against undocumented thresholds). Each detector returns the created/updated
Alert or None (condition not met).
"""
from __future__ import annotations

from decimal import Decimal
from typing import Optional

from django.utils import timezone

from apps.alerts.models import Alert, AlertSeverity, AlertStatus, AlertType
from apps.alerts.services.notifications import dispatch

# =====================  DOCUMENTED ALERT THRESHOLDS  =======================
# Freight moves are fractional changes vs a reference (e.g. 0.05 = 5%).
FREIGHT_MOVE_PCT = 0.05              # >=5% move fires an increase/decrease alert
FREIGHT_MOVE_PCT_HIGH = 0.12         # >=12% move is HIGH severity
FREIGHT_VOLATILITY_THRESHOLD = 0.5   # 0..1 volatility at/above this fires
CONGESTION_SCORE_THRESHOLD = 55.0    # 0..100 congestion at/above this fires (HIGH band)
CONGESTION_SCORE_SEVERE = 75.0       # SEVERE band
VESSEL_SCARCITY_AVAILABILITY = 0.30  # 0..1 availability at/below this fires
ETA_DELAY_PROB_THRESHOLD = 0.6       # 0..1 delay probability at/above this fires
MARKET_PRESSURE_TIGHT = 75.0         # MPI at/above this is "extremely tight"
MARKET_PRESSURE_WEAK = 25.0          # MPI at/below this is "very weak"
# Marine/cyclone severities (from WarningSeverity) that warrant an alert.
WARNING_SEVERITIES_ALERT = {"moderate", "high", "severe"}
# ===========================================================================


def _dec(value) -> Optional[Decimal]:
    if value is None:
        return None
    return value if isinstance(value, Decimal) else Decimal(str(value))


def raise_alert(
    *,
    alert_type: str,
    severity: str,
    message: str,
    entity: str = "",
    trigger_value=None,
    threshold=None,
    recommended_action: str = "",
    dedup_key: str = "",
    context: Optional[dict] = None,
    route=None,
    port=None,
    vessel=None,
    notify: bool = True,
    timestamp=None,
) -> Alert:
    """Create or update an alert (deduped on dedup_key) and notify.

    If an OPEN (non-resolved) alert with the same dedup_key exists, it is updated
    in place (its trigger value/message/timestamp refreshed) rather than
    duplicated; otherwise a new NEW alert is created and notifications dispatched.
    """
    now = timestamp or timezone.now()
    defaults = {
        "alert_type": alert_type,
        "severity": severity,
        "timestamp": now,
        "entity": entity,
        "trigger_value": _dec(trigger_value),
        "threshold": _dec(threshold),
        "message": message,
        "recommended_action": recommended_action,
        "context": context or {},
        "route": route,
        "port": port,
        "vessel": vessel,
    }

    existing = None
    if dedup_key:
        existing = (
            Alert.objects.filter(dedup_key=dedup_key)
            .exclude(status=AlertStatus.RESOLVED)
            .order_by("-timestamp")
            .first()
        )

    if existing is not None:
        for field, value in defaults.items():
            setattr(existing, field, value)
        existing.save()
        return existing

    alert = Alert.objects.create(dedup_key=dedup_key, status=AlertStatus.NEW, **defaults)
    if notify:
        dispatch(alert)
    return alert


# ---------------------------------------------------------------------------
# Detectors — each returns an Alert or None.
# ---------------------------------------------------------------------------
def detect_freight_move(
    *, entity: str, current_rate, reference_rate, route=None, **kw
) -> Optional[Alert]:
    """Fire a freight increase/decrease alert when the move exceeds the
    documented threshold."""
    cur = float(current_rate)
    ref = float(reference_rate)
    if ref <= 0:
        return None
    move = (cur - ref) / ref
    if abs(move) < FREIGHT_MOVE_PCT:
        return None
    rising = move > 0
    severity = AlertSeverity.HIGH if abs(move) >= FREIGHT_MOVE_PCT_HIGH else AlertSeverity.MEDIUM
    alert_type = AlertType.FREIGHT_INCREASE if rising else AlertType.FREIGHT_DECREASE
    action = (
        "Consider fixing sooner to avoid paying more." if rising
        else "Consider waiting; rates are falling."
    )
    return raise_alert(
        alert_type=alert_type, severity=severity,
        message=f"Freight {'up' if rising else 'down'} {move*100:.1f}% on {entity} "
                f"({ref:g} -> {cur:g}).",
        entity=entity, trigger_value=round(move, 4), threshold=FREIGHT_MOVE_PCT,
        recommended_action=action, dedup_key=f"freight_move:{entity}",
        context={"current_rate": cur, "reference_rate": ref, "move_pct": round(move, 4)},
        route=route, **kw,
    )


def detect_freight_volatility(*, entity: str, volatility, route=None, **kw) -> Optional[Alert]:
    vol = float(volatility)
    if vol < FREIGHT_VOLATILITY_THRESHOLD:
        return None
    return raise_alert(
        alert_type=AlertType.FREIGHT_VOLATILITY,
        severity=AlertSeverity.HIGH if vol >= 0.75 else AlertSeverity.MEDIUM,
        message=f"Elevated freight volatility ({vol:.2f}) on {entity}.",
        entity=entity, trigger_value=round(vol, 4), threshold=FREIGHT_VOLATILITY_THRESHOLD,
        recommended_action="Consider hedging with a partial fix / term cover.",
        dedup_key=f"freight_vol:{entity}", context={"volatility": vol}, route=route, **kw,
    )


def detect_congestion(*, entity: str, congestion_score, port=None, **kw) -> Optional[Alert]:
    score = float(congestion_score)
    if score < CONGESTION_SCORE_THRESHOLD:
        return None
    severe = score >= CONGESTION_SCORE_SEVERE
    return raise_alert(
        alert_type=AlertType.CONGESTION_INCREASE,
        severity=AlertSeverity.CRITICAL if severe else AlertSeverity.HIGH,
        message=f"Port congestion elevated ({score:.0f}/100) at {entity}.",
        entity=entity, trigger_value=round(score, 2), threshold=CONGESTION_SCORE_THRESHOLD,
        recommended_action="Assess alternative ports / expect demurrage exposure.",
        dedup_key=f"congestion:{entity}", context={"congestion_score": score},
        port=port, **kw,
    )


def detect_marine_warning(*, entity: str, severity_level: str, port=None, cyclone=False, **kw):
    level = str(severity_level or "").lower()
    if level not in WARNING_SEVERITIES_ALERT:
        return None
    sev = {
        "moderate": AlertSeverity.MEDIUM,
        "high": AlertSeverity.HIGH,
        "severe": AlertSeverity.CRITICAL,
    }[level]
    atype = AlertType.CYCLONE_WARNING if cyclone else AlertType.MARINE_WARNING
    label = "Cyclone" if cyclone else "Marine"
    return raise_alert(
        alert_type=atype, severity=sev,
        message=f"{label} warning ({level}) affecting {entity}.",
        entity=entity, recommended_action="Review ETA/routing; expect weather delay.",
        dedup_key=f"{atype}:{entity}", context={"severity": level}, port=port, **kw,
    )


def detect_vessel_scarcity(*, entity: str, availability, **kw) -> Optional[Alert]:
    avail = float(availability)
    if avail > VESSEL_SCARCITY_AVAILABILITY:
        return None
    return raise_alert(
        alert_type=AlertType.VESSEL_SCARCITY,
        severity=AlertSeverity.HIGH if avail <= 0.15 else AlertSeverity.MEDIUM,
        message=f"Tonnage scarce for {entity} (availability {avail:.2f}).",
        entity=entity, trigger_value=round(avail, 4), threshold=VESSEL_SCARCITY_AVAILABILITY,
        recommended_action="Fix promptly / widen vessel search.",
        dedup_key=f"scarcity:{entity}", context={"availability": avail}, **kw,
    )


def detect_eta_delay(*, entity: str, delay_probability, vessel=None, **kw) -> Optional[Alert]:
    prob = float(delay_probability)
    if prob < ETA_DELAY_PROB_THRESHOLD:
        return None
    return raise_alert(
        alert_type=AlertType.ETA_DELAY,
        severity=AlertSeverity.HIGH if prob >= 0.8 else AlertSeverity.MEDIUM,
        message=f"High ETA-delay probability ({prob:.2f}) for {entity}.",
        entity=entity, trigger_value=round(prob, 4), threshold=ETA_DELAY_PROB_THRESHOLD,
        recommended_action="Communicate revised laycan; review demurrage exposure.",
        dedup_key=f"eta_delay:{entity}", context={"delay_probability": prob},
        vessel=vessel, **kw,
    )


def detect_port_incompatibility(*, entity: str, reason: str, port=None, vessel=None, **kw):
    return raise_alert(
        alert_type=AlertType.PORT_INCOMPATIBILITY, severity=AlertSeverity.HIGH,
        message=f"Vessel incompatible with {entity}: {reason}",
        entity=entity, recommended_action="Select a compatible vessel or port.",
        dedup_key=f"incompat:{entity}", context={"reason": reason},
        port=port, vessel=vessel, **kw,
    )


def detect_unusual_market_pressure(*, entity: str, market_pressure_index, **kw) -> Optional[Alert]:
    mpi = float(market_pressure_index)
    if mpi >= MARKET_PRESSURE_TIGHT:
        band, sev = "extremely tight", AlertSeverity.HIGH
    elif mpi <= MARKET_PRESSURE_WEAK:
        band, sev = "very weak", AlertSeverity.MEDIUM
    else:
        return None
    return raise_alert(
        alert_type=AlertType.UNUSUAL_MARKET_PRESSURE, severity=sev,
        message=f"Freight market {band} (pressure index {mpi:.0f}) for {entity}.",
        entity=entity, trigger_value=round(mpi, 2),
        threshold=MARKET_PRESSURE_TIGHT if mpi >= MARKET_PRESSURE_TIGHT else MARKET_PRESSURE_WEAK,
        recommended_action=(
            "Consider committing term cover." if mpi >= MARKET_PRESSURE_TIGHT
            else "Consider staying on spot to ride rates down."
        ),
        dedup_key=f"market_pressure:{entity}", context={"market_pressure_index": mpi}, **kw,
    )

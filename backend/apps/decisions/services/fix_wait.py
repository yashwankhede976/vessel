"""Fix / Wait timing decision engine (transparent, deterministic).

Given the current freight rate and 7/14/30-day forecasts (plus their confidence)
together with market context (vessel availability, congestion, volatility) and
the cargo deadline, it recommends one of:

    FIX_NOW      lock the fixture now (rates expected to rise / little downside
                 / deadline pressure / low confidence in a fall)
    WAIT         hold off (rates expected to fall with adequate confidence and
                 enough time before the deadline)
    PARTIAL_FIX  hedge: fix part now, leave part to the market (mixed signals)
    MONITOR      no strong signal / insufficient data — keep watching

EVERY threshold used is a NAMED, DOCUMENTED constant below (per the platform rule
that no arbitrary thresholds may be used without documentation). It is rule-based
— NOT ML. The output includes the numeric drivers and a plain-language reason so
the decision is fully auditable.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from decimal import Decimal
from enum import Enum
from typing import Optional

Number = float


class FixWaitDecision(str, Enum):
    FIX_NOW = "FIX_NOW"
    WAIT = "WAIT"
    PARTIAL_FIX = "PARTIAL_FIX"
    MONITOR = "MONITOR"


# =====================  DOCUMENTED DECISION THRESHOLDS  =====================
# All thresholds are explicit and justified; none are arbitrary.

# Expected rate move (fraction of current) that counts as "material". A forecast
# within +/-2% of current is treated as flat (noise), not a directional signal.
MATERIAL_MOVE_PCT = 0.02

# A "strong" expected fall/rise used to trigger a decisive WAIT / FIX_NOW.
STRONG_MOVE_PCT = 0.05           # >=5% expected move is a strong directional signal

# Minimum forecast confidence to ACT on a directional signal. Below this we do
# not trust the forecast enough to WAIT (we lean to fixing / monitoring).
MIN_CONFIDENCE_TO_ACT = 0.55

# Confidence at/above which a WAIT on an expected fall is decisive.
HIGH_CONFIDENCE = 0.70

# Deadline pressure: if the cargo must be fixed within this many days, we bias to
# FIX_NOW regardless of a mild expected fall (no time to wait out the market).
DEADLINE_URGENT_DAYS = 7
# Below this many days we consider a WAIT only if the fall is strong + confident.
DEADLINE_TIGHT_DAYS = 14

# Tight tonnage supply (low availability) argues for fixing now before it tightens
# further. availability is 0..1 (1 = abundant). Below this it's "tight".
TIGHT_AVAILABILITY = 0.35

# High volatility reduces our willingness to WAIT (the forecast is less reliable
# in a whippy market) and nudges toward PARTIAL_FIX. volatility is 0..1.
HIGH_VOLATILITY = 0.6
# ===========================================================================


class FixWaitError(ValueError):
    """Raised for invalid fix/wait inputs."""


@dataclass
class FixWaitInput:
    """Inputs for the timing decision.

    Forecasts are freight rates in the SAME unit as current_rate (currency/tonne).
    Any forecast/confidence left None is treated as unavailable (not used).
    """

    current_rate: Decimal
    forecast_7d: Optional[Decimal] = None
    forecast_14d: Optional[Decimal] = None
    forecast_30d: Optional[Decimal] = None
    confidence_7d: Optional[float] = None
    confidence_14d: Optional[float] = None
    confidence_30d: Optional[float] = None
    days_to_deadline: Optional[int] = None
    vessel_availability: Optional[float] = None   # 0..1 (1 = abundant tonnage)
    congestion_score: Optional[float] = None       # 0..100
    freight_volatility: Optional[float] = None      # 0..1

    def __post_init__(self):
        self.current_rate = _dec(self.current_rate)
        self.forecast_7d = _dec(self.forecast_7d)
        self.forecast_14d = _dec(self.forecast_14d)
        self.forecast_30d = _dec(self.forecast_30d)


@dataclass
class FixWaitResult:
    decision: str
    expected_move_pct: Optional[float]     # signed; negative = fall expected
    effective_confidence: Optional[float]
    drivers: dict
    reason: str

    def to_dict(self) -> dict:
        return {
            "decision": self.decision,
            "expected_move_pct": self.expected_move_pct,
            "effective_confidence": self.effective_confidence,
            "drivers": self.drivers,
            "reason": self.reason,
        }


def _dec(v) -> Optional[Decimal]:
    if v is None:
        return None
    return v if isinstance(v, Decimal) else Decimal(str(v))


def _validate(inp: FixWaitInput) -> None:
    if inp.current_rate is None or inp.current_rate <= 0:
        raise FixWaitError("current_rate must be positive.")
    for name in ("confidence_7d", "confidence_14d", "confidence_30d"):
        c = getattr(inp, name)
        if c is not None and not (0.0 <= c <= 1.0):
            raise FixWaitError(f"{name} must be within [0, 1].")
    if inp.days_to_deadline is not None and inp.days_to_deadline < 0:
        raise FixWaitError("days_to_deadline cannot be negative.")


def _blended_outlook(inp: FixWaitInput):
    """Confidence-weighted expected move (fraction of current) across horizons.

    Returns (expected_move_pct, effective_confidence, per_horizon) or (None,
    None, {}) when no forecast is available. Nearer horizons get more weight.
    """
    cur = float(inp.current_rate)
    horizons = [
        (inp.forecast_7d, inp.confidence_7d, 3.0, "7d"),
        (inp.forecast_14d, inp.confidence_14d, 2.0, "14d"),
        (inp.forecast_30d, inp.confidence_30d, 1.0, "30d"),
    ]
    num = 0.0
    wsum = 0.0
    conf_num = 0.0
    per_horizon = {}
    for fc, conf, horizon_w, label in horizons:
        if fc is None:
            continue
        move = (float(fc) - cur) / cur
        c = conf if conf is not None else 0.5   # unknown confidence -> neutral 0.5
        w = horizon_w * c
        num += move * w
        wsum += w
        conf_num += (conf if conf is not None else 0.5) * horizon_w
        per_horizon[label] = {"forecast": float(fc), "move_pct": round(move, 4),
                              "confidence": conf}
    if wsum == 0:
        return None, None, {}
    expected_move = num / wsum
    # Effective confidence = horizon-weighted mean of provided confidences.
    horizon_w_total = sum(hw for _, _, hw, _ in horizons
                          if _forecast_present(inp, hw))
    eff_conf = conf_num / horizon_w_total if horizon_w_total else 0.5
    return round(expected_move, 4), round(eff_conf, 3), per_horizon


def _forecast_present(inp: FixWaitInput, horizon_w: float) -> bool:
    mapping = {3.0: inp.forecast_7d, 2.0: inp.forecast_14d, 1.0: inp.forecast_30d}
    return mapping.get(horizon_w) is not None


def decide_fix_wait(inp: FixWaitInput) -> FixWaitResult:
    """Return the FIX_NOW / WAIT / PARTIAL_FIX / MONITOR decision."""
    _validate(inp)

    expected_move, eff_conf, per_horizon = _blended_outlook(inp)

    drivers = {
        "expected_move_pct": expected_move,
        "effective_confidence": eff_conf,
        "per_horizon": per_horizon,
        "days_to_deadline": inp.days_to_deadline,
        "vessel_availability": inp.vessel_availability,
        "congestion_score": inp.congestion_score,
        "freight_volatility": inp.freight_volatility,
        "thresholds": {
            "material_move_pct": MATERIAL_MOVE_PCT,
            "strong_move_pct": STRONG_MOVE_PCT,
            "min_confidence_to_act": MIN_CONFIDENCE_TO_ACT,
            "high_confidence": HIGH_CONFIDENCE,
            "deadline_urgent_days": DEADLINE_URGENT_DAYS,
            "deadline_tight_days": DEADLINE_TIGHT_DAYS,
            "tight_availability": TIGHT_AVAILABILITY,
            "high_volatility": HIGH_VOLATILITY,
        },
    }

    # --- No forecast at all -> MONITOR (we won't guess a direction) ---
    if expected_move is None:
        return FixWaitResult(
            decision=FixWaitDecision.MONITOR.value,
            expected_move_pct=None,
            effective_confidence=None,
            drivers=drivers,
            reason="No freight forecast available; monitoring until a "
                   "directional signal with sufficient confidence appears.",
        )

    reasons: list[str] = []

    # --- Deadline pressure dominates: urgent deadline => FIX_NOW ---
    if inp.days_to_deadline is not None and inp.days_to_deadline <= DEADLINE_URGENT_DAYS:
        reasons.append(
            f"Deadline in {inp.days_to_deadline}d (<= {DEADLINE_URGENT_DAYS}d urgent "
            "threshold): no time to wait out the market."
        )
        return _result(FixWaitDecision.FIX_NOW, expected_move, eff_conf, drivers, reasons)

    # --- Tight tonnage supply => bias to FIX_NOW ---
    tight_supply = (
        inp.vessel_availability is not None
        and inp.vessel_availability <= TIGHT_AVAILABILITY
    )

    falling = expected_move <= -MATERIAL_MOVE_PCT
    rising = expected_move >= MATERIAL_MOVE_PCT
    strong_fall = expected_move <= -STRONG_MOVE_PCT
    confident = eff_conf is not None and eff_conf >= MIN_CONFIDENCE_TO_ACT
    high_conf = eff_conf is not None and eff_conf >= HIGH_CONFIDENCE
    high_vol = (
        inp.freight_volatility is not None
        and inp.freight_volatility >= HIGH_VOLATILITY
    )

    # --- Rates expected to RISE (or supply tightening) => FIX_NOW ---
    if rising:
        reasons.append(
            f"Rates expected to rise {expected_move*100:.1f}% "
            f"(>= +{MATERIAL_MOVE_PCT*100:.0f}%): fixing now avoids paying more."
        )
        return _result(FixWaitDecision.FIX_NOW, expected_move, eff_conf, drivers, reasons)
    if tight_supply:
        reasons.append(
            f"Tonnage availability {inp.vessel_availability} "
            f"(<= {TIGHT_AVAILABILITY}) is tight: fix before supply tightens further."
        )
        return _result(FixWaitDecision.FIX_NOW, expected_move, eff_conf, drivers, reasons)

    # --- Rates expected to FALL ---
    if falling:
        deadline_ok = (
            inp.days_to_deadline is None
            or inp.days_to_deadline > DEADLINE_TIGHT_DAYS
        )
        if strong_fall and high_conf and deadline_ok and not high_vol:
            reasons.append(
                f"Rates expected to fall {expected_move*100:.1f}% "
                f"(<= -{STRONG_MOVE_PCT*100:.0f}%) with high confidence "
                f"({eff_conf} >= {HIGH_CONFIDENCE}) and time before deadline: waiting "
                "is expected to pay off."
            )
            return _result(FixWaitDecision.WAIT, expected_move, eff_conf, drivers, reasons)
        if confident and not high_vol and deadline_ok:
            reasons.append(
                f"Rates expected to fall {expected_move*100:.1f}% with adequate "
                f"confidence ({eff_conf} >= {MIN_CONFIDENCE_TO_ACT}) but the signal "
                "is not decisively strong: hedge with a partial fix."
            )
            return _result(FixWaitDecision.PARTIAL_FIX, expected_move, eff_conf, drivers, reasons)
        # Falling but low confidence / high volatility / tight deadline.
        if high_vol:
            reasons.append(
                f"Expected fall but volatility {inp.freight_volatility} "
                f">= {HIGH_VOLATILITY} makes the forecast unreliable: partial fix "
                "to hedge."
            )
            return _result(FixWaitDecision.PARTIAL_FIX, expected_move, eff_conf, drivers, reasons)
        reasons.append(
            f"Expected fall but confidence {eff_conf} < {MIN_CONFIDENCE_TO_ACT} "
            "(or deadline tight): not enough conviction to wait — monitor."
        )
        return _result(FixWaitDecision.MONITOR, expected_move, eff_conf, drivers, reasons)

    # --- Flat outlook (within +/- material move) => MONITOR ---
    reasons.append(
        f"Expected move {expected_move*100:.1f}% is within +/-"
        f"{MATERIAL_MOVE_PCT*100:.0f}% (flat): no directional edge — monitor."
    )
    return _result(FixWaitDecision.MONITOR, expected_move, eff_conf, drivers, reasons)


def _result(decision, move, conf, drivers, reasons) -> FixWaitResult:
    return FixWaitResult(
        decision=decision.value,
        expected_move_pct=move,
        effective_confidence=conf,
        drivers=drivers,
        reason=" ".join(reasons),
    )

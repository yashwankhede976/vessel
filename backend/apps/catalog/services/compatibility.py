"""Deterministic, rule-based vessel–port–berth compatibility engine.

This is intentionally NOT a machine-learning model. It is transparent,
rule-based logic: each physical/operational constraint is checked
independently, produces a status and a human-readable reason, and the
per-constraint outcomes are aggregated into an overall verdict and score.

Design principles
-----------------
- Deterministic: same inputs always give the same output.
- Explainable: every non-passing constraint yields a reason string.
- Honest about missing data: a constraint whose data is unavailable is
  reported as UNKNOWN, never silently treated as a pass or a fail.

Overall status aggregation
---------------------------
- INCOMPATIBLE  if any constraint FAILs (a hard physical limit is exceeded).
- CONDITIONAL   if no FAILs but at least one constraint is CONDITIONAL
                (feasible only under a stated condition, e.g. a high tide).
- UNKNOWN       if no FAILs/CONDITIONALs but there is not enough data to
                confirm compatibility (no constraint could be positively
                evaluated, or a critical dimension is unknown).
- COMPATIBLE    if all evaluable constraints PASS and enough are known.

The engine works on plain values (Decimals, sets, dicts) so it is trivially
unit-testable and carries no Django dependency. A thin service adapter
(service.py) maps ORM models onto these inputs.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import Optional

# A tiny tolerance so exact-equality at a limit counts as "meets the limit"
# rather than tipping over due to Decimal representation.
EPSILON = Decimal("0.001")


class Status(str, Enum):
    COMPATIBLE = "COMPATIBLE"
    CONDITIONAL = "CONDITIONAL"
    INCOMPATIBLE = "INCOMPATIBLE"
    UNKNOWN = "UNKNOWN"


class CheckOutcome(str, Enum):
    PASS = "PASS"
    CONDITIONAL = "CONDITIONAL"
    FAIL = "FAIL"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class ConstraintResult:
    """Outcome of a single constraint check."""

    name: str
    outcome: CheckOutcome
    reason: Optional[str] = None


@dataclass
class CompatibilityInput:
    """Plain inputs for one vessel–berth evaluation.

    All physical dimensions are Decimals in metres / tonnes. Any value left as
    None means "not available" and yields an UNKNOWN outcome for that check.
    """

    # Vessel.
    vessel_loa: Optional[Decimal] = None
    vessel_beam: Optional[Decimal] = None
    vessel_draft: Optional[Decimal] = None
    vessel_dwt: Optional[Decimal] = None
    vessel_cargo: Optional[str] = None  # commodity name the vessel intends to carry

    # Berth / port limits.
    max_loa: Optional[Decimal] = None
    max_beam: Optional[Decimal] = None
    max_draft: Optional[Decimal] = None
    max_dwt: Optional[Decimal] = None
    supported_commodities: Optional[set[str]] = None  # None => unknown

    # Conditional allowances (e.g. extra draft available on a high tide).
    tidal_draft_allowance: Optional[Decimal] = None

    # Documented operational restrictions. Each is (applies: bool|None, reason).
    # applies True  -> CONDITIONAL (feasible but with a documented caveat)
    # applies None  -> UNKNOWN (restriction exists but applicability unclear)
    # applies False -> ignored
    operational_restrictions: list[tuple[Optional[bool], str]] = field(
        default_factory=list
    )


@dataclass
class CompatibilityResult:
    status: Status
    score: int
    reasons: list[str]
    checks: list[ConstraintResult]

    def to_dict(self) -> dict:
        return {
            "status": self.status.value,
            "score": self.score,
            "reasons": self.reasons,
            "checks": [
                {"name": c.name, "outcome": c.outcome.value, "reason": c.reason}
                for c in self.checks
            ],
        }


# Per-outcome score penalties (out of 100). A FAIL floors the score to 0.
_PENALTY_CONDITIONAL = 12
_PENALTY_UNKNOWN = 6


def _check_dimension(
    name: str,
    vessel_value: Optional[Decimal],
    limit: Optional[Decimal],
    unit: str,
    tidal_allowance: Optional[Decimal] = None,
) -> ConstraintResult:
    """Generic 'vessel dimension must not exceed berth limit' check."""
    if vessel_value is None or limit is None:
        return ConstraintResult(
            name,
            CheckOutcome.UNKNOWN,
            f"{name} could not be evaluated: "
            f"{'vessel value' if vessel_value is None else 'berth limit'} unknown.",
        )

    if vessel_value <= limit + EPSILON:
        return ConstraintResult(name, CheckOutcome.PASS)

    # Exceeds the normal limit. If a tidal/extra allowance brings it within
    # reach, it's CONDITIONAL rather than a hard fail.
    if tidal_allowance is not None and vessel_value <= limit + tidal_allowance + EPSILON:
        return ConstraintResult(
            name,
            CheckOutcome.CONDITIONAL,
            f"{name} {vessel_value}{unit} exceeds the normal limit "
            f"{limit}{unit} but is within the tidal allowance "
            f"(+{tidal_allowance}{unit}); feasible under favourable tide.",
        )

    return ConstraintResult(
        name,
        CheckOutcome.FAIL,
        f"{name} {vessel_value}{unit} exceeds the berth limit {limit}{unit}.",
    )


def _check_cargo(
    vessel_cargo: Optional[str],
    supported: Optional[set[str]],
) -> ConstraintResult:
    name = "Cargo compatibility"
    if vessel_cargo is None:
        return ConstraintResult(
            name, CheckOutcome.UNKNOWN, "No cargo specified for the vessel."
        )
    if supported is None:
        return ConstraintResult(
            name,
            CheckOutcome.UNKNOWN,
            "Berth's supported commodities are not documented.",
        )
    if len(supported) == 0:
        return ConstraintResult(
            name,
            CheckOutcome.UNKNOWN,
            "Berth lists no supported commodities.",
        )
    # Case-insensitive membership.
    supported_lower = {s.lower() for s in supported}
    if vessel_cargo.lower() in supported_lower:
        return ConstraintResult(name, CheckOutcome.PASS)
    return ConstraintResult(
        name,
        CheckOutcome.FAIL,
        f"Cargo '{vessel_cargo}' is not among the berth's supported commodities.",
    )


def _check_restrictions(
    restrictions: list[tuple[Optional[bool], str]],
) -> list[ConstraintResult]:
    results: list[ConstraintResult] = []
    for applies, reason in restrictions:
        if applies is True:
            results.append(
                ConstraintResult("Operational restriction", CheckOutcome.CONDITIONAL, reason)
            )
        elif applies is None:
            results.append(
                ConstraintResult("Operational restriction", CheckOutcome.UNKNOWN, reason)
            )
        # applies is False -> no impact, not recorded.
    return results


def evaluate(inp: CompatibilityInput) -> CompatibilityResult:
    """Evaluate compatibility deterministically and return the verdict."""
    checks: list[ConstraintResult] = [
        _check_dimension("LOA", inp.vessel_loa, inp.max_loa, "m"),
        _check_dimension("Beam", inp.vessel_beam, inp.max_beam, "m"),
        _check_dimension(
            "Draft", inp.vessel_draft, inp.max_draft, "m", inp.tidal_draft_allowance
        ),
        _check_dimension("DWT", inp.vessel_dwt, inp.max_dwt, "t"),
        _check_cargo(inp.vessel_cargo, inp.supported_commodities),
    ]
    checks.extend(_check_restrictions(inp.operational_restrictions))

    # Aggregate.
    has_fail = any(c.outcome == CheckOutcome.FAIL for c in checks)
    has_conditional = any(c.outcome == CheckOutcome.CONDITIONAL for c in checks)
    num_pass = sum(1 for c in checks if c.outcome == CheckOutcome.PASS)
    num_unknown = sum(1 for c in checks if c.outcome == CheckOutcome.UNKNOWN)

    reasons = [c.reason for c in checks if c.reason and c.outcome != CheckOutcome.PASS]

    if has_fail:
        # A hard physical limit is exceeded — no score to give.
        status = Status.INCOMPATIBLE
        score = 0
    elif has_conditional:
        status = Status.CONDITIONAL
        score = _score(num_unknown, num_conditional=_count(checks, CheckOutcome.CONDITIONAL))
    elif num_pass == 0:
        # No fails or conditionals, but nothing could be positively confirmed.
        status = Status.UNKNOWN
        score = _score(num_unknown, num_conditional=0)
    else:
        # At least one positive pass and no fails/conditionals.
        status = Status.COMPATIBLE
        score = _score(num_unknown, num_conditional=0)

    return CompatibilityResult(
        status=status, score=score, reasons=reasons, checks=checks
    )


def _count(checks: list[ConstraintResult], outcome: CheckOutcome) -> int:
    return sum(1 for c in checks if c.outcome == outcome)


def _score(num_unknown: int, num_conditional: int) -> int:
    """Compute a 0–100 confidence score from penalties (never below 1 here)."""
    score = 100 - num_conditional * _PENALTY_CONDITIONAL - num_unknown * _PENALTY_UNKNOWN
    return max(1, min(100, score))

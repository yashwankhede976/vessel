"""Service adapter: map catalog ORM models onto the compatibility engine.

Keeps the engine (compatibility.py) free of Django. This layer reads the
Vessel, Port, and Berth models, extracts the relevant values (treating the
curated 'UNKNOWN' provenance markers as missing data), and calls evaluate().
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Optional

from apps.catalog.models import Berth, Port, Vessel

from .compatibility import (
    CompatibilityInput,
    CompatibilityResult,
    evaluate,
)

UNKNOWN = "UNKNOWN"


def _meta_decimal(port: Port, key: str) -> Optional[Decimal]:
    """Read a Decimal value from Port.metadata[key]['value'], or None if unknown."""
    entry = (port.metadata or {}).get(key)
    if not isinstance(entry, dict):
        return None
    value = entry.get("value")
    if value is None or value == UNKNOWN or value == "":
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def _positive_or_none(value: Optional[Decimal]) -> Optional[Decimal]:
    """Treat non-positive placeholder values (e.g. handling_rate 0) as unknown."""
    if value is None:
        return None
    return value if value > 0 else None


def build_input(
    vessel: Vessel,
    port: Port,
    berth: Optional[Berth] = None,
    *,
    cargo: Optional[str] = None,
    tidal_draft_allowance: Optional[Decimal] = None,
) -> CompatibilityInput:
    """Assemble a CompatibilityInput from the models.

    Berth dimensions take precedence; where a berth is not given or lacks a
    value, port-level metadata limits are used as a fallback. Unknown values
    become None (engine reports UNKNOWN for that check).
    """
    # Berth-level limits (may be None-ish if berth not provided).
    if berth is not None:
        max_loa = _positive_or_none(berth.max_loa)
        max_beam = _positive_or_none(berth.max_beam)
        max_draft = _positive_or_none(berth.max_draft)
    else:
        max_loa = max_beam = max_draft = None

    # Fall back to port-level metadata limits where berth values are absent.
    if max_loa is None:
        max_loa = _meta_decimal(port, "max_loa_m")
    if max_beam is None:
        max_beam = _meta_decimal(port, "max_beam_m")
    if max_draft is None:
        max_draft = _meta_decimal(port, "max_draft_m")

    max_dwt = _meta_decimal(port, "max_dwt_t")

    # Supported commodities: prefer the berth M2M; None => unknown.
    supported: Optional[set[str]] = None
    if berth is not None:
        names = {c.name for c in berth.supported_commodities.all()}
        supported = names if names else None

    # Documented operational restrictions from port metadata (informational →
    # CONDITIONAL when present). We surface the port's documented restriction
    # text as a conditional caveat rather than a pass/fail.
    restrictions: list[tuple[Optional[bool], str]] = []
    op = (port.metadata or {}).get("operational_constraints")
    if isinstance(op, dict):
        op_value = op.get("value")
        if op_value and op_value != UNKNOWN:
            restrictions.append((True, f"Documented operational restriction: {op_value}"))

    return CompatibilityInput(
        vessel_loa=vessel.loa,
        vessel_beam=vessel.beam,
        vessel_draft=vessel.draft,
        vessel_dwt=vessel.dwt,
        vessel_cargo=cargo,
        max_loa=max_loa,
        max_beam=max_beam,
        max_draft=max_draft,
        max_dwt=max_dwt,
        supported_commodities=supported,
        tidal_draft_allowance=tidal_draft_allowance,
        operational_restrictions=restrictions,
    )


def evaluate_compatibility(
    vessel: Vessel,
    port: Port,
    berth: Optional[Berth] = None,
    *,
    cargo: Optional[str] = None,
    tidal_draft_allowance: Optional[Decimal] = None,
) -> CompatibilityResult:
    """Evaluate vessel–port(–berth) compatibility from the ORM models."""
    inp = build_input(
        vessel,
        port,
        berth,
        cargo=cargo,
        tidal_draft_allowance=tidal_draft_allowance,
    )
    return evaluate(inp)

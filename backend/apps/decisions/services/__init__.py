"""Domain/service layer for the decisions app.

Deterministic, explainable chartering/procurement economics (no ML, no
optimization). Currently provides the voyage economics engine.
"""
from .voyage_economics import (
    VoyageEconomicsError,
    VoyageEconomicsInput,
    VoyageEconomicsResult,
    compute_voyage_economics,
)

__all__ = [
    "VoyageEconomicsError",
    "VoyageEconomicsInput",
    "VoyageEconomicsResult",
    "compute_voyage_economics",
]

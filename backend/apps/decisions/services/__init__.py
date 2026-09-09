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
from .vessel_suitability import (
    SuitabilityInput,
    SuitabilityResult,
    FactorScore,
    score_vessel_suitability,
)
from .landed_cost import (
    LandedCostError,
    LandedCostInput,
    LandedCostResult,
    CostComponent,
    Money,
    OriginComparison,
    PROJECT_ORIGINS,
    compute_landed_cost,
    compare_origins,
)

__all__ = [
    "VoyageEconomicsError",
    "VoyageEconomicsInput",
    "VoyageEconomicsResult",
    "compute_voyage_economics",
    "SuitabilityInput",
    "SuitabilityResult",
    "FactorScore",
    "score_vessel_suitability",
    "LandedCostError",
    "LandedCostInput",
    "LandedCostResult",
    "CostComponent",
    "Money",
    "OriginComparison",
    "PROJECT_ORIGINS",
    "compute_landed_cost",
    "compare_origins",
]

"""Feature engineering for the freight forecasting system.

Pure pandas/numpy — no Django, no model training. Builds leakage-safe features
(rolling stats, lags, pct-change, seasonal, and domain indicators) on top of the
unified dataset (see ml/datasets/). Every transform uses only past-and-present
data within each lane; nothing derived from future rows leaks into a training
row (see docs/FREIGHT_DATASET_SCHEMA.md §4).
"""
from .validation import (
    LEAKAGE_PRONE_COLUMNS,
    TimeOrderError,
    validate_temporal_order,
)
from .transforms import (
    add_lags,
    add_pct_change,
    add_rolling_mean,
    add_rolling_volatility,
    add_seasonal_features,
)
from .indicators import (
    add_demand_indicators,
    add_port_congestion_indicators,
    add_vessel_supply_indicators,
    add_weather_risk_indicators,
)
from .pipeline import LANE, build_features

__all__ = [
    "build_features",
    "LANE",
    "validate_temporal_order",
    "TimeOrderError",
    "LEAKAGE_PRONE_COLUMNS",
    "add_lags",
    "add_pct_change",
    "add_rolling_mean",
    "add_rolling_volatility",
    "add_seasonal_features",
    "add_demand_indicators",
    "add_port_congestion_indicators",
    "add_vessel_supply_indicators",
    "add_weather_risk_indicators",
]

"""Feature engineering pipeline entrypoint.

Composes: sort (per lane by date) -> validate temporal order -> leakage-safe
transforms (lags, rolling mean/vol, pct-change, seasonal) -> domain indicators.
Returns the engineered frame. Future target columns are preserved as labels but
NEVER used as inputs to any feature, and can be split out via `feature_columns`.

Pure pandas — no Django, no model training.
"""
from __future__ import annotations

from typing import Optional

import pandas as pd

from .validation import (
    GRAIN,
    LANE,
    LEAKAGE_PRONE_COLUMNS,
    require_columns,
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

# Default configuration for the freight-rate value series.
DEFAULT_VALUE_COLUMN = "freight_rate"
DEFAULT_LAGS = [1, 2, 3, 7]
DEFAULT_ROLL_WINDOWS = [3, 7, 14]
DEFAULT_PCT_PERIODS = [1, 7]


def build_features(
    df: pd.DataFrame,
    *,
    value_column: str = DEFAULT_VALUE_COLUMN,
    lags: Optional[list[int]] = None,
    roll_windows: Optional[list[int]] = None,
    pct_periods: Optional[list[int]] = None,
    validate: bool = True,
) -> pd.DataFrame:
    """Engineer leakage-safe features from a dataset frame.

    Parameters
    ----------
    df : dataset frame containing at least GRAIN + `value_column`.
    value_column : the series to build lag/rolling/pct-change features from
        (default the current freight_rate). Must NOT be a future target.
    validate : run temporal-order validation before transforming (recommended).

    Returns a copy of `df` with engineered feature columns appended. Rows keep
    their original grain; early rows have NaN for features that need history.
    """
    if value_column in LEAKAGE_PRONE_COLUMNS:
        raise ValueError(
            f"value_column '{value_column}' is a future/target column; "
            "building features from it would leak the label."
        )

    require_columns(df, GRAIN + [value_column])

    lags = lags or DEFAULT_LAGS
    roll_windows = roll_windows or DEFAULT_ROLL_WINDOWS
    pct_periods = pct_periods or DEFAULT_PCT_PERIODS

    if df.empty:
        return df.copy()

    # 1) Deterministic per-lane chronological order (required by all transforms).
    out = df.copy()
    out["date"] = pd.to_datetime(out["date"])
    out = out.sort_values(LANE + ["date"]).reset_index(drop=True)

    # 2) Validate ordering/uniqueness before any windowed op.
    if validate:
        validate_temporal_order(out)

    # 3) Leakage-safe value-series transforms.
    out = add_lags(out, value_column, lags)
    out = add_rolling_mean(out, value_column, roll_windows)
    out = add_rolling_volatility(out, value_column, roll_windows)
    out = add_pct_change(out, value_column, pct_periods)

    # 4) Seasonal (calendar-only) features.
    out = add_seasonal_features(out)

    # 5) Domain indicators (derived from as-of features only).
    out = add_vessel_supply_indicators(out)
    out = add_demand_indicators(out)
    out = add_port_congestion_indicators(out)
    out = add_weather_risk_indicators(out)

    return out


def engineered_feature_columns(df: pd.DataFrame) -> list[str]:
    """Return the columns safe to use as MODEL INPUTS.

    Excludes the grain keys and all future/target columns. This is how a trainer
    should select X — it guarantees no future target is fed as a feature.
    """
    exclude = set(GRAIN) | LEAKAGE_PRONE_COLUMNS | {"freight_rate"}
    return [c for c in df.columns if c not in exclude]

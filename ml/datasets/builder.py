"""Assemble the unified freight forecasting dataset.

Pure pandas/numpy. No Django, no I/O to the database, no model training. The
caller supplies source frames (extracted from the DB or elsewhere) keyed by the
row grain (date, origin, destination, vessel_type) or by lane. This module joins
them, derives features, and computes the future_* targets, returning a single
tidy DataFrame conforming to schema.py.

Leakage discipline
-------------------
- Features describe state known AS OF `date`.
- `historical_freight_rate` is the freight rate LAGGED by one step per lane
  (yesterday's rate), so it never contains the same-day realized rate.
- `freight_rate` (current target) is the realized same-day rate.
- `future_7d/14d/30d_freight` are realized rates looked up FORWARD by the
  horizon per lane, using a merge_asof on a daily calendar (nearest within a
  tolerance), so targets come only from the future.
"""
from __future__ import annotations

import warnings
from typing import Optional

import numpy as np
import pandas as pd

from .schema import (
    FEATURE_COLUMNS,
    GRAIN_COLUMNS,
    TARGET_HORIZONS,
    column_order,
)

# pandas 2.2 emits noisy chained-assignment *preview* FutureWarnings for the
# pandas-3.0 Copy-on-Write transition. Our assignments operate on owned copies
# (we always `df = <frame>.copy()` or reassign `df = df...`), so the behaviour
# is correct today; silence only this forward-looking preview to keep output
# clean. Revisit when upgrading to pandas 3.0.
warnings.filterwarnings(
    "ignore",
    category=FutureWarning,
    message=".*ChainedAssignmentError.*",
)
try:  # pandas may not expose this in all versions
    warnings.filterwarnings("ignore", category=pd.errors.SettingWithCopyWarning)
except AttributeError:  # pragma: no cover
    pass

GRAIN = ["date", "origin", "destination", "vessel_type"]
LANE = ["origin", "destination", "vessel_type"]

# Monsoon months relevant to the Bay of Bengal (heuristic: SW Jun-Sep, NE Oct-Dec).
MONSOON_MONTHS = {6, 7, 8, 9, 10, 11, 12}


def _empty_frame() -> pd.DataFrame:
    return pd.DataFrame(columns=column_order())


def build_dataset(
    freight: pd.DataFrame,
    *,
    routes: Optional[pd.DataFrame] = None,
    vessel_availability: Optional[pd.DataFrame] = None,
    congestion: Optional[pd.DataFrame] = None,
    commodity_volume: Optional[pd.DataFrame] = None,
    commodity_price: Optional[pd.DataFrame] = None,
    bunker: Optional[pd.DataFrame] = None,
    weather_risk: Optional[pd.DataFrame] = None,
    trade_volume: Optional[pd.DataFrame] = None,
    target_tolerance_days: int = 3,
) -> pd.DataFrame:
    """Build the unified dataset.

    Parameters
    ----------
    freight : DataFrame with columns [date, origin, destination, vessel_type,
        freight_rate]. This is the spine — one row per grain — and the source of
        the current/lagged/future freight values.
    routes : optional [origin, destination, route_distance_nm]
    vessel_availability : optional [date, origin, vessel_type, vessel_availability]
    congestion : optional [date, destination, port_congestion, port_waiting_time]
    commodity_volume : optional [date, destination, commodity_import_volume]
    commodity_price : optional [date, commodity_price]
    bunker : optional [date, bunker_indicator]
    weather_risk : optional [date, destination, weather_risk]
    trade_volume : optional [date, origin, destination, trade_volume]
    target_tolerance_days : how close a forward observation must be to the exact
        horizon date to count as that target (merge_asof nearest tolerance).

    Returns
    -------
    DataFrame conforming to schema.column_order().
    """
    if freight is None or len(freight) == 0:
        return _empty_frame()

    df = freight.copy()
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values(GRAIN).reset_index(drop=True)

    # Deduplicate the spine on the grain (keep last freight_rate per grain).
    df = df.drop_duplicates(subset=GRAIN, keep="last").reset_index(drop=True)

    # --- lagged historical freight rate (per lane, previous observation) ---
    df = df.sort_values(["origin", "destination", "vessel_type", "date"])
    df["historical_freight_rate"] = (
        df.groupby(LANE, observed=True)["freight_rate"].shift(1)
    )

    # --- future targets (forward look per lane) ---
    df = _attach_future_targets(df, target_tolerance_days)

    # --- static / calendar features ---
    df["seasonality_month"] = df["date"].dt.month.astype("Int64")
    month = df["date"].dt.month
    df["seasonality_sin"] = np.sin(2 * np.pi * month / 12.0)
    df["seasonality_cos"] = np.cos(2 * np.pi * month / 12.0)
    df["is_monsoon"] = month.isin(MONSOON_MONTHS).astype("Int64")

    # --- joins with optional source frames ---
    df = _left_join(df, routes, on=["origin", "destination"])
    df = _left_join(df, vessel_availability, on=["date", "origin", "vessel_type"])
    df = _left_join(df, congestion, on=["date", "destination"])
    df = _left_join(df, commodity_volume, on=["date", "destination"])
    df = _left_join(df, commodity_price, on=["date"])
    df = _left_join(df, bunker, on=["date"])
    df = _left_join(df, weather_risk, on=["date", "destination"])
    df = _left_join(df, trade_volume, on=["date", "origin", "destination"])

    # --- derived proxies ---
    df["ton_mile_proxy"] = _safe_mul(df.get("route_distance_nm"), df.get("commodity_import_volume"))
    df["vessel_supply_proxy"] = _supply_proxy(df)

    # --- ensure every schema column exists, then order + type ---
    df = _finalize(df)
    return df


def _attach_future_targets(df: pd.DataFrame, tolerance_days: int) -> pd.DataFrame:
    """For each grain row, look up the realized freight rate `h` days later.

    Uses a per-lane merge_asof(direction="nearest") against the lane's own
    freight series, restricted to a tolerance window around date+h. This pulls
    the target only from future observations.
    """
    tol = pd.Timedelta(days=tolerance_days)
    out = df.copy()

    for col, horizon in TARGET_HORIZONS.items():
        out[col] = np.nan

    # Work lane by lane.
    for _, lane_df in df.groupby(LANE, observed=True):
        lane_series = lane_df[["date", "freight_rate"]].sort_values("date")
        for col, horizon in TARGET_HORIZONS.items():
            target_dates = lane_df[["date"]].copy()
            target_dates["target_date"] = target_dates["date"] + pd.Timedelta(days=horizon)
            target_dates = target_dates.sort_values("target_date")

            merged = pd.merge_asof(
                target_dates,
                lane_series.rename(columns={"date": "obs_date"}),
                left_on="target_date",
                right_on="obs_date",
                direction="nearest",
                tolerance=tol,
            )
            # Map back onto the original rows by their `date`.
            merged = merged.set_index("date")["freight_rate"]
            out.loc[lane_df.index, col] = lane_df["date"].map(merged).to_numpy()

    return out


def _left_join(df: pd.DataFrame, other: Optional[pd.DataFrame], on: list[str]) -> pd.DataFrame:
    if other is None or len(other) == 0:
        return df
    other = other.copy()
    if "date" in on and "date" in other.columns:
        other["date"] = pd.to_datetime(other["date"])
    # Only join on keys actually present in both frames.
    keys = [k for k in on if k in df.columns and k in other.columns]
    if not keys:
        return df
    other = other.drop_duplicates(subset=keys, keep="last")
    return df.merge(other, on=keys, how="left")


def _safe_mul(a, b):
    if a is None or b is None:
        return np.nan
    return pd.to_numeric(a, errors="coerce") * pd.to_numeric(b, errors="coerce")


def _supply_proxy(df: pd.DataFrame) -> pd.Series:
    """vessel_availability normalized by ton-mile demand (supply tightness).

    Higher => more available tonnage relative to demand. Guards against
    divide-by-zero and missing inputs (yields NaN).
    """
    avail = pd.to_numeric(df.get("vessel_availability"), errors="coerce") if "vessel_availability" in df else pd.Series(np.nan, index=df.index)
    demand = pd.to_numeric(df.get("ton_mile_proxy"), errors="coerce") if "ton_mile_proxy" in df else pd.Series(np.nan, index=df.index)
    # Scale demand down so the proxy is O(1); avoid inf.
    scaled = demand.replace(0, np.nan) / 1_000_000.0
    return avail / scaled


def _finalize(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    order = column_order()
    for name in order:
        if name not in df.columns:
            df[name] = np.nan

    # Apply dtypes where sensible (categories for grain, Int64 for counts).
    df["origin"] = df["origin"].astype("category")
    df["destination"] = df["destination"].astype("category")
    df["vessel_type"] = df["vessel_type"].astype("category")
    for c in ("vessel_availability", "seasonality_month", "is_monsoon"):
        df[c] = pd.to_numeric(df[c], errors="coerce").astype("Int64")

    return df[order].sort_values(GRAIN).reset_index(drop=True)

"""Leakage-safe time-series transforms (per lane).

All transforms operate WITHIN each lane (origin, destination, vessel_type) on
chronologically-sorted rows. To prevent target leakage, rolling/lag/pct-change
features derived from a value series are **shifted by one step** by default, so
a row's feature reflects only information available *before* that row's date —
never the current or any future row.

The caller must have validated temporal order first (validation.validate_
temporal_order). These functions do not re-sort; they assume sorted input and
preserve the frame's index.
"""
from __future__ import annotations

import warnings

import numpy as np
import pandas as pd

# Silence pandas 2.2 chained-assignment *preview* warnings for the pandas-3.0
# Copy-on-Write transition; our assignments target owned copies. Revisit at the
# pandas 3.0 upgrade. (Mirrors ml/datasets/builder.py.)
warnings.filterwarnings(
    "ignore", category=FutureWarning, message=".*ChainedAssignmentError.*"
)
try:
    warnings.filterwarnings("ignore", category=pd.errors.SettingWithCopyWarning)
except AttributeError:  # pragma: no cover
    pass

LANE = ["origin", "destination", "vessel_type"]


def _grouped(df: pd.DataFrame, column: str):
    return df.groupby(LANE, observed=True)[column]


def add_lags(
    df: pd.DataFrame, column: str, lags: list[int], *, prefix: str | None = None
) -> pd.DataFrame:
    """Add lag features: value of `column` `k` steps earlier within the lane.

    lag>=1 only (a lag of 0 would be the current value = potential target leak).
    """
    out = df.copy()
    name = prefix or column
    for k in lags:
        if k < 1:
            raise ValueError(f"Lag must be >= 1 (got {k}); lag 0 risks leakage.")
        out[f"{name}_lag_{k}"] = _grouped(out, column).shift(k)
    return out


def add_rolling_mean(
    df: pd.DataFrame,
    column: str,
    windows: list[int],
    *,
    shift: int = 1,
    min_periods: int = 1,
    prefix: str | None = None,
) -> pd.DataFrame:
    """Rolling mean over the last `w` PAST rows within the lane.

    The series is shifted by `shift` (default 1) BEFORE rolling, so the window
    ends at the previous row — the current row's value is excluded. This makes
    the feature safe even when `column` is the target series.
    """
    out = df.copy()
    name = prefix or column
    base = _grouped(out, column).shift(shift)
    grp = base.groupby([out[c] for c in LANE], observed=True)
    for w in windows:
        out[f"{name}_rollmean_{w}"] = grp.transform(
            lambda s, _w=w: s.rolling(_w, min_periods=min_periods).mean()
        )
    return out


def add_rolling_volatility(
    df: pd.DataFrame,
    column: str,
    windows: list[int],
    *,
    shift: int = 1,
    min_periods: int = 2,
    prefix: str | None = None,
) -> pd.DataFrame:
    """Rolling volatility (std) over the last `w` PAST rows within the lane.

    Same shift-then-roll discipline as add_rolling_mean. min_periods defaults to
    2 (std of one point is undefined -> NaN).
    """
    out = df.copy()
    name = prefix or column
    base = _grouped(out, column).shift(shift)
    grp = base.groupby([out[c] for c in LANE], observed=True)
    for w in windows:
        out[f"{name}_rollvol_{w}"] = grp.transform(
            lambda s, _w=w: s.rolling(_w, min_periods=min_periods).std()
        )
    return out


def add_pct_change(
    df: pd.DataFrame, column: str, periods: list[int], *, prefix: str | None = None
) -> pd.DataFrame:
    """Percentage change of `column` over `p` PAST steps within the lane.

    Defined as (prev - prev_p) / prev_p using shifted values, so the current
    row's value never enters the ratio (no target leak). NaN/inf are cleaned.
    """
    out = df.copy()
    name = prefix or column
    shifted = _grouped(out, column).shift(1)  # previous value (past)
    grp = shifted.groupby([out[c] for c in LANE], observed=True)
    for p in periods:
        if p < 1:
            raise ValueError(f"pct_change period must be >= 1 (got {p}).")
        prev_p = grp.shift(p)
        change = (shifted - prev_p) / prev_p.replace(0, np.nan)
        out[f"{name}_pctchg_{p}"] = change.replace([np.inf, -np.inf], np.nan)
    return out


def add_seasonal_features(df: pd.DataFrame) -> pd.DataFrame:
    """Calendar/seasonal features derived purely from `date` (no leakage risk).

    Adds day-of-year, week-of-year, quarter, and a monsoon flag if not already
    present. (Month + cyclical encodings are produced by the dataset builder;
    this adds finer-grained calendar signal.)
    """
    out = df.copy()
    dt = pd.to_datetime(out["date"])
    out["day_of_year"] = dt.dt.dayofyear.astype("Int64")
    out["week_of_year"] = dt.dt.isocalendar().week.astype("Int64")
    out["quarter"] = dt.dt.quarter.astype("Int64")
    if "is_monsoon" not in out.columns:
        out["is_monsoon"] = dt.dt.month.isin({6, 7, 8, 9, 10, 11, 12}).astype("Int64")
    return out

"""Validation and leakage guards for feature engineering.

These checks are the safety rail for the whole pipeline: they ensure the frame
is sorted per lane by date, has no duplicate timestamps within a lane, and that
features derived from *future* information are never fed into training rows.
"""
from __future__ import annotations

import pandas as pd

GRAIN = ["date", "origin", "destination", "vessel_type"]
LANE = ["origin", "destination", "vessel_type"]

# Columns that contain FUTURE information by construction (targets). Any feature
# must never be derived from these, and they must be excluded from the feature
# matrix used to train (they are labels, not inputs). See dataset schema §4.
LEAKAGE_PRONE_COLUMNS = {
    "future_7d_freight",
    "future_14d_freight",
    "future_30d_freight",
}


class TimeOrderError(ValueError):
    """Raised when rows are not correctly ordered/keyed in time within a lane."""


def require_columns(df: pd.DataFrame, columns: list[str]) -> None:
    missing = [c for c in columns if c not in df.columns]
    if missing:
        raise ValueError(f"Frame is missing required columns: {missing}")


def validate_temporal_order(df: pd.DataFrame, *, lane: list[str] = LANE) -> None:
    """Validate that within each lane, `date` is strictly increasing.

    Raises TimeOrderError if any lane is unsorted or has duplicate timestamps.
    This must pass before any rolling/lag feature is computed, because those
    transforms assume rows are in chronological order per lane.
    """
    require_columns(df, ["date"] + lane)

    if df.empty:
        return

    dates = pd.to_datetime(df["date"])
    if dates.isna().any():
        raise TimeOrderError("Found null/unparseable dates.")

    for keys, group in df.assign(_d=dates).groupby(lane, observed=True):
        d = group["_d"]
        # Strictly increasing => no duplicates and correct order.
        if not d.is_monotonic_increasing:
            raise TimeOrderError(
                f"Dates are not sorted ascending within lane {keys!r}. "
                "Sort by lane+date before feature engineering."
            )
        if d.duplicated().any():
            raise TimeOrderError(
                f"Duplicate timestamps within lane {keys!r}; the grain "
                "(date, origin, destination, vessel_type) must be unique."
            )


def assert_no_future_source(feature_sources: dict[str, list[str]]) -> None:
    """Guard: no engineered feature may be derived from a leakage-prone column.

    `feature_sources` maps a produced feature name -> the source columns it was
    derived from. Raises if any source is a future/target column.
    """
    offenders = {
        feat: [s for s in srcs if s in LEAKAGE_PRONE_COLUMNS]
        for feat, srcs in feature_sources.items()
    }
    offenders = {f: s for f, s in offenders.items() if s}
    if offenders:
        raise TimeOrderError(
            f"Leakage: features derived from future columns: {offenders}"
        )

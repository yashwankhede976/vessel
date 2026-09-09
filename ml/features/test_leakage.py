"""Leakage-prevention tests for the feature pipeline.

Run from ml/ with the ml venv:
    .venv/bin/python -m features.test_leakage
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from features.pipeline import build_features, engineered_feature_columns
from features.validation import TimeOrderError, validate_temporal_order
from features.transforms import add_lags, add_pct_change, add_rolling_mean


def _assert(cond, msg):
    if not cond:
        raise AssertionError(msg)


def _lane_frame(rates, origin="Australia", dest="Paradip", vtype="capesize", start="2026-01-01"):
    dates = pd.date_range(start, periods=len(rates), freq="D")
    return pd.DataFrame({
        "date": dates, "origin": origin, "destination": dest,
        "vessel_type": vtype, "freight_rate": rates,
    })


# --- core leakage guarantee: a future spike must not affect earlier rows ---
def test_future_spike_does_not_affect_earlier_features():
    # Rates are flat 10.0 except a huge spike on the LAST day.
    rates = [10.0] * 9 + [1000.0]
    df = build_features(_lane_frame(rates), validate=True).sort_values("date").reset_index(drop=True)

    # For every row before the spike, no engineered feature may reflect 1000.0.
    feat_cols = engineered_feature_columns(df)
    early = df.iloc[:9]
    for col in feat_cols:
        vals = pd.to_numeric(early[col], errors="coerce").dropna()
        _assert((vals.abs() < 500).all(),
                f"future spike leaked into '{col}' on pre-spike rows: {vals.tolist()}")


def test_rolling_mean_excludes_current_row():
    # Increasing series: rolling mean (shifted) at row i must be < current value.
    rates = [float(i) for i in range(1, 21)]
    df = build_features(_lane_frame(rates), roll_windows=[3]).sort_values("date").reset_index(drop=True)
    col = "freight_rate_rollmean_3"
    _assert(col in df.columns, "rolling mean column missing")
    later = df.iloc[3:]
    _assert((later[col] < later["freight_rate"]).all(),
            "rolling mean must exclude current row (be below it on rising series)")
    _assert(pd.isna(df.loc[0, col]), "first rolling mean must be NaN (no past)")


def test_lag_is_strictly_past():
    rates = [5.0, 6.0, 7.0, 8.0]
    df = add_lags(_lane_frame(rates).sort_values("date"), "freight_rate", [1]).reset_index(drop=True)
    _assert(pd.isna(df.loc[0, "freight_rate_lag_1"]), "first lag must be NaN")
    _assert(df.loc[1, "freight_rate_lag_1"] == 5.0, "lag_1 must be the previous value")
    _assert(df.loc[3, "freight_rate_lag_1"] == 7.0, "lag_1 wrong")


def test_lag_zero_rejected():
    try:
        add_lags(_lane_frame([1.0, 2.0]), "freight_rate", [0])
        raise AssertionError("lag 0 should be rejected (leakage)")
    except ValueError:
        pass


def test_pct_change_uses_prior_values_only():
    # 100,110,121 (+10% each). pct change should reference past, not current.
    df = add_pct_change(_lane_frame([100.0, 110.0, 121.0]).sort_values("date"),
                        "freight_rate", [1]).reset_index(drop=True)
    col = "freight_rate_pctchg_1"
    _assert(pd.isna(df.loc[0, col]) and pd.isna(df.loc[1, col]),
            "first two pct-change values need two past points -> NaN")
    # row 2: (prev=110 - prev_prev=100)/100 = 0.10
    _assert(abs(df.loc[2, col] - 0.10) < 1e-9, f"pct change wrong: {df.loc[2, col]}")


def test_future_target_columns_not_in_features():
    df = _lane_frame([10.0] * 12)
    df["future_7d_freight"] = [99.0] * 12  # a target column present in the frame
    out = build_features(df)
    feat_cols = set(engineered_feature_columns(out))
    _assert("future_7d_freight" not in feat_cols, "future target must be excluded from features")
    _assert("freight_rate" not in feat_cols, "current label must be excluded from features")


def test_building_features_from_target_rejected():
    df = _lane_frame([10.0] * 5)
    df["future_7d_freight"] = 1.0
    try:
        build_features(df, value_column="future_7d_freight")
        raise AssertionError("building features from a future target must raise")
    except ValueError:
        pass


# --- temporal ordering validation ---
def test_unsorted_lane_raises():
    df = _lane_frame([1.0, 2.0, 3.0])
    df = df.iloc[::-1]  # reverse -> descending dates
    try:
        validate_temporal_order(df)
        raise AssertionError("unsorted lane should raise TimeOrderError")
    except TimeOrderError:
        pass


def test_duplicate_timestamp_raises():
    df = _lane_frame([1.0, 2.0])
    df.loc[1, "date"] = df.loc[0, "date"]  # duplicate timestamp in the lane
    try:
        validate_temporal_order(df)
        raise AssertionError("duplicate timestamp should raise TimeOrderError")
    except TimeOrderError:
        pass


def test_pipeline_sorts_then_validates_ok():
    # Shuffle input; pipeline should sort per lane and not raise.
    df = _lane_frame([float(i) for i in range(10)]).sample(frac=1, random_state=1)
    out = build_features(df)
    # After processing, each lane is sorted ascending.
    validate_temporal_order(out)  # should not raise


def test_multi_lane_isolation():
    # Two lanes; a spike in lane B must not affect lane A features.
    a = _lane_frame([10.0] * 10, origin="Australia", dest="Paradip", vtype="capesize")
    b = _lane_frame([10.0] * 9 + [1000.0], origin="Indonesia", dest="Visakhapatnam", vtype="panamax")
    out = build_features(pd.concat([a, b], ignore_index=True))
    lane_a = out[(out["origin"] == "Australia")]
    feat_cols = engineered_feature_columns(out)
    for col in feat_cols:
        vals = pd.to_numeric(lane_a[col], errors="coerce").dropna()
        _assert((vals.abs() < 500).all(), f"lane B spike leaked into lane A '{col}'")


def _run_all():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for t in tests:
        t()
        print(f"  ok: {t.__name__}")
    print(f"{len(tests)}/{len(tests)} leakage tests passed")


if __name__ == "__main__":
    _run_all()

"""Tests for forecast uncertainty: response structure + principled behaviour.

Run from ml/ with the ml venv:
    .venv/bin/python -m models.test_uncertainty
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

from models.uncertainty import (
    CONFIDENCE_SCALE_K,
    build_forecast_result,
    confidence_from_interval,
    relative_width,
    ForecastResult,
)
from datasets.builder import build_dataset
from models.freight_gbm import (
    load_bundle,
    predict_with_uncertainty,
    run_and_store,
    train_and_evaluate,
    _numeric_feature_columns,
    HORIZONS,
)
from features.pipeline import build_features


def _assert(cond, msg):
    if not cond:
        raise AssertionError(msg)


# ---- confidence formula (unit) ----
def test_zero_width_interval_is_max_confidence():
    c = confidence_from_interval(24.8, 24.8, 24.8)
    _assert(abs(c - 1.0) < 1e-9, "zero-width interval must give confidence 1.0")


def test_wider_interval_gives_lower_confidence():
    tight = confidence_from_interval(24.8, 24.0, 25.6)   # width 1.6
    wide = confidence_from_interval(24.8, 20.0, 29.6)    # width 9.6
    _assert(wide < tight, "wider interval must lower confidence")
    _assert(0.0 < wide < tight <= 1.0, "confidence must be in (0,1] and monotonic")


def test_confidence_matches_documented_formula():
    pred, lo, hi = 24.8, 23.1, 26.7
    rw = relative_width(pred, lo, hi)          # (26.7-23.1)/24.8
    expected = 1.0 / (1.0 + rw / CONFIDENCE_SCALE_K)
    got = confidence_from_interval(pred, lo, hi)
    _assert(abs(got - expected) < 1e-12, "confidence must equal the documented formula")


def test_confidence_half_at_k_relative_width():
    # By construction, relative width == k => confidence == 0.5.
    pred = 100.0
    width = CONFIDENCE_SCALE_K * pred          # relative width == k
    lo, hi = pred - width / 2, pred + width / 2
    _assert(abs(confidence_from_interval(pred, lo, hi) - 0.5) < 1e-9,
            "confidence must be 0.5 when relative width == k")


# ---- ForecastResult structure + ordering ----
def test_result_structure_and_ordering():
    r = build_forecast_result(24.8, 23.1, 26.7, lower_quantile=0.1, upper_quantile=0.9)
    _assert(isinstance(r, ForecastResult), "must return ForecastResult")
    d = r.to_dict()
    for field in ("predicted", "lower", "upper", "confidence",
                  "lower_quantile", "upper_quantile", "confidence_scale_k"):
        _assert(field in d, f"response missing '{field}'")
    _assert(d["lower"] <= d["predicted"] <= d["upper"], "must satisfy lower<=pred<=upper")
    _assert(0.0 < d["confidence"] <= 1.0, "confidence must be in (0,1]")


def test_crossed_quantiles_repaired():
    # upper < lower on input -> repaired so ordering holds.
    r = build_forecast_result(10.0, 12.0, 8.0, lower_quantile=0.1, upper_quantile=0.9)
    _assert(r.lower <= r.predicted <= r.upper, "crossed quantiles must be repaired")


def test_point_outside_interval_clamped():
    # predicted above the upper bound -> clamped into the interval.
    r = build_forecast_result(100.0, 20.0, 25.0, lower_quantile=0.1, upper_quantile=0.9)
    _assert(r.lower <= r.predicted <= r.upper, "point estimate must be clamped inside")


# ---- integration: predict_with_uncertainty on a trained bundle ----
def _synthetic(days=140):
    rng = np.random.default_rng(5)
    dates = pd.date_range("2026-01-01", periods=days, freq="D")
    rows = []
    for origin, dest, vtype in [("Australia", "Paradip", "capesize"),
                                ("Indonesia", "Visakhapatnam", "panamax")]:
        lvl = 20.0
        for d in dates:
            lvl += rng.normal(0.01, 0.3)
            rows.append({"date": d, "origin": origin, "destination": dest,
                         "vessel_type": vtype, "freight_rate": round(lvl, 3)})
    return build_dataset(pd.DataFrame(rows))


def test_predict_with_uncertainty_structure():
    df = _synthetic()
    models, _ = train_and_evaluate(df)
    h = next(iter(models))  # a horizon that was fitted
    feats = build_features(df)
    fl = _numeric_feature_columns(feats)
    X = feats[fl].astype("float64").tail(5)
    results = predict_with_uncertainty(models[h], X)
    _assert(len(results) == 5, "one result per row")
    for r in results:
        d = r.to_dict()
        _assert(d["lower"] <= d["predicted"] <= d["upper"], "ordering must hold")
        _assert(0.0 < d["confidence"] <= 1.0, "confidence in (0,1]")
        _assert(d["lower_quantile"] == 0.1 and d["upper_quantile"] == 0.9,
                "quantile provenance recorded")


def test_report_records_uncertainty_method():
    df = _synthetic()
    with tempfile.TemporaryDirectory() as tmp:
        out = run_and_store(df, artifact_dir=Path(tmp))
        rep = json.loads((out / "training_report.json").read_text())
        _assert("uncertainty" in rep, "report must document uncertainty")
        u = rep["uncertainty"]
        _assert(u["method"] == "quantile_regression", "method must be quantile regression")
        _assert("formula" in u["confidence"], "confidence formula must be documented")
        _assert(u["lower_quantile"] == 0.1 and u["upper_quantile"] == 0.9, "quantiles recorded")


def _run_all():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for t in tests:
        t()
        print(f"  ok: {t.__name__}")
    print(f"{len(tests)}/{len(tests)} uncertainty tests passed")


if __name__ == "__main__":
    _run_all()

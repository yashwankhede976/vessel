"""Tests for the gradient-boosted freight model + time-based split.

Run from ml/ with the ml venv:
    .venv/bin/python -m models.test_freight_gbm
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

from datasets.builder import build_dataset
from models.splits import time_split
from models.freight_gbm import (
    MODEL_NAME,
    run_and_store,
    train_and_evaluate,
)


def _assert(cond, msg):
    if not cond:
        raise AssertionError(msg)


def _synthetic_freight(days=140, lanes=None):
    """Longer, mildly-trending series so all horizons have test rows."""
    rng = np.random.default_rng(3)
    lanes = lanes or [("Australia", "Paradip", "capesize"),
                      ("Indonesia", "Visakhapatnam", "panamax")]
    dates = pd.date_range("2026-01-01", periods=days, freq="D")
    rows = []
    for origin, dest, vtype in lanes:
        level = 15.0
        for d in dates:
            level += rng.normal(0.02, 0.25)  # slight drift + noise
            rows.append({"date": d, "origin": origin, "destination": dest,
                         "vessel_type": vtype, "freight_rate": round(level, 3)})
    return build_dataset(pd.DataFrame(rows))


# --- time split ---
def test_time_split_is_chronological_and_disjoint():
    df = _synthetic_freight()
    sp = time_split(df, train_frac=0.6, val_frac=0.2)
    _assert(sp.train["date"].max() <= sp.train_end, "train past boundary")
    _assert(sp.val["date"].min() > sp.train_end, "val must start after train")
    _assert(sp.test["date"].min() > sp.val_end, "test must start after val")
    # No test date precedes any train date (global temporal order).
    _assert(sp.test["date"].min() > sp.train["date"].max(),
            "test dates must be after all train dates")
    total = len(sp.train) + len(sp.val) + len(sp.test)
    _assert(total == len(df), "split must partition all rows")


def test_split_fractions_validated():
    df = _synthetic_freight(days=40)
    try:
        time_split(df, train_frac=0.9, val_frac=0.2)  # sums > 1
        raise AssertionError("invalid fractions should raise")
    except ValueError:
        pass


# --- training + evaluation ---
def test_trains_all_horizons_and_reports():
    df = _synthetic_freight()
    models, report = train_and_evaluate(df, dataset_version="test-v1")
    # Feature list is non-empty and excludes targets/grain.
    _assert(len(report.feature_list) > 0, "must have features")
    for bad in ("freight_rate", "future_7d_freight", "date", "origin"):
        _assert(bad not in report.feature_list, f"{bad} must not be a feature")
    # Each horizon reported; where test rows exist, a fitted model exists.
    for h in (7, 14, 30):
        _assert(str(h) in report.horizons, f"horizon {h} missing from report")
    _assert(len(models) >= 1, "at least one horizon model should be fitted")
    # Report carries required provenance.
    _assert(report.dataset_version == "test-v1", "dataset version not recorded")
    _assert(report.trained_at, "training timestamp missing")
    _assert(report.model_name == MODEL_NAME, "model name missing")


def test_report_contains_baseline_comparison():
    df = _synthetic_freight()
    _, report = train_and_evaluate(df)
    # At least one horizon should have both model + baseline metrics.
    has_compare = any(
        block.get("metrics", {}).get("mae") is not None
        and block.get("baseline_metrics", {}).get("mae") is not None
        for block in report.horizons.values()
    )
    _assert(has_compare, "expected model-vs-baseline metrics for some horizon")


# --- artifact saving ---
def test_artifacts_saved_with_required_fields():
    df = _synthetic_freight()
    with tempfile.TemporaryDirectory() as d:
        out = run_and_store(df, dataset_version="art-v2", artifact_dir=Path(d))
        # Report file with all required fields.
        report = json.loads((out / "training_report.json").read_text())
        for field in ("model_name", "model_version", "dataset_version",
                      "feature_list", "trained_at", "horizons", "xgb_params", "split"):
            _assert(field in report, f"report missing '{field}'")
        _assert(report["dataset_version"] == "art-v2", "dataset version wrong")
        # Standalone feature list.
        _assert((out / "feature_list.json").exists(), "feature_list.json missing")
        # At least one model artifact saved.
        models = list(out.glob(f"{MODEL_NAME}_h*.joblib"))
        _assert(len(models) >= 1, "no model artifacts saved")


def test_saved_model_can_be_loaded_and_predict():
    import joblib
    df = _synthetic_freight()
    with tempfile.TemporaryDirectory() as d:
        out = run_and_store(df, artifact_dir=Path(d))
        model_files = list(out.glob(f"{MODEL_NAME}_h*.joblib"))
        feats = json.loads((out / "feature_list.json").read_text())
        # Each artifact is now a bundle: {"point","lower","upper"}.
        bundle = joblib.load(model_files[0])
        _assert(set(bundle.keys()) == {"point", "lower", "upper"},
                "artifact must be a point+quantile bundle")
        X = pd.DataFrame([[0.0] * len(feats)], columns=feats)
        pred = bundle["point"].predict(X)
        _assert(pred.shape == (1,), "loaded point model must predict")


def _run_all():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for t in tests:
        t()
        print(f"  ok: {t.__name__}")
    print(f"{len(tests)}/{len(tests)} gbm tests passed")


if __name__ == "__main__":
    _run_all()

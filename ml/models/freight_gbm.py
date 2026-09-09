"""First production-oriented freight forecasting model (gradient-boosted).

One XGBoost regressor per horizon (7/14/30 days) trained on the VALIDATED
feature-engineering pipeline (ml/features), evaluated with time-based
train/validation/test splits, and compared against the deterministic baseline
(ml/models/baseline_freight). A versioned artifact bundle is saved:

    model(s), feature list, metrics, training timestamp, dataset version.

Not exposed to the React frontend (backend/ML only). No deep learning — XGBoost
is a gradient-boosted tree ensemble. Pure pandas/numpy/xgboost; no Django.
"""
from __future__ import annotations

import json
import sys
import warnings
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

warnings.filterwarnings(
    "ignore", category=FutureWarning, message=".*ChainedAssignmentError.*"
)
try:
    warnings.filterwarnings("ignore", category=pd.errors.SettingWithCopyWarning)
except AttributeError:  # pragma: no cover
    pass

import joblib
from xgboost import XGBRegressor

# ml/ on path so sibling packages import cleanly under `python -m`.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from features.pipeline import build_features, engineered_feature_columns  # noqa: E402
from models.baseline_freight import HORIZONS, evaluate_baselines  # noqa: E402
from models.metrics import evaluate_metrics  # noqa: E402
from models.splits import time_split  # noqa: E402
from models.uncertainty import (  # noqa: E402
    CONFIDENCE_SCALE_K,
    build_forecast_result,
    ForecastResult,
)

MODEL_NAME = "freight_gbm_xgboost"
MODEL_VERSION = "0.2.0"  # adds quantile-based uncertainty
ARTIFACT_DIR = Path(__file__).resolve().parent / "artifacts"

# Prediction-interval quantiles (10th / 90th percentile => ~80% interval).
LOWER_QUANTILE = 0.10
UPPER_QUANTILE = 0.90

DEFAULT_XGB_PARAMS = dict(
    n_estimators=300,
    max_depth=4,
    learning_rate=0.05,
    subsample=0.9,
    colsample_bytree=0.9,
    reg_lambda=1.0,
    random_state=42,
    n_jobs=2,
)


@dataclass
class HorizonModel:
    horizon_days: int
    target_column: str
    metrics: dict            # test-set metrics for this horizon
    baseline_metrics: dict   # baseline (naive) test metrics for comparison
    improvement_pct: dict    # % improvement vs baseline (MAE/RMSE)


@dataclass
class TrainingReport:
    model_name: str
    model_version: str
    dataset_version: str
    feature_list: list[str]
    xgb_params: dict
    split: dict              # train/val/test row counts + boundary dates
    horizons: dict           # {"7": HorizonModel-as-dict, ...}
    uncertainty: dict        # method + quantile levels + confidence formula
    trained_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


def _numeric_feature_columns(feat_df: pd.DataFrame) -> list[str]:
    """Model-input columns: engineered features restricted to numeric dtypes.

    engineered_feature_columns already excludes grain, freight_rate, and all
    future_* targets (leakage guard); we further keep only numeric columns
    (drop the raw `date` and any category passthroughs XGBoost can't take).
    """
    candidate = engineered_feature_columns(feat_df)
    numeric = []
    for c in candidate:
        if c in ("date",):
            continue
        if pd.api.types.is_numeric_dtype(feat_df[c]):
            numeric.append(c)
    return numeric


def _pct_improvement(baseline: Optional[float], model: Optional[float]) -> Optional[float]:
    if baseline in (None, 0) or model is None:
        return None
    return round((baseline - model) / baseline * 100.0, 2)


def train_and_evaluate(
    df: pd.DataFrame,
    *,
    dataset_version: str = "synthetic-demo",
    xgb_params: Optional[dict] = None,
    train_frac: float = 0.6,
    val_frac: float = 0.2,
) -> tuple[dict, TrainingReport]:
    """Train one GBM per horizon, evaluate on the time-based test split.

    Returns (models_by_horizon, report). `models_by_horizon` maps horizon (int)
    -> fitted XGBRegressor.
    """
    params = {**DEFAULT_XGB_PARAMS, **(xgb_params or {})}

    # 1) Engineer validated (leakage-safe) features.
    feats = build_features(df)

    # 2) Time-based split (chronological; no shuffling).
    split = time_split(feats, train_frac=train_frac, val_frac=val_frac)

    feature_list = _numeric_feature_columns(feats)
    if not feature_list:
        raise ValueError("No numeric features available to train on.")

    # Baseline comparison (evaluated on the SAME test rows).
    baseline_results = evaluate_baselines(split.test)
    naive = next((r for r in baseline_results if r.model == "naive_previous"), None)

    # Each horizon holds a bundle: point + lower-quantile + upper-quantile models.
    models_by_horizon: dict[int, dict[str, XGBRegressor]] = {}
    horizons_report: dict[str, dict] = {}

    for h, target_col in HORIZONS.items():
        # Rows usable for this horizon = feature-complete-enough + known target.
        def _xy(frame: pd.DataFrame):
            sub = frame.dropna(subset=[target_col])
            X = sub[feature_list].astype("float64")
            y = sub[target_col].astype("float64")
            return sub, X, y

        _, X_train, y_train = _xy(split.train)
        _, X_val, y_val = _xy(split.val)
        test_sub, X_test, y_test = _xy(split.test)

        if len(X_train) == 0 or len(X_test) == 0:
            # Not enough data for this horizon on this dataset — record + skip.
            horizons_report[str(h)] = asdict(
                HorizonModel(h, target_col, {"n": 0}, {}, {})
            )
            continue

        # Point (mean) model.
        model = XGBRegressor(**params)
        eval_set = [(X_val, y_val)] if len(X_val) else None
        model.fit(X_train, y_train, eval_set=eval_set, verbose=False)

        # Lower/upper QUANTILE models (data-derived prediction interval).
        q_params = {**params}
        q_params.pop("objective", None)
        lower_model = XGBRegressor(
            objective="reg:quantileerror", quantile_alpha=LOWER_QUANTILE, **q_params
        )
        upper_model = XGBRegressor(
            objective="reg:quantileerror", quantile_alpha=UPPER_QUANTILE, **q_params
        )
        lower_model.fit(X_train, y_train, verbose=False)
        upper_model.fit(X_train, y_train, verbose=False)

        models_by_horizon[h] = {
            "point": model,
            "lower": lower_model,
            "upper": upper_model,
        }

        preds = model.predict(X_test)
        metrics = evaluate_metrics(y_test.to_numpy(), preds)

        # Interval coverage on the test set: fraction of actuals inside [lo, hi].
        # This is a real, measured property of the interval (not asserted).
        if len(X_test):
            lo_test = lower_model.predict(X_test)
            hi_test = upper_model.predict(X_test)
            lo_arr = np.minimum(lo_test, hi_test)
            hi_arr = np.maximum(lo_test, hi_test)
            inside = (y_test.to_numpy() >= lo_arr) & (y_test.to_numpy() <= hi_arr)
            metrics = {**metrics, "interval_coverage": float(np.mean(inside))}

        base_metrics = (
            naive.horizons.get(str(h), {}) if naive is not None else {}
        )
        improvement = {
            "mae": _pct_improvement(base_metrics.get("mae"), metrics.get("mae")),
            "rmse": _pct_improvement(base_metrics.get("rmse"), metrics.get("rmse")),
        }

        horizons_report[str(h)] = asdict(
            HorizonModel(
                horizon_days=h,
                target_column=target_col,
                metrics=metrics,
                baseline_metrics=base_metrics,
                improvement_pct=improvement,
            )
        )

    report = TrainingReport(
        model_name=MODEL_NAME,
        model_version=MODEL_VERSION,
        dataset_version=dataset_version,
        feature_list=feature_list,
        xgb_params=params,
        split={
            "train_rows": int(len(split.train)),
            "val_rows": int(len(split.val)),
            "test_rows": int(len(split.test)),
            "train_end": split.train_end.isoformat(),
            "val_end": split.val_end.isoformat(),
        },
        horizons=horizons_report,
        uncertainty={
            "method": "quantile_regression",
            "detail": "Separate XGBoost reg:quantileerror models predict the "
            "lower and upper quantiles; the interval is [lower_q, upper_q].",
            "lower_quantile": LOWER_QUANTILE,
            "upper_quantile": UPPER_QUANTILE,
            "nominal_interval_pct": round((UPPER_QUANTILE - LOWER_QUANTILE) * 100, 1),
            "confidence": {
                "formula": "1 / (1 + relative_width / k)",
                "relative_width": "(upper - lower) / max(|predicted|, eps)",
                "k": CONFIDENCE_SCALE_K,
                "note": "Deterministic function of the interval width; no "
                "hand-picked confidence values.",
            },
        },
    )
    return models_by_horizon, report


def save_artifacts(
    models_by_horizon: dict,
    report: TrainingReport,
    *,
    artifact_dir: Path = ARTIFACT_DIR,
) -> Path:
    """Persist the model bundle: per-horizon models (point + quantiles), feature
    list, metrics, uncertainty method, training timestamp, dataset version."""
    artifact_dir.mkdir(parents=True, exist_ok=True)

    # Per-horizon fitted model bundles (point + lower + upper quantile models).
    for h, bundle in models_by_horizon.items():
        joblib.dump(bundle, artifact_dir / f"{MODEL_NAME}_h{h}.joblib")

    # Feature list (also embedded in the report, kept standalone for loaders).
    (artifact_dir / "feature_list.json").write_text(
        json.dumps(report.feature_list, indent=2)
    )

    # Full report: metrics, timestamp, dataset version, params, split.
    (artifact_dir / "training_report.json").write_text(
        json.dumps(asdict(report), indent=2)
    )
    return artifact_dir


def predict_with_uncertainty(
    bundle: dict,
    X: pd.DataFrame,
    *,
    lower_quantile: float = LOWER_QUANTILE,
    upper_quantile: float = UPPER_QUANTILE,
) -> list[ForecastResult]:
    """Predict point + interval + confidence for each row of X.

    `bundle` is a per-horizon dict {"point","lower","upper"} of fitted models.
    Returns one ForecastResult per input row with the structured response:
    predicted, lower, upper, confidence (+ the quantile provenance).
    """
    point = bundle["point"].predict(X)
    lower = bundle["lower"].predict(X)
    upper = bundle["upper"].predict(X)
    results: list[ForecastResult] = []
    for i in range(len(X)):
        results.append(
            build_forecast_result(
                predicted=float(point[i]),
                lower=float(lower[i]),
                upper=float(upper[i]),
                lower_quantile=lower_quantile,
                upper_quantile=upper_quantile,
            )
        )
    return results


def load_bundle(horizon: int, *, artifact_dir: Path = ARTIFACT_DIR) -> dict:
    """Load a saved per-horizon model bundle from disk."""
    return joblib.load(artifact_dir / f"{MODEL_NAME}_h{horizon}.joblib")


def run_and_store(
    df: Optional[pd.DataFrame] = None,
    *,
    dataset_version: str = "synthetic-demo",
    artifact_dir: Path = ARTIFACT_DIR,
) -> Path:
    """Train + evaluate + save. If `df` is None, uses the synthetic demo dataset
    (validation only — no real data)."""
    if df is None:
        from datasets.example import build_demo

        df = build_demo()
    models_by_horizon, report = train_and_evaluate(df, dataset_version=dataset_version)
    return save_artifacts(models_by_horizon, report, artifact_dir=artifact_dir)


if __name__ == "__main__":  # pragma: no cover
    out = run_and_store()
    report = json.loads((out / "training_report.json").read_text())
    print(f"Saved artifacts to {out}")
    print(f"Model: {report['model_name']} v{report['model_version']} "
          f"dataset={report['dataset_version']} features={len(report['feature_list'])}")
    for h, block in report["horizons"].items():
        m = block.get("metrics", {})
        imp = block.get("improvement_pct", {})
        if m.get("mae") is not None:
            print(f"  {h}d: MAE={m['mae']:.3f} RMSE={m['rmse']:.3f} "
                  f"MAPE={m.get('mape_pct')}  vs baseline MAE improvement={imp.get('mae')}%")

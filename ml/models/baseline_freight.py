"""Baseline freight forecasting benchmark.

Two deterministic, non-deep-learning benchmarks that advanced models must beat:

- **NaivePrevious**: forecast every future horizon as the last known freight
  rate on `date` (a random-walk / persistence forecast).
- **MovingAverage(w)**: forecast every horizon as the trailing mean of the last
  `w` PAST rates within the lane (shift-then-roll, so today's rate is excluded).

Forecast horizons: 7, 14, 30 days. Ground truth is the dataset's realized
`future_7d/14d/30d_freight` columns. Evaluation uses MAE, RMSE, and MAPE, both
per lane and overall. Results are stored as JSON.

Pure pandas/numpy. No deep learning. No Django. See docs/FREIGHT_DATASET_SCHEMA.md.
"""
from __future__ import annotations

import json
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

from .metrics import evaluate_metrics

LANE = ["origin", "destination", "vessel_type"]
VALUE_COLUMN = "freight_rate"

# Horizon (days) -> the dataset target column holding the realized future rate.
HORIZONS = {
    7: "future_7d_freight",
    14: "future_14d_freight",
    30: "future_30d_freight",
}

RESULTS_DIR = Path(__file__).resolve().parent / "results"
RESULTS_FILE = RESULTS_DIR / "baseline_freight_results.json"


# ---------------------------------------------------------------------------
# Forecasters (return a per-row point forecast used for ALL horizons)
# ---------------------------------------------------------------------------
def naive_previous_forecast(df: pd.DataFrame) -> pd.Series:
    """Persistence: the forecast for any future horizon is today's rate.

    `freight_rate` is the rate known ON `date`, so using it as the forecast for
    a future date is a valid (leakage-free) persistence baseline.
    """
    return pd.to_numeric(df[VALUE_COLUMN], errors="coerce")


def moving_average_forecast(df: pd.DataFrame, window: int = 7) -> pd.Series:
    """Trailing moving average of the last `window` PAST rates within the lane.

    The value series is shifted by 1 before rolling so the current row's rate is
    excluded — the forecast uses only rates strictly before `date`. Falls back
    to the shifted (previous) value where a full window is not yet available
    (min_periods=1).
    """
    work = df[LANE + ["date", VALUE_COLUMN]].copy()
    work["date"] = pd.to_datetime(work["date"])
    work = work.sort_values(LANE + ["date"])
    shifted = work.groupby(LANE, observed=True)[VALUE_COLUMN].shift(1)
    grp = shifted.groupby([work[c] for c in LANE], observed=True)
    ma = grp.transform(lambda s: s.rolling(window, min_periods=1).mean())
    # Return aligned to the original df index.
    return ma.reindex(df.index)


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------
@dataclass
class BaselineResult:
    model: str
    params: dict
    horizons: dict            # {"7": {overall metrics}, ...}
    per_lane: dict            # {"7": {lane_str: metrics}, ...}
    n_rows: int
    generated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


def _forecast_for_model(df: pd.DataFrame, model: str, ma_window: int) -> pd.Series:
    if model == "naive_previous":
        return naive_previous_forecast(df)
    if model == "moving_average":
        return moving_average_forecast(df, window=ma_window)
    raise ValueError(f"Unknown baseline model '{model}'.")


def evaluate_baselines(
    df: pd.DataFrame,
    *,
    ma_window: int = 7,
) -> list[BaselineResult]:
    """Evaluate each baseline across all horizons, overall and per lane.

    For each horizon h, the point forecast is compared to the realized
    `future_{h}d_freight`. Rows with a missing target are dropped from that
    horizon's metrics (they have no ground truth yet).
    """
    if df.empty:
        return []

    work = df.copy()
    work["date"] = pd.to_datetime(work["date"])
    work = work.sort_values(LANE + ["date"]).reset_index(drop=True)

    results: list[BaselineResult] = []
    models = [("naive_previous", {}), ("moving_average", {"window": ma_window})]

    for model, params in models:
        forecast = _forecast_for_model(work, model, ma_window)

        horizons_metrics: dict[str, dict] = {}
        per_lane_metrics: dict[str, dict] = {}

        for h, target_col in HORIZONS.items():
            if target_col not in work.columns:
                continue
            actual = pd.to_numeric(work[target_col], errors="coerce")
            # Overall metrics (NaN pairs dropped inside evaluate_metrics).
            horizons_metrics[str(h)] = evaluate_metrics(actual, forecast)

            # Per-lane metrics.
            lane_block: dict[str, dict] = {}
            for keys, idx in work.groupby(LANE, observed=True).groups.items():
                lane_actual = actual.loc[idx]
                lane_fc = forecast.loc[idx]
                lane_key = " | ".join(str(k) for k in keys)
                lane_block[lane_key] = evaluate_metrics(lane_actual, lane_fc)
            per_lane_metrics[str(h)] = lane_block

        results.append(
            BaselineResult(
                model=model,
                params=params,
                horizons=horizons_metrics,
                per_lane=per_lane_metrics,
                n_rows=int(len(work)),
            )
        )

    return results


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------
def store_results(results: list[BaselineResult], path: Path = RESULTS_FILE) -> Path:
    """Write evaluation results to JSON (creating the directory if needed)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "benchmark": "baseline_freight",
        "note": "Deterministic benchmarks (naive previous, moving average). "
        "Advanced models are compared against these.",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "results": [asdict(r) for r in results],
    }
    path.write_text(json.dumps(payload, indent=2))
    return path


def run_and_store(
    df: Optional[pd.DataFrame] = None,
    *,
    ma_window: int = 7,
    path: Path = RESULTS_FILE,
) -> Path:
    """Evaluate baselines and persist results. If `df` is None, build the
    synthetic demo dataset (validation only — trains nothing)."""
    if df is None:
        # Local import to avoid a hard dependency when a df is supplied.
        import sys

        sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
        from datasets.example import build_demo

        df = build_demo()
    results = evaluate_baselines(df, ma_window=ma_window)
    return store_results(results, path)


if __name__ == "__main__":  # pragma: no cover
    out = run_and_store()
    print(f"Wrote baseline results to {out}")
    print(out.read_text()[:800])

"""Export per-lane freight forecasts as a JSON artifact for the backend bridge.

This is the ML-side half of the ML -> Django FreightForecast bridge. It runs in
the ML virtualenv (Python 3.13; the scientific stack segfaults on 3.14), trains
the XGBoost horizon models on a dataset, then produces the LATEST per-lane
forecast for each horizon (7/14/30 days) by predicting from the most recent
feature-complete row of each lane. The result is written as a plain JSON
artifact that the backend management command reads and upserts into the
`operations.FreightForecast` table.

Keeping this on the ML side preserves the architecture boundary: Django never
imports the ML package or the scientific stack; it only reads the JSON artifact.

Data provenance: with the synthetic demo dataset every forecast is SYNTHETIC +
FORECAST (model output on generated inputs). The artifact records `dataset_kind`
so the backend can label the stored rows accordingly.

Usage (from repo root, ML venv):
    python -m ml.models.export_forecasts                 # synthetic demo
    python -m ml.models.export_forecasts --out /tmp/f.json
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from features.pipeline import build_features  # noqa: E402
from models.baseline_freight import HORIZONS, LANE  # noqa: E402
from models.freight_gbm import (  # noqa: E402
    MODEL_NAME,
    MODEL_VERSION,
    _numeric_feature_columns,
    predict_with_uncertainty,
    train_and_evaluate,
)

ARTIFACT_DIR = Path(__file__).resolve().parent / "results"
DEFAULT_OUT = ARTIFACT_DIR / "freight_forecasts.json"


def export_forecasts(
    df: pd.DataFrame,
    *,
    dataset_version: str = "synthetic-demo",
    dataset_kind: str = "SYNTHETIC",
) -> dict:
    """Train the horizon models and produce the latest per-lane forecast for each
    horizon. Returns the artifact dict (also suitable for JSON serialization)."""
    models_by_horizon, report = train_and_evaluate(df, dataset_version=dataset_version)

    feats = build_features(df)
    feats["date"] = pd.to_datetime(feats["date"])
    feature_list = _numeric_feature_columns(feats)

    generated_at = datetime.now(timezone.utc).isoformat()
    # Latest observed date per lane -> the "as-of" date the forecast is made from.
    latest_idx = feats.sort_values("date").groupby(LANE, observed=True).tail(1).index
    latest_rows = feats.loc[latest_idx]

    forecasts = []
    for _, row in latest_rows.iterrows():
        as_of = row["date"]
        lane = {c: row[c] for c in LANE}
        X = pd.DataFrame([row[feature_list].astype("float64")])
        for h, _target in HORIZONS.items():
            bundle = models_by_horizon.get(h)
            if bundle is None:
                continue
            fr = predict_with_uncertainty(bundle, X)[0]
            target_date = (as_of + pd.Timedelta(days=h)).date().isoformat()
            forecasts.append(
                {
                    **lane,
                    "as_of_date": as_of.date().isoformat(),
                    "horizon_days": h,
                    "target_date": target_date,
                    "predicted_rate_per_tonne": fr.predicted,
                    "lower_bound": fr.lower,
                    "upper_bound": fr.upper,
                    "confidence": fr.confidence,
                }
            )

    return {
        "model_name": MODEL_NAME,
        "model_version": MODEL_VERSION,
        "dataset_version": dataset_version,
        "dataset_kind": dataset_kind,            # SYNTHETIC | REAL
        "data_kind": "FORECAST",                 # these are model FORECASTS
        "generated_at": generated_at,
        "trained_at": report.trained_at,
        "feature_count": len(feature_list),
        "horizons": list(HORIZONS.keys()),
        "metrics": report.horizons,              # per-horizon test metrics + baseline
        "forecasts": forecasts,
    }


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description="Export freight forecasts to JSON.")
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="Output JSON path.")
    parser.add_argument(
        "--dataset-version", default="synthetic-demo", help="Dataset version label."
    )
    args = parser.parse_args(argv)

    from datasets.example import build_demo

    artifact = export_forecasts(build_demo(), dataset_version=args.dataset_version)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(artifact, indent=2))
    print(f"Wrote {len(artifact['forecasts'])} forecasts to {out}")


if __name__ == "__main__":  # pragma: no cover
    main()

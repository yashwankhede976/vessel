# Model Evaluation

**Project:** Vessel — Intelligent Freight Forecasting & Vessel Chartering platform
**Document type:** Model / Methodology note
**Status:** v1.0

How the freight models are evaluated and compared against baselines. Implemented
in `ml/models/metrics.py`, `ml/models/baseline_freight.py`,
`ml/models/splits.py`, and the reporting in `ml/models/freight_gbm.py`.

---

## 1. Split

`time_split(df, train_frac=0.6, val_frac=0.2)` splits **chronologically** by
global date quantiles into train / val / test. No shuffling; the test set is
strictly later than train, so metrics reflect genuine forecasting, not
interpolation.

## 2. Metrics

`evaluate_metrics(y_true, y_pred)` returns `{n, mae, rmse, mape_pct}`:
- **MAE** — mean absolute error.
- **RMSE** — root mean squared error.
- **MAPE** — mean absolute percentage error (guards against zero denominators).

For the interval, the GBM report also measures **`interval_coverage`**: the
fraction of test actuals that fell inside `[lower, upper]` — a real, measured
property of the prediction interval, not an assumed one.

## 3. Baselines

Two deterministic benchmarks the advanced model must beat
(`ml/models/baseline_freight.py`):
- **naive_previous** — persistence (forecast = last known rate).
- **moving_average(w=7)** — trailing mean of the last 7 past rates (shift-then-roll).

Baselines are evaluated on the **same test rows**, per horizon and per lane.

## 4. Advanced vs baseline

`train_and_evaluate` records per horizon: the GBM `metrics`, the naive
`baseline_metrics`, and `improvement_pct` (% MAE/RMSE improvement vs naive). This
is the advanced-vs-baseline comparison required by the spec.

## 5. Measured results (SYNTHETIC demo)

Run: `python -m ml.models.export_forecasts` on the 60-row / 2-lane synthetic demo.
These numbers are from **SYNTHETIC** data and are for pipeline validation only —
they are **not** indicative of real-market accuracy.

| Horizon | GBM MAE | Baseline (naive) MAE | Improvement | Notes |
|---|---|---|---|---|
| 7d | ~1.15 | ~0.42 | ~-173% (worse) | Naive persistence is very strong on a short synthetic random walk. |
| 14d | ~0.59 | ~0.69 | ~+13.9% (better) | GBM beats baseline. |
| 30d | n/a | n/a | n/a | Skipped — 60 rows are insufficient to form 30-day-ahead test targets. |

### Interpretation
On this tiny synthetic set the tree model cannot out-forecast a random-walk
persistence baseline at the shortest horizon — an honest, expected outcome given
the data volume and the near-random-walk generator. The pipeline, leakage guards,
quantile intervals, and baseline comparison are all validated end-to-end. Real,
larger, multi-lane data is required to draw conclusions about production accuracy.

## 6. Reproducing

```bash
cd ml && PYTHONPATH=. .venv/bin/python -m models.freight_gbm      # train + print metrics
cd ml && PYTHONPATH=. .venv/bin/python -m models.baseline_freight # baseline results JSON
```

Artifacts: `ml/models/artifacts/training_report.json` (metrics, timestamp,
dataset version, features, split) and `ml/models/results/`.

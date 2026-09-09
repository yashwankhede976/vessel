# Freight Forecasting

**Project:** Vessel — Intelligent Freight Forecasting & Vessel Chartering platform
**Document type:** Model / Methodology note
**Status:** v1.0

How the platform forecasts freight rates at the 7, 14 and 30-day horizons, and
how those forecasts reach the API. Implemented in `ml/models/freight_gbm.py`,
`ml/features/`, `ml/models/baseline_freight.py`, `ml/models/uncertainty.py`, and
bridged into Django by `ml/models/export_forecasts.py` +
`apps/operations/management/commands/import_freight_forecasts.py`.

---

## 1. Model

The advanced model is a **gradient-boosted tree ensemble (XGBoost)** — one
`XGBRegressor` per horizon (7 / 14 / 30 days). It is not deep learning. LightGBM
was preferred originally but its wheel did not build on the target macOS, so
XGBoost was chosen; this is documented in `ml/README.md`.

- `MODEL_NAME = "freight_gbm_xgboost"`, `MODEL_VERSION = "0.2.0"`.
- Per horizon, three models are trained: a **point** model plus **lower (q=0.10)**
  and **upper (q=0.90)** `reg:quantileerror` models — a data-derived ~80%
  prediction interval (see `EVALUATION.md` and `FREIGHT_FORECAST_UNCERTAINTY.md`).

## 2. Horizons

`HORIZONS = {7: future_7d_freight, 14: future_14d_freight, 30: future_30d_freight}`.
Each horizon is trained and evaluated independently on the rows whose realized
future target is known. If a dataset is too small to expose a horizon's target
(e.g. the 60-row synthetic demo cannot form 30-day-ahead targets on the test
split), that horizon is **skipped and recorded** — never fabricated.

## 3. Features (leakage-safe)

See `FEATURE_ENGINEERING.md` for the full list. Inputs include historical
freight, rolling averages, rolling volatility, percentage change, seasonality,
vessel-supply indicators, demand / ton-mile indicators, port-congestion
indicators, weather-risk indicators, commodity price, bunker indicators and
route distance. **No future-dated column is ever used as a feature** — the
leakage rails are described in `FEATURE_ENGINEERING.md`.

## 4. Response shape

`predict_with_uncertainty(...)` returns, per forecast row:

```json
{ "predicted": 18.5, "lower": 17.0, "upper": 20.0, "confidence": 0.80,
  "lower_quantile": 0.10, "upper_quantile": 0.90 }
```

`model_version`, `training_timestamp` (the report's `trained_at`) and dataset
provenance live in the **training report / artifact**, not on each row. When the
forecasts are exported and imported into Django (§6), the stored
`FreightForecast` row carries `predicted_rate_per_tonne`, `lower_bound`,
`upper_bound`, `confidence`, `model_name`, `model_version` and `generated_at`.

`data_freshness` is a property of the **stored** forecasts, surfaced by the read
API `GET /api/v1/forecasts/freight/` (latest observation date, observation age,
forecast generation time, forecast count) rather than by the model itself.

## 5. Baseline comparison

Every horizon is compared on the same test rows against deterministic baselines
(`naive_previous`, `moving_average`) with MAE / RMSE / MAPE and an
`improvement_pct` vs the naive baseline. See `EVALUATION.md`.

## 6. ML → Django bridge

The ML layer is a **separate package and virtualenv** (Python 3.13; the
scientific stack segfaults on the backend's 3.14). Django never imports it. The
bridge is file-based:

1. **ML side** (`python -m ml.models.export_forecasts`, ML venv): trains the
   horizon models and writes `ml/models/results/freight_forecasts.json` — the
   latest per-lane forecast for each horizon plus metrics and provenance
   (`dataset_kind`, `data_kind="FORECAST"`, `generated_at`).
2. **Backend side** (`python manage.py import_freight_forecasts --file <artifact>`):
   reads the JSON and upserts `operations.FreightForecast` rows. Idempotent
   (keyed on the model's natural unique constraint). `--create-lanes` adds
   missing Origin/Route; otherwise unknown lanes are skipped and reported.
   Horizon mapping: 7d & 14d → `short_term`, 30d → `medium_term`.

## 7. Data provenance labelling

- **REAL** — sourced from a real provider (none of the demo forecasts are REAL).
- **SYNTHETIC** — generated inputs (the demo dataset). The importer prints a
  warning and the artifact records `dataset_kind=SYNTHETIC`.
- **ESTIMATED** — a value inferred where a direct measurement was unavailable.
- **FORECAST** — a model output for a future date (`data_kind=FORECAST`).

The demo pipeline produces **SYNTHETIC + FORECAST** data end-to-end. Nothing in
this layer claims to be real market data.

## 8. Known limitations

- On the tiny synthetic demo (60 rows, 2 lanes) the GBM does **not** reliably
  beat the naive baseline at the 7-day horizon (the naive persistence baseline is
  very strong on a short random walk); the 14-day horizon does beat it. These are
  honest measured results on synthetic data — real, larger data is expected to
  change them. The 30-day horizon is skipped on the demo for lack of rows.
- The bridge stores the **latest** per-lane forecast per horizon; it is not a
  streaming/real-time pipeline. There is no real-time inference in the request
  path — the read API serves stored rows.

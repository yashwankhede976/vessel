# Freight Forecasting Dataset Schema

**Project:** Vessel — Intelligent Freight Forecasting & Vessel Chartering platform
**Document type:** Analytical Dataset / Feature Schema
**Status:** Draft v1.0

The unified analytical dataset that the freight forecasting models consume.
Defined in code at `ml/datasets/schema.py` (the single source of truth) and
assembled by `ml/datasets/builder.py`. **No model is trained here** — this
document and that package define the *inputs* to modelling.

---

## 1. Row grain

Each row represents one **(date, origin, destination, vessel_type)**:

| Column | Type | Description |
| --- | --- | --- |
| `date` | date | Observation date. Features describe conditions known **as of** this date. |
| `origin` | category | Origin country/region (Australia, Indonesia, Mozambique, USA, Russia). |
| `destination` | category | Destination East Coast India port (Paradip, Visakhapatnam, …). |
| `vessel_type` | category | Vessel class (handysize, supramax, panamax, capesize, …). |

The four columns together form the unique key — one row per lane-vessel-day.

## 2. Features

All features describe state **known as of `date`** — no future information leaks
into a feature (see §4).

| Feature | Type | Unit | Description | Source |
| --- | --- | --- | --- | --- |
| `route_distance_nm` | float | nautical miles | Sailing distance for the origin→destination route. | catalog.Route |
| `historical_freight_rate` | float | USD/tonne | Freight rate for the lane/vessel_type **lagged one step** (excludes the same-day realized rate). | FreightObservation |
| `vessel_availability` | int | count | Suitable vessels open/available near the origin. | Vessel.availability + AIS |
| `port_congestion` | float | count | Vessels waiting / congestion at the destination port. | PortCongestionObservation |
| `port_waiting_time` | float | days | Expected/observed average waiting time at the destination. | PortCongestionObservation |
| `commodity_import_volume` | float | tonnes | Recent import throughput of the commodity into the destination. | PortTraffic / TradeObservation |
| `commodity_price` | float | USD/tonne | Recent commodity (coal) price. | CommodityPriceObservation / WB Pink Sheet |
| `bunker_indicator` | float | USD/tonne | Recent bunker (marine fuel) price indicator. | BunkerPriceObservation |
| `weather_risk` | float | 0..1 | Normalized weather/marine risk for the lane/destination (monsoon/cyclone exposure). Derived. | Weather/Marine/Cyclone (derived) |
| `seasonality_month` | int | month | Calendar month (1–12). | calendar |
| `seasonality_sin` | float | — | `sin(2π·month/12)` cyclical encoding. | calendar |
| `seasonality_cos` | float | — | `cos(2π·month/12)` cyclical encoding. | calendar |
| `is_monsoon` | int | 0/1 | 1 if `date` is within the Bay-of-Bengal monsoon window (Jun–Dec heuristic). | calendar |
| `trade_volume` | float | tonnes | Recent bilateral trade volume on the lane for the commodity. | TradeObservation (Comtrade) |
| `ton_mile_proxy` | float | tonne-nm | `route_distance_nm × commodity_import_volume` — demand-for-shipping proxy. | derived |
| `vessel_supply_proxy` | float | — | `vessel_availability` normalized by ton-mile demand — supply-tightness proxy. | derived |

## 3. Target fields

The values the model predicts (realized future freight rates for the same lane
and vessel_type):

| Target | Type | Unit | Description |
| --- | --- | --- | --- |
| `freight_rate` | float | USD/tonne | Realized freight rate **on** `date` (current label). |
| `future_7d_freight` | float | USD/tonne | Realized rate ~7 days after `date` (short-term). |
| `future_14d_freight` | float | USD/tonne | Realized rate ~14 days after `date`. |
| `future_30d_freight` | float | USD/tonne | Realized rate ~30 days after `date` (medium-term). |

Future targets are looked up by a per-lane forward `merge_asof` (nearest within
a small day tolerance, default ±3 days), so a target is drawn only from an
observation at or after the horizon date. Rows near the end of a lane's series
have `NaN` future targets (no future observation exists yet) and should be
dropped or masked at training time.

## 4. Temporal integrity (no leakage)

Getting this right is the difference between a real forecast and a fantasy:

- **Features are as-of `date`.** Point-in-time joins only; nothing from after `date` enters a feature.
- **`historical_freight_rate` is lagged.** It is the lane's *previous* observation, never the same-day realized rate — so the current rate isn't smuggled in as a feature.
- **`freight_rate` is the current label**, `future_*` are strictly forward. They are targets, not features; never feed them (or anything derived from them) as inputs.
- **Train/validate splits must be temporal** (walk-forward), not random, to respect this ordering. The dataset does not shuffle.

## 5. Assembling the dataset

```python
from datasets.builder import build_dataset   # run from ml/ with the ml venv

df = build_dataset(
    freight=freight_df,              # spine: date,origin,destination,vessel_type,freight_rate
    routes=routes_df,                # optional feature frames…
    congestion=congestion_df,
    commodity_price=price_df,
    bunker=bunker_df,
    commodity_volume=volume_df,
    vessel_availability=avail_df,
    weather_risk=weather_df,
    trade_volume=trade_df,
)
```

Only the `freight` spine is required; every other source frame is optional and
left-joined on the keys it shares. Missing sources leave their columns null —
never fabricated. A runnable synthetic demo is in `ml/datasets/example.py`
(`python -m datasets.example`), used only to validate the schema end-to-end; it
uses generated data and trains nothing.

## 6. Feature engineering (leakage-safe)

`ml/features/` engineers additional model-ready features on top of this dataset
(`features.build_features(df)`). All transforms operate **per lane on
chronologically-sorted rows** and are **past-only**, so no future information
enters a training row:

- **Rolling mean / volatility** — the value series is shifted by one step before
  rolling, so the window ends at the *previous* row (the current row's value is
  excluded — safe even for the freight-rate series).
- **Lag values** — lag ≥ 1 only (lag 0 is rejected as it would be the label).
- **Percentage change** — computed from shifted (past) values only.
- **Seasonal** — day/week/quarter/monsoon derived purely from `date`.
- **Domain indicators** — vessel supply, demand, port congestion, and weather
  risk, each derived only from as-of feature columns.

Guardrails:
- `build_features` refuses to build from a future target column.
- `validate_temporal_order` raises if any lane is unsorted or has duplicate
  timestamps (run before any windowed op).
- `engineered_feature_columns(df)` returns the input columns for a model,
  **excluding** the grain keys, `freight_rate`, and all `future_*` targets.

Leakage prevention is covered by `ml/features/test_leakage.py` (e.g. a spike in
a future row provably does not affect any earlier row's features; lanes are
isolated).

## 6a. Baseline benchmark

`ml/models/baseline_freight.py` provides the deterministic benchmark that
advanced models must beat: **naive previous value** (persistence) and **moving
average** forecasters for the 7/14/30-day horizons. Each is evaluated against
the realized `future_{7,14,30}d_freight` targets using **MAE, RMSE, and MAPE**,
both overall and per lane. Results are stored as JSON in
`ml/models/results/baseline_freight_results.json`. No deep learning is used.

## 6b. Gradient-boosted model (XGBoost)

`ml/models/freight_gbm.py` is the first production-oriented model: one XGBoost
regressor per horizon (7/14/30d) trained on the validated feature pipeline
(§6), using a **time-based** train/validation/test split (`ml/models/splits.py`)
so it is only ever tested on dates after those it trained on. It reports
MAE/RMSE/MAPE per horizon on the test split **alongside the baseline**, and
saves a versioned artifact bundle (per-horizon models, feature list, metrics,
training timestamp, dataset version) to `ml/models/artifacts/`. Model binaries
are git-ignored; the `training_report.json` and `feature_list.json` are tracked.
XGBoost is a gradient-boosted tree ensemble (no deep learning); the model is not
yet exposed to the frontend.

## 7. Notes & limitations

- The dataset is **provider-agnostic**: it consumes already-extracted frames, so it carries no Django dependency and is unit-testable in isolation (`ml/datasets/test_builder.py`).
- Several features are **proxies** (ton-mile, vessel-supply), explicitly labelled as such — they approximate demand/supply pressure, not measured quantities.
- The authoritative freight target ideally comes from a licensed benchmark (Baltic Exchange); for the prototype a lawful public proxy or clearly-labelled synthetic rate is used (see [DATA_SOURCES.md](./DATA_SOURCES.md)).
- The schema is versioned with the code; changing a column updates `ml/datasets/schema.py` and this document together (documentation golden rule).

## Related documents

- [ARCHITECTURE.md](./ARCHITECTURE.md) (§5 ML layer)
- [DATA_SOURCES.md](./DATA_SOURCES.md)
- [FUNCTIONAL_REQUIREMENTS.md](./FUNCTIONAL_REQUIREMENTS.md) (FR-FC Freight Forecasting)
- [NON_FUNCTIONAL_REQUIREMENTS.md](./NON_FUNCTIONAL_REQUIREMENTS.md) (NFR-ACC accuracy/leakage)

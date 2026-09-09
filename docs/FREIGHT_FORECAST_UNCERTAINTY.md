# Freight Forecast Uncertainty

**Project:** Vessel — Intelligent Freight Forecasting & Vessel Chartering platform
**Document type:** Model / Methodology note
**Status:** Draft v1.0

How the freight forecasting model produces an uncertainty estimate — a
prediction interval and a confidence score — for each forecast. Implemented in
`ml/models/uncertainty.py` and `ml/models/freight_gbm.py`. The numbers are
**derived**, not hand-picked.

---

## 1. Response structure

Every forecast returns:

```json
{
  "predicted": 24.8,
  "lower": 23.1,
  "upper": 26.7,
  "confidence": 0.82,
  "lower_quantile": 0.1,
  "upper_quantile": 0.9,
  "confidence_scale_k": 0.2
}
```

- **predicted** — the point forecast (USD/tonne), from the mean/point model.
- **lower / upper** — the prediction interval bounds.
- **confidence** — a score in (0, 1] (see §3).
- **lower_quantile / upper_quantile / confidence_scale_k** — provenance, so the
  interval and confidence can be reproduced exactly.

The structure always satisfies **lower ≤ predicted ≤ upper**.

## 2. Prediction interval — quantile regression

The interval is produced by **quantile regression**, not a Gaussian ±σ band and
not an arbitrary percentage. For each horizon we train two additional XGBoost
models using the quantile objective (`reg:quantileerror`):

- a **lower** model at quantile α = 0.10,
- an **upper** model at quantile α = 0.90.

At prediction time the interval is `[lower_model(x), upper_model(x)]`. Because
each bound is a separate model conditioned on the features, the interval **width
varies per input** — it widens where the training data was noisier/sparser for
similar feature values and narrows where the signal was cleaner. The default
0.10/0.90 pair is a nominal **80% prediction interval**.

Quantile models are trained independently, so on rare points the raw bounds can
cross or the point estimate can fall just outside them. `build_forecast_result`
repairs this deterministically (swap crossed bounds, clamp the point estimate
into the interval) so the response is always coherent.

**Measured coverage.** Training records `interval_coverage` per horizon on the
test split — the fraction of realized values that actually fell inside the
interval. This lets us check whether the nominal 80% interval is well-calibrated
on held-out data (and recalibrate the quantiles if not), rather than assuming it.

## 3. Confidence score — a documented function of interval width

Confidence is a **deterministic function of the interval's relative width** — no
hand-picked confidence values anywhere:

```
relative_width = (upper - lower) / max(|predicted|, eps)
confidence     = 1 / (1 + relative_width / k)
```

with a single fixed, documented constant **k = 0.20** (`CONFIDENCE_SCALE_K`).

Why this form:

- **Monotonic** — a wider interval strictly lowers confidence; a tighter one
  raises it. This is the property a confidence score must have.
- **Bounded** — confidence ∈ (0, 1]. A zero-width interval → confidence = 1.0.
- **Scale-free** — it uses *relative* width, so it behaves consistently across
  lanes/vessel classes with very different absolute rate levels.
- **Interpretable anchor** — `k` is the relative width at which confidence =
  0.50. With k = 0.20, an interval spanning 20% of the predicted value is
  "half-confident"; 10% → ~0.67; 40% → ~0.33. `k` is the *only* tunable and it
  is explicit and versioned, not chosen per forecast.

### Worked example

For `predicted = 24.8, lower = 23.1, upper = 26.7`:

```
relative_width = (26.7 - 23.1) / 24.8 = 3.6 / 24.8 = 0.14516…
confidence     = 1 / (1 + 0.14516 / 0.20) = 1 / 1.72581… = 0.5795…
```

so the interval [23.1, 26.7] around 24.8 yields **confidence ≈ 0.58**. A tighter
interval (say [24.0, 25.6]) around the same point gives ≈ 0.76. The example
figure of `0.82` in the task corresponds to a relative width of ≈ 0.044 (a very
tight ±~2% interval).

## 4. What this is NOT

- Not a fixed ±X% band.
- Not a Normal-distribution assumption on the errors.
- Not a hand-assigned confidence table. Every confidence value is computed from
  the model's own interval via the formula above.

## 5. Where it lives / how to reproduce

- Interval + confidence: `ml/models/uncertainty.py` (`build_forecast_result`,
  `confidence_from_interval`).
- Quantile-model training + `predict_with_uncertainty`: `ml/models/freight_gbm.py`.
- The trained artifact's `training_report.json` records the `uncertainty` block
  (method, quantile levels, confidence formula, and `k`), so a saved model's
  uncertainty behaviour is fully documented alongside it.
- Tests: `ml/models/test_uncertainty.py` validate the response structure and the
  principled behaviour (ordering, monotonicity, the exact formula, k-anchor).

## Related documents

- [FREIGHT_DATASET_SCHEMA.md](./FREIGHT_DATASET_SCHEMA.md)
- [ARCHITECTURE.md](./ARCHITECTURE.md) (§5 ML layer)
- [NON_FUNCTIONAL_REQUIREMENTS.md](./NON_FUNCTIONAL_REQUIREMENTS.md) (NFR-ACC-2: forecasts carry uncertainty)
- [FUNCTIONAL_REQUIREMENTS.md](./FUNCTIONAL_REQUIREMENTS.md) (FR-FC-2: forecast confidence bands)

# Explainability

**Project:** Vessel — Intelligent Freight Forecasting & Vessel Chartering platform
**Document type:** Methodology note
**Status:** v1.0

Every recommendation the platform produces is auditable: it exposes WHY it was
made, the factors for and against, the model/engine versions used, and how fresh
the underlying data is. This is built into the decision engine
(`apps/decisions/services/decision_engine.py`) and surfaced by the API and UI.

---

## 1. The explainability block

`POST /api/v1/decision/` returns an `explainability` object on every response:

```json
{
  "reasons": ["Recommended Pana Fit (panamax) for Australia → Paradip.",
              "Contract: MULTI_VOYAGE (lowest risk-adjusted cost).",
              "Timing: FIX_NOW — Rates expected to rise 6.0% ..."],
  "positive_factors": ["Top vessel Pana Fit scores 88/100 on suitability.",
                       "Market is NEUTRAL (index 50)."],
  "negative_factors": ["Destination congestion 60/100.",
                       "2 vessel(s) excluded as incompatible with the port."],
  "model_version": {
    "freight_model": "freight_gbm_xgboost",
    "freight_model_version": "0.2.0",
    "generated_at": "2026-09-10T...",
    "suitability_engine": "vessel_suitability@rule-based",
    "risk_engine": "risk_engine@rule-based",
    "timing_engine": "fix_wait@rule-based"
  },
  "data_freshness": [ { "dataset": "ais_positions", "level": "FRESH", ... }, ... ]
}
```

## 2. Where each part comes from (real outputs, not narration)

- **reasons** — the concrete decisions taken: which vessel, which contract
  (with the rule that drove it — lowest risk-adjusted cost), and the fix/wait
  decision with the engine's own `reason` string.
- **positive_factors / negative_factors** — derived from the real engine
  numbers: suitability score, market classification, overall risk band,
  destination congestion, and how many vessels were excluded as incompatible.
  A factor lands in positive vs negative based on documented thresholds (e.g.
  congestion ≥ 55 is negative; risk < 50 is positive).
- **model_version** — the freight model name/version and generation time read
  from the latest stored `FreightForecast` row, plus the rule-based engine tags
  for suitability, risk and timing. So a recommendation can always be traced to
  the exact model that produced its forecast.
- **data_freshness** — the freshness of the datasets the decision consumed
  (AIS, weather, marine, trade, congestion), from
  `apps/ingestion/freshness.data_freshness()`, classified FRESH / STALE /
  VERY_STALE / UNKNOWN. A user can see how current a recommendation is.

## 3. Per-factor breakdowns

Beyond the summary block, each composed engine returns its own factor breakdown,
also surfaced in the decision response and the UI:

- **Risk** — `risk.factors[]`: each factor's raw value, normalized 0–1, weight,
  contribution to the 0–100 score, and whether it was available. UNKNOWN factors
  are shown as UNKNOWN and excluded from the score (never assigned a value).
- **Market pressure** — `market.factors[]`: the same shape for the 0–100 index.
- **Suitability** — the recommended vessel's `suitability.factors[]`: how each
  factor (compatibility, capacity, draft/LOA/beam, freight, ETA reliability,
  congestion, weather, demurrage, fuel efficiency) contributed to its score.
- **Timing** — `timing.drivers` includes the numeric expected move, effective
  confidence, and the documented thresholds used, so the FIX/WAIT call is fully
  reproducible.

## 4. Honesty guarantees

- No fabricated values: absent inputs stay UNKNOWN / null; a missing freight
  forecast is replaced by a clearly-labelled planning default with a note.
- Deterministic: given the same inputs and stored data, the same decision and
  the same explainability are produced.
- Data provenance: the UI labels each value REAL / SYNTHETIC / ESTIMATED /
  FORECAST (see `docs/FRONTEND_ARCHITECTURE.md`), and the freshness block states
  how current the inputs are.

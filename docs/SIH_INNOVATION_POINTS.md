# SIH Innovation Points

What makes Vessel more than a dashboard. These are claims we can back with
running code and passing tests. Where something is a model output or a heuristic,
it is labelled that way — we do not dress estimates up as measured truth.

---

## 1. One composed, explainable decision — not a pile of charts

Most tools show freight, congestion, and vessel data on separate screens and
leave the judgement to the analyst. Vessel composes the whole chain into a
single call, `POST /api/v1/decision/`:

freight forecast → vessel recommendation → berth compatibility → congestion →
ETA → demurrage → landed cost → contract strategy → risk → **FIX / WAIT /
PARTIAL_FIX / MONITOR** + expected savings.

Every result carries `explainability`: `reasons`, `positive_factors`,
`negative_factors`, `model_version`, and `data_freshness`. The recommendation is
auditable, not a black box.

## 2. India-East-Coast-specific operational intelligence

The decision layer is tuned for the actual constraint set of East Coast India
dry-bulk imports: port draft/berth limits (e.g. capesize excluded at draft-
limited berths), congestion at Paradip / Visakhapatnam / Gangavaram / Gopalpur /
Dhamra / Sagar-Sandheads / Haldia, laycan windows, demurrage exposure, and
monsoon/weather risk. Compatibility is a **deterministic rule engine**, so
exclusions are explainable ("draft 18.1 m > berth limit"), not statistical.

## 3. Honest uncertainty on forecasts

Freight forecasts ship with quantile-regression intervals and a documented
confidence formula (wider interval → lower confidence), not arbitrary
percentages. The ML layer has explicit **no-leakage** tests: rolling/lag
features are proven to use only past rows, and a future spike cannot change an
earlier forecast. That is verifiable data-integrity, tested in CI.

## 4. Timing as a first-class output (FIX vs WAIT)

The platform does not just forecast a rate — it turns the forecast into an
action: fix now, wait, partially fix, or monitor, with an expected freight move
and an effective confidence. This is the difference between "here is a chart"
and "here is what to do and why."

## 5. A grounded chatbot

`POST /api/v1/chat/` answers common chartering questions in natural language,
grounded in real backend output (freight forecast, vessel, cost, contract, risk,
FIX/WAIT). The OpenAI key is backend-only; when unset the chatbot falls back to a
deterministic grounded answer. It is designed to refuse to invent numbers it
cannot compute — the answer is tied to the same engines the decision endpoint
uses. See `docs/CHATBOT.md`.

## 6. Scenario / what-if reusing the same engines

Freight-change %, congestion, and vessel-availability overrides flow through the
same composition, so a what-if uses the identical logic as the base case. No
divergence between "the model" and "the simulator."

## 7. Data labelled by nature, end to end

Every value is tagged **REAL / FORECAST / ESTIMATED / SYNTHETIC** in the API and
the UI. Judges (and users) always know whether they are looking at an observed
fact, a prediction, a derived estimate, or seeded demo data. This honesty is a
feature, not a caveat.

---

## Verified, not aspirational

- Backend **478 tests pass**, frontend **21 pass**, ML **43 pass**.
- `docker compose up --build` brings up db + backend + frontend and they
  communicate; the backend migrates and seeds ports on startup.
- The 100,000 MT coal Australia → Paradip workflow returns every field above
  with grounded values.

See `docs/FINAL_TEST_REPORT.md` for exact commands, results, and the honest list
of known limitations (notably: no auth yet, and synthetic/seed inputs).

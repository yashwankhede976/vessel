# AI Assistant

**Project:** Vessel — Intelligent Freight Forecasting & Vessel Chartering platform
**Document type:** Feature note
**Status:** v1.0

A grounded question-answering assistant for chartering decisions. It answers
from the platform's own decision engines and **never invents values**.
Implemented at `POST /api/v1/decision/assistant/`
(`backend/apps/api/v1/decision/views.py`), consumed by the frontend AI Assistant
page (`/assistant`).

---

## 1. What it is (and is not)

- It **is** an intent classifier over a small set of chartering questions that
  routes each question to the existing engines (decision engine, contract
  strategy, landed cost) and summarises the real result.
- It is **not** an LLM and does **not** generate free-form prose or numbers.
  Every figure in an answer comes from a backend engine call; if a value can't
  be computed, the assistant says so rather than guessing. A conversational LLM
  layer could be added on top later without changing this grounding contract.

## 2. Endpoint

```
POST /api/v1/decision/assistant/
{ "question": "Should I fix Australia to Paradip?" }

→ { "intent": "fix_or_wait",
    "answer": "For Australia → Paradip: FIX_NOW. Rates expected to rise ...",
    "data": { "timing": {...}, "recommended_vessel": {...}, "risk": {...} },
    "grounded": true }
```

The response always carries the machine-readable `data` (the engine output it
was grounded in) alongside the human `answer`, so the UI can show both.

## 3. Supported questions → intent → engines used

| Example question | Intent | Grounded in |
|---|---|---|
| "Should I fix Australia to Paradip?" | `fix_or_wait` | decision engine → fix/wait + vessel + risk |
| "Which vessel is best?" | `best_vessel` | decision engine → recommended vessel (suitability) |
| "Is Dhamra better than Paradip?" | `compare_ports` | decision engine run for each port → total voyage cost |
| "Spot or multi-voyage?" | `contract_choice` | decision engine → spot-vs-contract comparison |
| "What happens if freight increases 10%?" | `freight_scenario` | decision engine with a scenario override |

Intent detection is deterministic: it scans the question for the project origins
(Australia / Indonesia / Mozambique / USA / Russia), the East Coast ports
(Paradip / Dhamra / Visakhapatnam / Gangavaram / Gopalpur / Haldia), a percentage
(for freight scenarios), and keywords (fix/wait, vessel, spot/multi/contract,
better/vs). Unrecognised questions fall back to the fix-or-wait read for the
detected (or default) lane.

## 4. Grounding rules

- **No invented values.** Port comparisons only assert a cheaper port when both
  ports' costs were actually computed; otherwise the assistant states that no
  cost ranking can be made (missing route/forecast data).
- **Reuses the decision engine**, so answers are consistent with the
  `/api/v1/decision/` endpoint and the Decision page.
- **No new backend logic** — the view only classifies and delegates.
- **No secrets / no external calls** — it runs entirely on stored data and the
  deterministic engines.

## 5. Frontend

The `/assistant` page offers the five sample questions as one-click prompts plus
a free-text box; it POSTs to the assistant endpoint and renders the grounded
answer with an ESTIMATED provenance label. See `docs/FRONTEND_ARCHITECTURE.md`.

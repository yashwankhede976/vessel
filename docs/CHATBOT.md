# Chatbot

**Project:** Vessel — Intelligent Freight Forecasting & Vessel Chartering platform
**Document type:** Feature note
**Status:** v1.0

The **Chatbot** is an **AI Freight Procurement and Vessel Chartering Expert for
India** — a conversational, OpenAI-backed assistant that is **strictly
specialized** in overseas bulk-cargo (primarily coal) procurement and vessel
chartering to India's East Coast ports. It is **not** a general-purpose chatbot.
It stays grounded in the platform's own data and never invents values.

Implemented at `POST /api/v1/chat/` (`backend/apps/api/v1/chat/`, service in
`backend/apps/decisions/services/chatbot.py`) and consumed by the React
**Chatbot** page (`/chatbot`, `frontend/src/pages/ChatbotPage.tsx`).

### Scope (in-domain only)

- **Origins:** Australia, Indonesia, Mozambique, USA, Russia
- **Indian destination ports:** Paradip, Dhamra, Visakhapatnam (alias "Vizag"),
  Gangavaram, Gopalpur, Sagar/Sandheads (alias "Sandheads"), Haldia
- **Vessel types:** Handysize, Supramax, Panamax, Capesize
- **Primary commodity:** Coal

It answers questions about: freight forecasting to India, Indian port selection,
Indian berth compatibility, vessel selection for Indian ports, Indian port
congestion, ETA to Indian ports, demurrage risk, total landed cost in India,
origin→India comparison, FIX_NOW / WAIT / PARTIAL_FIX timing, spot vs
short-term vs multi-voyage contracts, multi-voyage procurement, alternative
Indian ports, Indian monsoon/weather/cyclone risk, vessel idle-time / next
voyage, Indian coal import/demand trends, and scenario analysis for Indian
routes.

**Out-of-scope questions** get exactly: *"This chatbot is specialized in
overseas bulk-cargo procurement and vessel chartering for India's East Coast
ports."* — and no backend call is made.

---

## 1. Architecture & flow

```
User question
  → Identify Indian freight/chartering intent (scope gate; else refuse)
  → Extract origin / destination / cargo / vessel / date (+ conversation memory)
  → Call the backend decision engine (real platform APIs)
  → Receive actual data (freight forecast, vessel, compatibility, congestion,
    ETA, demurrage, landed cost, contract, risk, FIX/WAIT, scenario, market)
  → OpenAI explains the result (never computes it)
  → Final answer (India-framed, labelled REAL/FORECAST/ESTIMATE/SYNTHETIC)
```

1. **Scope gate.** Off-topic questions are refused up front with the fixed
   message and **no backend/OpenAI call** is made. A follow-up within an
   existing conversation stays in scope (see §8, context memory).
2. **Grounding first.** The service infers the lane
   (origin/destination/commodity/cargo/vessel) from the message, page `context`
   and the previous turn, then calls the platform's own `evaluate_decision(...)`
   engine to retrieve **real** data: freight forecast, vessel recommendation,
   vessel–port compatibility, congestion, ETA, voyage/landed cost, contract
   strategy, risk, FIX/WAIT timing, scenario overrides, market pressure,
   expected savings and explainability. These come from PostgreSQL + the
   platform engines — OpenAI is **never** allowed to calculate them.
3. **LLM phrasing (optional).** That compact, real data packet plus the user
   question is sent to the OpenAI **Responses API** with a strict India-expert
   system prompt instructing the model to use only supplied data, prioritise the
   Indian angle, apply the data labels, and never invent values.
4. **Graceful fallback.** If `OPENAI_API_KEY` is unset, or OpenAI errors/times
   out, the service returns a deterministic, India-framed answer composed
   directly from the grounded data.
5. **Honesty.** If the decision engine cannot produce grounded data, the answer
   is exactly: *"Indian data for this request is currently unavailable."*

Code: `backend/apps/decisions/services/chatbot.py` (service) and
`backend/apps/api/v1/chat/` (API).

## 2. Contract

```
POST /api/v1/chat/
{ "message": "...", "conversation_id": "...", "context": { ... } }

-> { "conversation_id": "...", "answer": "...", "sources": [...],
     "data_used": [...], "confidence": null }
```

- `sources` — the platform engines that produced the grounding.
- `data_used` — which grounded fields were populated for this answer.
- `confidence` — the platform's own decision confidence (or `null`).
- `DELETE /api/v1/chat/?conversation_id=...` resets a conversation.

## 3. Capabilities

Supports questions such as: *Should I fix Australia to Paradip? · Which vessel
is best for 100,000 MT? · Compare Paradip and Dhamra · Which is cheaper,
Australia or Indonesia? · Spot or multi-voyage? · What happens if freight
increases 10%? · Why did the system recommend WAIT?*

The React page offers quick-question chips ("Should I fix now?", "Best vessel?",
"Best port?", "Compare origins", "Spot vs contract"), a message transcript, an
input box with send/loading/error states, and a conversation reset.

## 4. System prompt (India expert, abridged)

> You are an AI Freight Procurement and Vessel Chartering Expert for India,
> STRICTLY specialized in overseas bulk-cargo (primarily coal) procurement and
> vessel chartering from Australia, Indonesia, Mozambique, the USA and Russia to
> India's East Coast ports (Paradip, Dhamra, Visakhapatnam, Gangavaram,
> Gopalpur, Sagar/Sandheads, Haldia) using Handysize, Supramax, Panamax and
> Capesize vessels. Use ONLY the supplied application data; never compute or
> invent freight rates, vessel details, port draft/LOA/beam limits, congestion,
> ETA, costs, savings, forecasts or risk. Prioritise the Indian angle. Label
> values REAL DATA / FORECAST / ESTIMATE / SYNTHETIC DEMO DATA and cite the
> source/timestamp when present. If data is missing, say what is missing.

## 5. Data labels

Every value in an answer is labelled by nature, using labels carried in the
grounding block:

- **REAL DATA** — stored/observed (e.g. vessel–port compatibility over stored
  vessel/berth data).
- **FORECAST** — a model prediction from a stored `FreightForecast` (carries a
  `generated_at` timestamp and model version).
- **ESTIMATE** — derived/heuristic engine output (congestion, ETA, demurrage,
  landed cost, risk, contract strategy).
- **SYNTHETIC DEMO DATA** — the planning default used when no stored forecast
  exists for the lane.

Costs are computed in USD; INR shown in an answer is an approximate display
conversion and is labelled as such.

## 6. Security

- `OPENAI_API_KEY` is read **only** on the Django backend
  (`settings.OPENAI["API_KEY"]`, env `OPENAI_API_KEY`). It is **never** sent to
  React, **never** logged, and **never** required (unset → grounded fallback).
- There is no `VITE_OPENAI*` variable; the browser never sees a key.
- The endpoint validates input and is rate-limited (`ScopedRateThrottle`,
  `CHAT_THROTTLE_RATE`, default `30/min`). OpenAI calls are timeout-guarded.
- See [SECURITY.md](./SECURITY.md).

## 7. Configuration

- `OPENAI_API_KEY` (backend env only; never exposed to React or logged)
- `OPENAI_MODEL` (default `gpt-4o-mini`), `OPENAI_TIMEOUT`,
  `OPENAI_MAX_OUTPUT_TOKENS`, `CHAT_THROTTLE_RATE` (default `30/min`).

## 8. Conversation context

Conversation memory (per `conversation_id`, in-process) keeps the last resolved
lane, so a follow-up inherits the earlier origin/destination/comparison.

> User: "Compare Australia and Indonesia to Paradip."
> User: "Which is cheaper?" → still understood as Australia vs Indonesia → Paradip.

`DELETE /api/v1/chat/?conversation_id=...` clears both the transcript and the
remembered lane.

## 9. Limitations (do not overclaim)

- Costs are computed in USD by the engines; where INR is shown it is an
  approximate display conversion, labelled as such.
- Conversation memory is in-process (per backend worker) — sufficient for the
  prototype; use a shared cache/DB for multi-worker production.
- When the lane cannot be inferred, the demo default lane (Australia → Paradip,
  coal) is used; page `context` and prior turns override it.
- Not a source of legal/financial advice; forecasts are model output, not
  measured market prices.

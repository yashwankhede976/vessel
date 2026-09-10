# Security

**Project:** Vessel — Intelligent Freight Forecasting & Vessel Chartering platform
**Document type:** Security notes
**Status:** v1.0

This document records the platform's security posture, with emphasis on secret
handling for the AI chatbot (OpenAI). It reflects what is actually implemented;
known limitations are called out honestly.

---

## 1. Secrets & API keys

- **All secrets come from environment variables**, read on the backend only via
  `django-environ` (`backend/config/settings.py`). Nothing is hard-coded.
- **`.env` is never committed.** `.env`, `.env.*` are git-ignored; only
  `.env.example` (placeholders) is tracked. Copy `.env.example` → `.env` locally.
- **The OpenAI key is backend-only.** `OPENAI_API_KEY` is read into
  `settings.OPENAI["API_KEY"]` and used exclusively inside
  `apps/decisions/services/chatbot.py`. It is:
  - **never** sent to the frontend (no `VITE_OPENAI*` variable exists, and the
    chat API response contains only `answer/sources/data_used/confidence`);
  - **never** logged — OpenAI failures log only the exception *type/name*, not
    the key or the prompt;
  - **never** required — if unset, the chatbot falls back to a grounded
    deterministic answer (no external call).
- **Rotate leaked keys immediately.** If a key is ever pasted into chat, a
  ticket, or a commit, treat it as compromised and revoke it in the provider
  console. Never re-commit it.

## 2. AI chatbot request handling

- **Validation:** `message` is required, trimmed, and length-capped
  (`ChatRequestSerializer`); invalid requests return HTTP 400.
- **Rate limiting:** the `chat` endpoint is throttled via DRF
  `ScopedRateThrottle` (`CHAT_THROTTLE_RATE`, default `30/min`) to bound abuse
  and OpenAI spend.
- **Timeouts / errors:** the OpenAI call is timeout-guarded
  (`OPENAI_TIMEOUT`); any error or empty result degrades to the grounded
  fallback rather than surfacing a stack trace.
- **Grounding:** the model is given only a compact packet of real platform data
  and instructed to never invent values.

## 3. API surface

- Read endpoints are intentionally **public** (`authentication_classes = []`)
  for the prototype. **There is no authentication/authorization yet** — this is
  a known limitation, not a working auth system. Do not expose the deployment
  publicly without adding auth.
- Errors return a **generic envelope** (`{success:false, errors:[...]}`) via a
  custom exception handler; stack traces are not leaked to clients.
- `DEBUG` must be `false` in production; `validate_production_settings()`
  enforces a real `SECRET_KEY`, `DEBUG=false`, a real `DATABASE_URL`, and
  configured `ALLOWED_HOSTS` at startup.

## 4. Data handling

- External content (provider feeds, model output) is treated as untrusted data,
  not instructions.
- Financial values are computed in USD; any INR shown is an approximate,
  labelled display conversion.
- Values unavailable from a source are recorded as `UNKNOWN`, never estimated.

## 5. Docker

- The backend container receives `OPENAI_API_KEY` from the host environment /
  `.env` via `docker-compose.yml` (`OPENAI_API_KEY: ${OPENAI_API_KEY:-}`) — the
  key is not baked into any image.

## 6. Known limitations

- No authentication/RBAC yet (see §3).
- Conversation memory for the chatbot is in-process per worker.
- Rate limiting is per-process (in-memory cache); use a shared cache for
  multi-worker deployments.

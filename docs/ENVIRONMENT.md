# Environment Configuration

**Project:** Vessel — Intelligent Freight Forecasting & Vessel Chartering platform
**Document type:** Environment & Secrets Guide
**Status:** Draft v1.0

How Vessel handles configuration and secrets across the backend and frontend. All configuration comes from environment variables — **no credentials are hard-coded**. See also [DEVELOPMENT_WORKFLOW.md](./DEVELOPMENT_WORKFLOW.md) §12–§13 and [DATA_SOURCES.md](./DATA_SOURCES.md).

---

## 1. How to create your `.env` files

Each service has its own template. Copy the template to a local `.env` (which is git-ignored) and fill in values.

```bash
# Backend
cp backend/.env.example backend/.env

# Frontend
cp frontend/.env.example frontend/.env
```

Then edit each `.env` with your local values.

- `backend/.env.example` and `frontend/.env.example` are **committed** (placeholders only).
- `backend/.env` and `frontend/.env` are **git-ignored** and must never be committed.
- For local convenience the backend also reads a repo-root `.env` as a fallback, but `backend/.env` takes precedence.
- In production, values come from the deployment platform's **secret store**, not from a committed file.

> **Never commit real secrets.** If a secret is ever committed, treat it as compromised: rotate it immediately and remove it from history.

---

## 2. Backend variables

### Mandatory in production

| Variable | Purpose | Dev behaviour |
| --- | --- | --- |
| `SECRET_KEY` | Django cryptographic key. | Falls back to an insecure dev key **only** when `DJANGO_ENV=development`. Production refuses to start without a strong value (≥ 32 chars). Alias: `DJANGO_SECRET_KEY`. |
| `DATABASE_URL` | PostgreSQL/PostGIS connection URL. | If unset, dev/test use local **SQLite**. Production **requires** a non-SQLite URL. |
| `DJANGO_ALLOWED_HOSTS` | Hosts Django will serve. | Defaults to `localhost,127.0.0.1` in dev. Production must list real host(s). |

### Optional (safe defaults)

| Variable | Purpose | Default |
| --- | --- | --- |
| `DJANGO_ENV` | `development` \| `testing` \| `production`. | `development` |
| `DEBUG` | Debug mode. Enforced **false** in production. Alias: `DJANGO_DEBUG`. | `false` |
| `CORS_ALLOWED_ORIGINS` | Comma-separated frontend origins allowed to call the API. | `http://localhost:5173` |

### External data provider keys (all optional — see §5)

| Variable | Provider | Key needed? |
| --- | --- | --- |
| `AISSTREAM_API_KEY` | AISStream (AIS / tracking) | Free, registration required |
| `COMTRADE_API_KEY` | UN Comtrade (trade flows). Alias: `UN_COMTRADE_API_KEY`. | Optional (raises limits) |
| `DATA_GOV_API_KEY` | data.gov.in | Free API key |
| `OPEN_METEO_BASE_URL` / `OPEN_METEO_API_KEY` | Open-Meteo (weather) | **No key needed** on free tier |
| `IMD_BASE_URL` | India Meteorological Department | Endpoint config, if used |
| `BALTIC_EXCHANGE_API_KEY` | Baltic Exchange (freight benchmark) | **Licensed/commercial** — leave unset for the prototype |

---

## 3. Frontend variables

Vite inlines any `VITE_`-prefixed variable into the client bundle at **build time**. Everything here is **public** — never put secrets or private API keys in the frontend.

### Mandatory for a production build

| Variable | Purpose | Dev default |
| --- | --- | --- |
| `VITE_API_BASE_URL` | Base URL of the backend API (baked into the build). | `http://localhost:8000/api/v1` |

### Optional

| Variable | Purpose | Default |
| --- | --- | --- |
| `VITE_MAP_PROVIDER` | `maplibre` (no key) \| `maptiler` \| `mapbox`. | `maplibre` |
| `VITE_MAP_STYLE_URL` | Public map style URL. | provider default |
| `VITE_MAP_API_KEY` | **Public**, domain-restricted map token (only for commercial providers). | unset |

---

## 4. APIs that work without a key

- **Open-Meteo** — free weather API, no key on the free tier. Only set `OPEN_METEO_*` for a commercial/self-hosted endpoint.
- **MapLibre** with a free/open style — renders maps with no token. A key is only needed for commercial map providers (MapTiler/Mapbox), and that token is public (restrict it by domain).
- **UN Comtrade** — has a free public tier usable without a key; a key mainly raises rate limits.
- **World Bank Indicators / Pink Sheet** — open/free (no key), consumed as batch data (see [DATA_SOURCES.md](./DATA_SOURCES.md)).

Keys that **are** required for their integrations: AISStream (free, registration), data.gov.in (free API key). Baltic Exchange is **licensed/commercial**.

---

## 5. How missing credentials are handled

The platform is designed to **degrade gracefully** (NFR-REL-2, NFR-DATA-4):

- **Optional provider keys unset** → that integration is simply **disabled**. The app still starts and runs; features depending on that source are unavailable or fall back to labelled estimated/alternative data. No crash.
- **Mandatory production settings missing/insecure** → the backend **fails fast at startup** with a clear `ImproperlyConfigured` error listing the offending variable **names** (never their values). This prevents an unsafe production boot. See `backend/config/env_validation.py`.
- **Development/testing** → safe defaults keep everything working with zero configuration (SQLite, dev secret key, localhost hosts). Validation is a no-op outside production.
- **Secrets are never logged.** Errors and logs reference variable names only, not values (NFR-SEC-3, DEVELOPMENT_WORKFLOW §15).

### Startup validation summary

`validate_production_settings()` runs on settings import (so `manage.py`, `manage.py check`, gunicorn, and tests all enforce it). When `DJANGO_ENV=production`, it requires:

- `SECRET_KEY` set, not the dev default, ≥ 32 chars;
- `DEBUG` is false;
- `DATABASE_URL` set and not SQLite;
- `DJANGO_ALLOWED_HOSTS` lists real host(s) (not localhost-only).

Outside production it does nothing, so local development stays frictionless.

---

## 6. Rules recap

- All config/secrets via environment variables; **never hard-code credentials**.
- `*.env.example` committed (placeholders); `*.env` git-ignored; never commit real secrets.
- Adding a new variable → update the relevant `.env.example` **and** this document in the same PR (Golden Rule, DEVELOPMENT_WORKFLOW §1).
- Frontend `VITE_*` values are public; keep secrets in the backend only.
- Production must pass startup validation before it boots.

## Related documents

- [DEVELOPMENT_WORKFLOW.md](./DEVELOPMENT_WORKFLOW.md)
- [DATA_SOURCES.md](./DATA_SOURCES.md)
- [ARCHITECTURE.md](./ARCHITECTURE.md)
- [NON_FUNCTIONAL_REQUIREMENTS.md](./NON_FUNCTIONAL_REQUIREMENTS.md)

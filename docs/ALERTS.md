# Alerts & Notifications

**Project:** Vessel — Intelligent Freight Forecasting & Vessel Chartering platform
**Document type:** Feature note
**Status:** v1.0

Detecting decision-relevant conditions and delivering them. Implemented in
`apps/alerts/` (models, generation service, notification foundation) and exposed
at `/api/v1/alerts/`.

## Alert model

An `Alert` records: `alert_type`, `severity` (info/low/medium/high/critical),
`timestamp`, `entity` (+ optional `route`/`port`/`vessel` FKs), `trigger_value`,
`threshold`, `message`, `recommended_action`, `status`, `dedup_key`, and an
explainability `context`. Lifecycle `status`: **NEW → ACKNOWLEDGED → RESOLVED**.

Alerts are deduped on `dedup_key`: while an open (non-resolved) alert with the
same key exists, re-detection **updates it in place** rather than creating a
duplicate. A new alert is created after the prior one is resolved.

## Alert types + documented thresholds

All thresholds are named constants in `apps/alerts/services/generation.py`.

| Type | Fires when | Threshold |
|---|---|---|
| `freight_increase` / `freight_decrease` | freight moves vs a reference | ≥ 5% (HIGH at ≥ 12%) |
| `freight_volatility` | volatility (0..1) | ≥ 0.5 (HIGH at ≥ 0.75) |
| `congestion_increase` | congestion score (0..100) | ≥ 55 (CRITICAL at ≥ 75) |
| `marine_warning` / `cyclone_warning` | warning severity | moderate/high/severe |
| `vessel_scarcity` | availability (0..1) | ≤ 0.30 (HIGH at ≤ 0.15) |
| `eta_delay` | delay probability (0..1) | ≥ 0.6 (HIGH at ≥ 0.8) |
| `port_incompatibility` | vessel incompatible with a port | any (HIGH) |
| `unusual_market_pressure` | market pressure index (0..100) | ≥ 75 or ≤ 25 |

Each detector is a small function taking already-computed inputs (from the
market-pressure / congestion / risk / ETA engines and the observation models),
so alert generation composes existing logic and is easy to test. Each returns
the created/updated `Alert` or `None` (condition not met).

## Notification foundation

`apps/alerts/services/notifications.py` defines a pluggable `Notifier` base with
two channels enabled now:

- **DashboardNotifier** — records that the alert is surfaced on the dashboard
  feed (the dashboard reads alerts via the API).
- **DatabaseNotifier** — persists a `Notification` row (durable in-app inbox).

`dispatch(alert)` delivers through `DEFAULT_NOTIFIERS` (dashboard + database).
A failure in one channel is recorded as a failed `Notification` and never blocks
the others. **No paid/external notification service is required.** Email and push
channels are reserved in the `Notification.Channel` enum and can be added later
by writing another `Notifier` subclass — no schema change needed.

## API

- `GET /api/v1/alerts/` — list (filter `?status=`, `?alert_type=`, `?severity=`;
  paginated, newest-first).
- `GET /api/v1/alerts/{id}/` — retrieve (with its notifications).
- `POST /api/v1/alerts/{id}/acknowledge/` — NEW/ACK → ACKNOWLEDGED (rejects a
  resolved alert).
- `POST /api/v1/alerts/{id}/resolve/` — → RESOLVED.

Responses use the standard success envelope. The endpoints are public read/
lifecycle, consistent with the rest of the API.

# AIS Ingestion — AISStream Adapter

**Project:** Vessel — Intelligent Freight Forecasting & Vessel Chartering platform
**Document type:** Ingestion Adapter Guide
**Status:** Draft v1.0

How the platform ingests live vessel positions from **AISStream** over a
server-side WebSocket, and maps them onto the `Vessel` and `AISPosition` models.
Built on the ingestion framework (see the `apps.ingestion` package and
[ARCHITECTURE.md](./ARCHITECTURE.md) §6). Implementation:
`backend/apps/ingestion/sources/aisstream.py` and `ais_mapping.py`.

---

## 1. Source

- **Provider:** AISStream (`aisstream.io`) — free real-time AIS over WebSocket, registration required (see [DATA_SOURCES.md](./DATA_SOURCES.md) §1).
- **Endpoint:** `wss://stream.aisstream.io/v0/stream`
- **Auth:** a single API key, carried **in the JSON subscribe message** (not an HTTP header). AISStream is WebSocket-only.

## 2. Credentials (backend-only)

- The API key is read **only** from `settings.EXTERNAL_APIS["AISSTREAM_API_KEY"]`, which is sourced from the `AISSTREAM_API_KEY` environment variable (see [ENVIRONMENT.md](./ENVIRONMENT.md)).
- It is **never** hard-coded and **never** exposed to the frontend. It lives entirely in the backend; the React app has no AIS credentials and does not connect to AISStream. (Frontend `VITE_*` variables are public by design; AIS keys are deliberately not among them.)
- Without a key the adapter refuses to connect (`SourceConfigError`) rather than using a placeholder.

## 3. Subscription

The adapter sends this subscribe payload on connect:

```json
{
  "APIKey": "<from AISSTREAM_API_KEY>",
  "BoundingBoxes": [[[5.0, 78.0], [23.0, 95.0]]],
  "FilterMessageTypes": ["PositionReport", "ShipStaticData"]
}
```

The default bounding box frames the Bay of Bengal / East Coast India approaches. It is configurable per session.

## 4. Messages consumed

| AISStream message | Used for | Key fields |
| --- | --- | --- |
| `PositionReport` | dynamic position → `AISPosition` | MMSI, latitude, longitude, SOG, COG, TrueHeading, NavigationalStatus, time |
| `ShipStaticData` | static identity → enrich `Vessel` | MMSI, ImoNumber, Name |

Captured fields (minimum required): **MMSI, IMO (when present), vessel name, latitude, longitude, speed (SOG), course (COG), heading, navigation status, timestamp.** AIS string padding (`@`) is stripped; heading `511` (“not available”) becomes null; navigational-status codes are mapped to labels.

## 5. Mapping to models

### AISPosition (from `PositionReport`)
Each valid position is **upserted** (`update_or_create`) keyed on `(mmsi, timestamp)` — this is the deduplication mechanism, so re-delivered messages don't create duplicates. Stored fields: `mmsi`, `vessel_name`, `latitude`, `longitude`, `sog`, `cog`, `heading`, `nav_status`, `timestamp`, `source="aisstream"`, and `vessel` (the linked `Vessel` if one matches the MMSI, else null).

### Vessel (from `ShipStaticData`)
The adapter does **not** fabricate `Vessel` rows from AIS. The `Vessel` model requires an IMO and physical specifications (DWT/LOA/beam/draft) that AIS does not provide. Instead:
- If a `Vessel` matches the MMSI (or the IMO from static data), its name/IMO are **enriched** where missing.
- If no vessel matches, the static message is a no-op (not an error). The position is still stored, carrying the raw MMSI and name, so nothing is lost.

This is why `AISPosition.vessel` is nullable and the model retains `mmsi`/`vessel_name` directly.

## 6. Robustness (handled cases)

| Case | Behaviour |
| --- | --- |
| **Reconnects** | The sync consume loop reconnects on any stream error/close, up to `max_reconnects` (default 5) with exponential backoff; reconnect count is recorded on the run. |
| **Malformed messages** | Undecodable JSON, unsupported message types, or messages with no MMSI are skipped and counted as `malformed` (never crash the loop). |
| **Duplicate messages** | `update_or_create` on `(mmsi, timestamp)` makes re-delivery idempotent; counted as `duplicate`. |
| **Missing IMO** | Positions are keyed by MMSI; IMO is optional and only applied to a vessel from `ShipStaticData` when present. |
| **Missing vessel** | The position is stored with `vessel=null` plus raw MMSI/name; it is not dropped. |
| **Invalid position** | Out-of-range lat/lon or missing timestamp → skipped, counted as `invalid`. |
| **Logging** | Structured logs under `vessel.ingestion.ais`; no secrets are logged. |

## 7. Run tracking

Each consume session records an `IngestionRun` (`source_key="aisstream"`) with status (`success` / `partial` / `failed`), start/finish timestamps, and counters (fetched, positions written, duplicates, malformed, invalid, reconnects). A session that saw malformed/invalid messages but still wrote data is marked **partial**.

## 8. Running it

The transport uses the `websockets` package (optional dependency in `backend/requirements.txt`), imported lazily — it is only needed to run the live consumer; the rest of the app and the tests do not require it.

Programmatically:

```python
from apps.ingestion.sources.aisstream import AISStreamSource

source = AISStreamSource()          # reads AISSTREAM_API_KEY from settings/env
source.run_session()                # runs until the process is stopped
```

A management command / Celery worker can wrap `run_session()` for deployment (the live consumer is a long-running process, not a scheduled batch).

## 9. Architecture note (sync vs async)

The live WebSocket transport is async, but message **processing writes to the database synchronously**. To keep Django's ORM out of the event loop (and avoid `SynchronousOnlyOperation` / DB-locking issues), the consume loop is synchronous: `connect_sync()` bridges the async socket to a synchronous generator of frames, and each frame is processed inline. Tests inject a plain synchronous iterable of mocked messages, so no socket or event loop is involved.

## 10. Testing

`backend/apps/ingestion/tests/test_aisstream.py` feeds **mocked AISStream messages** through the same processing path (no network, no `websockets`): position creates an `AISPosition` (with and without a matching vessel), duplicate upsert, malformed skip, out-of-range invalid, static-data enrichment, missing-vessel no-op, a full session (→ partial with a malformed message), reconnect-on-error, and credential/subscription checks.

## Related documents

- [DATA_SOURCES.md](./DATA_SOURCES.md)
- [ENVIRONMENT.md](./ENVIRONMENT.md)
- [ARCHITECTURE.md](./ARCHITECTURE.md)
- [NON_FUNCTIONAL_REQUIREMENTS.md](./NON_FUNCTIONAL_REQUIREMENTS.md)

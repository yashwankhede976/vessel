# API Conventions

**Project:** Vessel — Intelligent Freight Forecasting & Vessel Chartering platform
**Document type:** API Conventions & Contract
**Status:** Draft v1.0

Conventions every Vessel API endpoint follows. These are enforced by shared infrastructure in `backend/apps/api/` and DRF configuration in `config/settings.py`, so endpoints get them for free. See also [ARCHITECTURE.md](./ARCHITECTURE.md) §4 (API layer) and [DEVELOPMENT_WORKFLOW.md](./DEVELOPMENT_WORKFLOW.md) §8.

> The domain endpoints themselves are not implemented yet — the routers are scaffolded and empty. This document defines the contract they will follow.

---

## 1. Versioning

- The API is versioned in the URL: **`/api/v1/`**.
- Versioning is **namespace-based** (`rest_framework.versioning.NamespaceVersioning`); the URL namespace `v1` sets `request.version`.
- Current: `v1` (`DEFAULT_VERSION = "v1"`, `ALLOWED_VERSIONS = ["v1"]`).
- **Breaking changes require a new version** (`/api/v2/`) in a new namespace. Additive, backwards-compatible changes stay within the current version.

## 2. URL & resource conventions

- Resource-oriented, plural nouns, kebab-case: e.g. `/api/v1/ports/`, `/api/v1/cargo/cargo-requirements/`, `/api/v1/freight/freight-observations/`.
- Domain modules under `/api/v1/`: `ports`, `vessels`, `cargo`, `freight`, `weather`, `forecasts`, `optimization`, `recommendations`, `alerts`.
- Correct HTTP verbs: `GET` (read, side-effect free), `POST` (create), `PUT`/`PATCH` (update), `DELETE` (remove).
- Endpoints are registered on DRF routers per domain, so list/detail routes are consistent.

## 3. Consistent response structure

Every response uses a stable envelope, applied automatically by `EnvelopeJSONRenderer`.

### Success (single object or arbitrary payload)

```json
{
  "success": true,
  "data": { "id": 1, "name": "Paradip" },
  "errors": null
}
```

### Success (paginated list)

```json
{
  "success": true,
  "data": [ { "id": 1 }, { "id": 2 } ],
  "pagination": {
    "count": 123,
    "page": 2,
    "page_size": 25,
    "num_pages": 5,
    "next": "https://host/api/v1/ports/?page=3",
    "previous": "https://host/api/v1/ports/?page=1"
  },
  "errors": null
}
```

### Error

```json
{
  "success": false,
  "data": null,
  "errors": [
    { "code": "required", "detail": "This field is required.", "field": "name" }
  ]
}
```

Rules:
- `success` is always present (boolean).
- On success, `data` holds the payload and `errors` is `null`.
- On error, `data` is `null` and `errors` is a non-empty list.
- `pagination` appears only on paginated list responses.

## 4. Errors & exception handling

Handled centrally by `apps.api.exceptions.exception_handler`.

- DRF/validation errors are normalized into a list of `{ "code", "detail", "field?" }` items.
  - `code` — machine-readable (e.g. `required`, `invalid`, `not_found`, `method_not_allowed`, `permission_denied`, `throttled`).
  - `detail` — human-readable message.
  - `field` — included for field-specific validation errors; omitted for non-field/`detail` errors.
- **HTTP status codes are meaningful** and set on the response (e.g. `400`, `401`, `403`, `404`, `405`, `429`, `500`).
- **Unhandled exceptions** are logged server-side and returned as a generic `500` with `{ "code": "server_error" }` — **no stack traces, internals, or secrets are ever leaked** to clients (NFR-SEC; DEVELOPMENT_WORKFLOW §14).

Example (validation, `400`):

```json
{
  "success": false,
  "data": null,
  "errors": [
    { "code": "required", "detail": "This field is required.", "field": "quantity_tonnes" },
    { "code": "invalid", "detail": "Enter a valid date.", "field": "laycan_start" }
  ]
}
```

> Note: a request to a URL that matches **no route** produces a Django-level `404` that does not pass through the DRF handler (so it is not enveloped). Errors raised **within** DRF views/routers (validation, 404 on a missing object, 405, 403, etc.) always use the envelope above.

## 5. Pagination

Provided by `apps.api.pagination.StandardPagination` (page-number pagination).

- Default page size: **25**. Max page size: **200**.
- Query params:
  - `page` — page number (1-based).
  - `page_size` — override page size, capped at 200.
- The `pagination` block (see §3) carries `count`, `page`, `page_size`, `num_pages`, `next`, `previous`.

```
GET /api/v1/ports/?page=2&page_size=50
```

## 6. Filtering

Backed by `django_filters.rest_framework.DjangoFilterBackend`.

- Endpoints declare which fields are filterable (`filterset_fields` or a `FilterSet`).
- Filters are applied as query params, e.g. `?country=India`, `?vessel_type=capesize`.
- Combine filters with pagination and ordering freely.

```
GET /api/v1/vessels/?vessel_type=panamax&flag=Panama
```

## 7. Ordering

Backed by `rest_framework.filters.OrderingFilter`.

- `ordering` query param; prefix a field with `-` for descending.
- Endpoints declare `ordering_fields` (allow-list) and a default `ordering`.

```
GET /api/v1/freight/freight-observations/?ordering=-observed_on
GET /api/v1/ports/?ordering=name
```

## 8. Search

Backed by `rest_framework.filters.SearchFilter`.

- `search` query param performs a text search over an endpoint's declared `search_fields`.

```
GET /api/v1/vessels/?search=paradip
```

## 9. Serializer conventions

- One serializer per resource representation; name as `<Model>Serializer` (e.g. `PortSerializer`). Use a separate write/`Create`/`Update` serializer when input and output differ.
- **Field naming:** `snake_case` in payloads, matching model fields.
- **Types:** timestamps are ISO-8601 with timezone (UTC unless a field is explicitly local); **monetary values are strings-or-numbers from `DecimalField`** (never lossy floats) — see the data-model docs; currency is a separate field.
- **Validation** lives in serializers (and model validators); invalid input yields the `400` error envelope (§4).
- **Read-only fields:** `id`, `created_at`, `updated_at`, and any derived/model-computed fields.
- **No business logic in serializers** — they validate and shape only; business rules live in the domain layer (ARCHITECTURE §3, §4).
- **Explainability payloads:** recommendation/forecast serializers expose drivers/confidence/assumptions produced server-side; clients render them (FR-XAI).

## 10. Authentication & authorization

- Endpoints are authenticated by default; role-based permissions are enforced server-side (NFR-SEC-2). The `health` endpoint is a public exception (liveness).
- Sensitive endpoints are throttled; throttling errors return `429` with `code: throttled`.

## 11. Content types

- Requests and responses are JSON (`application/json`). The default parser is `JSONParser`.
- In development (`DEBUG=True`) the DRF Browsable API renderer is also enabled for convenience; production serves JSON only.

## 12. API documentation (OpenAPI)

Generated by **drf-spectacular** from the code (schema-first-from-code).

| Route | Purpose |
| --- | --- |
| `/api/v1/schema/` | OpenAPI 3 schema (YAML/JSON). |
| `/api/v1/docs/` | Swagger UI (interactive). |
| `/api/v1/redoc/` | ReDoc (reference reading view). |

- Endpoints should be annotated with `@extend_schema` (summary, description, request/response, examples) so the generated docs are accurate.
- **The API reference is kept current with the API**: any endpoint change updates its annotations in the same PR (DEVELOPMENT_WORKFLOW §1, §8).
- Generate the schema file locally with `python manage.py spectacular --file schema.yml` (should produce 0 warnings/0 errors).

## 13. Health / meta endpoint

- `GET /api/v1/health/` — liveness probe; no auth. Returns the standard envelope:

```json
{ "success": true, "data": { "status": "ok", "service": "vessel-backend", "environment": "development" }, "errors": null }
```

## 14. Where this is implemented

| Concern | Location |
| --- | --- |
| Versioning, pagination default, filter backends, exception handler, schema class | `backend/config/settings.py` (`REST_FRAMEWORK`, `SPECTACULAR_SETTINGS`) |
| Response envelope | `backend/apps/api/renderers.py` (`EnvelopeJSONRenderer`) |
| Error normalization | `backend/apps/api/exceptions.py` (`exception_handler`) |
| Pagination | `backend/apps/api/pagination.py` (`StandardPagination`) |
| URL aggregation + docs routes | `backend/apps/api/v1/urls.py` |
| Domain routers (scaffold) | `backend/apps/api/v1/<domain>/urls.py` |
| Version namespace mount | `backend/config/urls.py` |

## Related documents

- [ARCHITECTURE.md](./ARCHITECTURE.md)
- [DEVELOPMENT_WORKFLOW.md](./DEVELOPMENT_WORKFLOW.md)
- [FUNCTIONAL_REQUIREMENTS.md](./FUNCTIONAL_REQUIREMENTS.md)
- [NON_FUNCTIONAL_REQUIREMENTS.md](./NON_FUNCTIONAL_REQUIREMENTS.md)

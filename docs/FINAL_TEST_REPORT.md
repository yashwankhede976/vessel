# Final Test Report

Honest, verified state of the Vessel platform for the SIH demo. Numbers below
were produced by actually running the suites and a live Docker bring-up on
macOS. Nothing here is aspirational — where something is not verified, it says
so.

Data in the product is labelled by nature: **REAL** (stored/observed),
**FORECAST** (model prediction), **ESTIMATED** (derived/heuristic), or
**SYNTHETIC** (generated for demo/seed).

---

## 1. Tests passed / failed

| Suite | Command | Result |
| --- | --- | --- |
| Backend (Django + DRF) | `cd backend && .venv/bin/python -m pytest -q` | **478 passed**, 0 failed (3 warnings) |
| Frontend (Vitest) | `cd frontend && npm test` | **21 passed**, 0 failed (8 test files) |
| Frontend types | `cd frontend && npx tsc -b` | **clean** (exit 0) |
| ML — leakage | `cd ml && PYTHONPATH=. .venv/bin/python features/test_leakage.py` | **11 passed** |
| ML — dataset builder | `cd ml && PYTHONPATH=. .venv/bin/python datasets/test_builder.py` | **7 passed** |
| ML — baselines | `cd ml && PYTHONPATH=. .venv/bin/python models/test_baseline.py` | **10 passed** |
| ML — uncertainty | `cd ml && PYTHONPATH=. .venv/bin/python models/test_uncertainty.py` | **9 passed** |
| ML — GBM forecast | `cd ml && PYTHONPATH=. .venv/bin/python models/test_freight_gbm.py` | **6 passed** |
| **ML total** | | **43 passed**, 0 failed |

Migration/consistency checks (backend):

- `python manage.py makemigrations --check` — no missing migrations.
- `python manage.py check` — no issues.

The 3 backend warnings are `DeprecationWarning`s emitted by the OR-Tools
(`ortools`/SWIG) import in the optimization tests. They are third-party and do
not affect results.

---

## 2. Docker status

Command: `docker compose -f docker/docker-compose.yml up --build`

Verified live: all three services start and communicate.

| Service | Status | Notes |
| --- | --- | --- |
| `db` (PostGIS) | healthy | compose healthcheck gates the backend via `depends_on: condition: service_healthy` |
| `backend` (Django/gunicorn) | up | entrypoint runs `migrate` + `seed_ports` (7 ports seeded), then gunicorn |
| `frontend` (static SPA) | up (HTTP 200) | served on the mapped port |

Verified through Docker: `GET /api/v1/health/`, `POST /api/v1/decision/`, and the
data-freshness endpoint all respond; the frontend serves and reaches the
backend.

Defects fixed to make Docker work (real defects, not rebuilds):

1. **No migrations on startup.** Added `docker/backend-entrypoint.sh`
   (`migrate` → `seed_ports` → gunicorn), wired into `docker/backend.Dockerfile`.
2. **Missing Postgres driver.** Added `psycopg[binary]==3.2.3` to
   `backend/requirements.txt` (modern driver matching Django 5).
3. Added pip `--timeout 120 --retries 5` for network resilience, a db
   healthcheck, and `USE_POSTGIS` wiring in compose.

---

## 3. Verified end-to-end workflow

`POST /api/v1/decision/` — 100,000 MT coal, Australia → Paradip. All of the
following fields are present and grounded in backend output (not invented):

- Freight forecast band + working rate (FORECAST)
- Recommended vessel + suitability score (ESTIMATED)
- Berth/vessel compatibility (REAL rules over SYNTHETIC/seed vessels)
- Port congestion score (ESTIMATED)
- ETA with delay probability (ESTIMATED)
- Demurrage exposure (ESTIMATED)
- Total landed cost (ESTIMATED)
- Recommended contract strategy (ESTIMATED)
- Risk score + level (ESTIMATED)
- Timing decision: FIX_NOW / WAIT / PARTIAL_FIX / MONITOR (ESTIMATED)
- Expected savings (ESTIMATED)
- Explainability: reasons, positive/negative factors, model versions, data
  freshness

Two real defects were found and fixed in
`backend/apps/decisions/services/decision_engine.py` during verification:

1. The freight band was silently empty when the recommended vessel's type did
   not match the forecast's vessel type — added a lane-level band fallback
   (`_lane_freight_band`). Covered by a new regression test
   (`test_lane_freight_band_fallback_when_type_mismatch`).
2. `total_landed_cost` showed `$0` despite a known working rate — it now
   recomputes via the existing `compute_voyage_economics` when the composed
   cost is zero.

---

## 4. Known limitations (do not overclaim)

- **No authentication / authorization yet.** API read endpoints are
  intentionally public (`authentication_classes = []`). This is a documented
  limitation, not a working auth system. Do not demo "secure login."
- **SYNTHETIC / seed data.** Vessels, some rates, and lane parameters used in
  the demo are seeded/synthetic. Forecast values are **model output**, not
  measured market prices.
- **Provider ingestion is partial.** Live external ingestion beyond the
  AISStream adapter is not wired for the demo; the workflow runs on
  seeded/synthetic inputs.
- **ETA / demurrage / risk are ESTIMATED.** They come from deterministic
  heuristics and models, not from a live operational feed.
- **Backend local venv is Python 3.14; Docker image is Python 3.12-slim.**
  Tests pass on both, but treat Python 3.12 as the supported target.

---

## 5. Files changed (this stabilization pass)

- `backend/apps/decisions/services/decision_engine.py` — freight-band fallback +
  landed-cost recompute (+ imports and `_is_zero` helper).
- `backend/apps/decisions/tests/` — regression test for the band fallback.
- `backend/requirements.txt` — added `psycopg[binary]==3.2.3`; pip timeout/retries.
- `docker/backend-entrypoint.sh` — new startup script (migrate + seed + gunicorn).
- `docker/backend.Dockerfile` — use the entrypoint script.
- `docker/docker-compose.yml` — db healthcheck, `depends_on: service_healthy`,
  `USE_POSTGIS`.
- `frontend/src/pages/DashboardPage.tsx` — surface Port Risk, Vessel
  Recommendation, and Expected Savings tiles from the composed decision.
- `frontend/src/__tests__/routing.test.tsx` — mock the new `decision` API.
- `README.md`, `docs/README.md` — corrected stale "scaffold only" status.
- `docs/SIH_DEMO_CHECKLIST.md`, `docs/FINAL_TEST_REPORT.md`,
  `docs/SIH_INNOVATION_POINTS.md` — new demo docs.

---

## 6. How to reproduce

```bash
# Backend
cd backend && .venv/bin/python -m pytest -q
.venv/bin/python manage.py makemigrations --check
.venv/bin/python manage.py check

# Frontend
cd frontend && npm test && npx tsc -b

# ML
cd ml
for f in features/test_leakage.py datasets/test_builder.py \
         models/test_baseline.py models/test_uncertainty.py \
         models/test_freight_gbm.py; do
  PYTHONPATH=. .venv/bin/python "$f"
done

# Docker
docker compose -f docker/docker-compose.yml up --build
```

# SIH Demo Checklist

A tight, honest run-through for demoing Vessel. Follow top to bottom. Every
claim here is backed by something you can show live. Where a value is a
forecast/estimate/seed, say so — the UI labels it **REAL / FORECAST /
ESTIMATED / SYNTHETIC**.

---

## 0. Before the demo (5 min)

- [ ] Docker Desktop running.
- [ ] From the repo root: `docker compose -f docker/docker-compose.yml up --build`
- [ ] Wait for: db **healthy**, backend logs show `migrate` + `seed_ports`
      (7 ports) then gunicorn, frontend serving.
- [ ] Health check: open `http://localhost:8000/api/v1/health/` → `{"status":"ok",...}`
- [ ] Frontend: open the mapped frontend URL; the dashboard loads.

If Docker is unavailable, run locally instead:

```bash
# terminal 1
cd backend && .venv/bin/python manage.py migrate && \
  .venv/bin/python manage.py seed_ports && \
  .venv/bin/python manage.py runserver 8000
# terminal 2
cd frontend && npm run dev
```

---

## 1. The one-command story: the unified decision (2 min)

This is the headline. One endpoint composes the whole workflow.

```bash
curl -s -X POST http://localhost:8000/api/v1/decision/ \
  -H 'Content-Type: application/json' \
  -d '{"commodity":"coal","cargo_quantity":"100000","origin":"Australia","destination":"Paradip","laycan_start":"2026-09-15","laycan_end":"2026-09-30"}' | python3 -m json.tool
```

Point out in the response:

- [ ] `freight_forecast` — band (low/mid/high) + working rate. **FORECAST.**
- [ ] `recommended_vessel` — name, type, suitability score. **ESTIMATED.**
- [ ] `compatibility` — berth/draft rules applied (incompatible vessels excluded).
- [ ] `congestion.score` — destination-port congestion. **ESTIMATED.**
- [ ] `eta` — arrival + delay probability. **ESTIMATED.**
- [ ] `demurrage` — exposure. **ESTIMATED.**
- [ ] `total_landed_cost` — full cost (verified non-zero). **ESTIMATED.**
- [ ] `recommended_contract` — spot vs short-term vs multi-voyage. **ESTIMATED.**
- [ ] `risk` — overall score + level (LOW/MEDIUM/HIGH). **ESTIMATED.**
- [ ] `timing_decision` — FIX_NOW / WAIT / PARTIAL_FIX / MONITOR.
- [ ] `expected_savings` — vs. worst-case action.
- [ ] `explainability` — reasons, positive/negative factors, model versions,
      and `data_freshness`.

Talking point: *"Every number is grounded in a backend engine and labelled by
nature. Nothing is invented at the UI."*

---

## 2. The dashboard: what's happening / what will happen / what to do (3 min)

Open the dashboard. Confirm all of these are immediately visible:

- [ ] **Data freshness** strip at the top.
- [ ] Headline **FIX / WAIT / PARTIAL FIX / MONITOR** decision card with
      expected savings, risk, confidence, and reasons.
- [ ] **Current freight** (REAL where available).
- [ ] **Market pressure** index (ESTIMATED).
- [ ] **Port risk** score + level (ESTIMATED).
- [ ] **Vessel recommendation** — name + type + suitability (ESTIMATED).
- [ ] **Recommended strategy** (contract recommendation).
- [ ] **Expected savings** (ESTIMATED).
- [ ] **Freight rate forecast** chart with confidence band (FORECAST).
- [ ] New alerts panel + East Coast India fleet map.

Talking point: *"The dashboard answers three questions in one screen — what is
happening, what will happen, and what should I do — for the Australia → Paradip
lane."*

---

## 3. The grounded assistant (1 min)

```bash
curl -s -X POST http://localhost:8000/api/v1/decision/assistant/ \
  -H 'Content-Type: application/json' \
  -d '{"question":"should I fix now or wait?"}' | python3 -m json.tool
```

- [ ] `answer` is generated from real engine output.
- [ ] `grounded: true` and `data` shows the values it used.

Talking point: *"It answers from backend data — it will not invent a number it
cannot compute."*

---

## 4. Explainability & vessel recommendation depth (2 min)

- [ ] Show `ranked_vessels` and `excluded_vessels` in the decision response —
      incompatible vessels are excluded automatically with a `reason`.
- [ ] Show the `POST /api/v1/recommendations/vessels/` endpoint returning ranked
      candidates and vessel-type rankings, each with compatibility, estimated
      freight, ETA, demurrage, risk, suitability, and estimated total cost.

---

## 5. Honesty slide (30 sec) — say this out loud

- [ ] API read endpoints are **public** — no auth/RBAC yet (documented
      limitation).
- [ ] Vessels and some inputs are **SYNTHETIC/seed** data; forecasts are
      **model output**, not measured prices.
- [ ] ETA / demurrage / risk are **ESTIMATED** from heuristics/models.

See `docs/FINAL_TEST_REPORT.md` for the full verified state.

---

## 6. Proof it works (optional, 1 min)

```bash
cd backend && .venv/bin/python -m pytest -q      # 478 passed
cd frontend && npm test                          # 21 passed
```

---

## Teardown

```bash
docker compose -f docker/docker-compose.yml down
```

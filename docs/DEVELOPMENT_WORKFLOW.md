# Development Workflow

**Project:** Intelligent Freight Forecasting Model for Optimized Vessel Chartering and Bulk Cargo Procurement from Overseas to the East Coast of India
**Codename:** Vessel
**Document type:** Development Workflow & Engineering Standards
**Status:** Draft v1.0

This document defines how the team builds Vessel: branching, commits, reviews, coding standards, testing, environments, and the rules that keep the codebase, data, and documentation consistent. It applies to the stack defined in [ARCHITECTURE.md](./ARCHITECTURE.md) (React/TypeScript frontend; Django/DRF backend; Python ML & optimization; PostgreSQL/PostGIS). No application code is defined here.

---

## 1. Golden rule — documentation follows the code

> **Every implemented feature must update the relevant documentation in the same pull request.**

A feature is not "done" until its documentation is updated. Concretely:

- A new/changed capability updates [FUNCTIONAL_REQUIREMENTS.md](./FUNCTIONAL_REQUIREMENTS.md).
- A new/changed data source updates [DATA_SOURCES.md](./DATA_SOURCES.md).
- An architectural change (new layer boundary, new service, new flow) updates [ARCHITECTURE.md](./ARCHITECTURE.md).
- A new/changed API endpoint updates the API reference (see §7).
- A new environment variable updates `.env.example` and the env-var docs (see §12).
- A new term updates [GLOSSARY.md](./GLOSSARY.md).
- An ML model change updates the model/experiment records (see §10).

PR review **must** reject changes that add or alter behaviour without the corresponding documentation update (see §4). This is enforced in the PR checklist.

---

## 2. Branch strategy

A trunk-based flow with short-lived branches off `main`.

- **`main`** — always releasable; protected. No direct pushes. Merges only via reviewed PR with green CI.
- **`develop`** *(optional)* — integration branch if the team needs a staging line before `main`; the same protections apply. Teams may run trunk-only (`main` + feature branches) to keep it simple for SIH.
- **Feature branches** — branch from `main` (or `develop`), one branch per unit of work, short-lived (aim to merge within days).

### Branch naming

`<type>/<short-kebab-description>` and, where a tracker is used, include the issue id:

```
feat/freight-forecast-endpoint
feat/123-laycan-optimizer
fix/eta-timezone-offset
chore/ci-lint-python
docs/data-sources-baltic
ml/xgboost-freight-baseline
refactor/domain-landed-cost
```

Types mirror the commit types in §3. Delete branches after merge. Never commit directly to `main`/`develop`. Never force-push shared branches.

---

## 3. Commit conventions

Use **Conventional Commits**: `type(scope): summary`.

```
feat(api): add freight forecast endpoint
fix(eta): correct IST vs UTC handling in arrival estimate
docs(architecture): document optimization boundary
ml(forecast): add LightGBM baseline for AU-PARADIP lane
chore(deps): pin Django and DRF versions
refactor(domain): extract landed-cost calculator
test(laycan): add demurrage-risk edge cases
perf(ingest): batch AIS position upserts
```

Rules:

- **Types:** `feat`, `fix`, `docs`, `refactor`, `test`, `chore`, `perf`, `build`, `ci`, `ml` (ML experiments/models), `data` (dataset/versioning changes).
- **Scope:** the layer/module (`api`, `domain`, `ingest`, `ml`, `opt`, `web`, `db`, `forecast`, `laycan`, etc.).
- **Summary:** imperative mood, lowercase, no trailing period, ≤ ~72 chars.
- **Body (optional):** what and why, not how. Reference issues (`Refs #123`, `Closes #123`).
- **Breaking changes:** add `!` (`feat(api)!: ...`) and a `BREAKING CHANGE:` footer.
- Commit in **logical, self-contained** units. Do not mix unrelated changes. Keep code and its doc updates in the same PR (they may be separate commits).

---

## 4. Pull-request workflow

1. Open a PR from your feature branch into `main` (or `develop`). Keep PRs small and focused.
2. Fill the PR description: what changed, why, how tested, screenshots for UI, and **which docs were updated**.
3. CI must pass: lint, type-check, tests, migrations check, build (see §11).
4. At least **one reviewer approval** required (two for changes to auth, data handling, migrations, or the ML↔Django boundary).
5. Resolve all review threads. No unresolved conversations at merge.
6. **Squash-merge** by default (clean history); the squash message follows Conventional Commits. Delete the branch on merge.

### PR checklist (required)

- [ ] Conventional-commit title.
- [ ] Tests added/updated and passing.
- [ ] Lint + type-check pass.
- [ ] **Relevant documentation updated (Golden Rule §1).**
- [ ] Migrations included and reviewed (if models changed) — see §8.
- [ ] `.env.example` updated (if new env vars) — no real secrets — see §12.
- [ ] No secrets, credentials, tokens, or real datasets committed.
- [ ] Backwards-compatibility / breaking changes noted.
- [ ] ML changes: experiment recorded, metrics reported (if `ml`/model change) — see §10.

Reviewers must **block** a PR that changes behaviour without the corresponding documentation update.

---

## 5. Coding standards (all languages)

- **Clarity over cleverness.** Small functions, meaningful names, early returns, minimal nesting.
- **Respect layer boundaries** ([ARCHITECTURE.md](./ARCHITECTURE.md) §12): API ↔ domain ↔ (ingest/ML/opt) ↔ data; no upward calls, no layer-skipping. ML/optimization stay pure (no Django/ORM/request objects leaking in).
- **No dead code, no commented-out blocks** merged to `main`.
- **Formatting/linting is automated** and enforced in CI; do not hand-fight the formatter.
- **Type everything** that can be typed (TypeScript types; Python type hints).
- **Handle errors explicitly** (§14); log meaningfully (§15).
- **Configuration via environment** (§12), never hard-coded secrets or endpoints.
- Prefer well-known, actively maintained dependencies; pin versions (§12/§11).

### Python (backend, ML, optimization)

- Target a single supported Python version (pinned in project config).
- **Formatter:** Black. **Import order:** isort. **Lint:** Ruff (or flake8). **Types:** mypy on domain/ML/optimization modules.
- PEP 8 naming; docstrings on public functions/classes/modules.
- Use type hints throughout; avoid `Any` in domain/ML interfaces.
- Dependency management via a lockfile (e.g. `requirements*.txt` pinned, or Poetry/pip-tools). Separate prod vs dev deps.

---

## 6. Frontend standards (React + TypeScript)

- **TypeScript strict mode** on. No implicit `any`. Prefer explicit prop and API types generated from / matching the API contract.
- **Component architecture:** feature-based folders; small, focused, reusable components; presentational vs container separation where useful; hooks for data-fetching and side effects.
- **Routing:** React Router; route-level code-splitting for heavy views (maps, analytics).
- **State:** server state via a data-fetching/caching library; local UI state kept local. Avoid a global store for server data.
- **Styling:** one agreed approach (CSS modules / utility framework / styled system) applied consistently; no ad-hoc inline styles for shared patterns.
- **Charts & maps:** use the chosen charting and map libraries via thin wrapper components; never leak vendor APIs across the app. Render server-provided explainability payloads; do not recompute confidence/drivers on the client.
- **Formatter/lint:** Prettier + ESLint (TypeScript + React + hooks rules), enforced in CI.
- **Accessibility:** semantic HTML, keyboard navigation, sufficient contrast, labelled controls (NFR-USE-3). Full WCAG conformance needs separate manual/AT testing.
- **Units & time:** display currency, per-tonne/per-voyage units, and time zones unambiguously (NFR-USE-4); ETAs show the zone.
- **Tests:** component/unit tests (e.g. Testing Library) for logic and key views; avoid brittle snapshot-only tests.

---

## 7. Django standards

- **Project structure:** Django apps aligned to bounded contexts (e.g. `catalog`/reference data, `voyages`, `recommendations`, `ingestion`, `risk`). Keep **business logic in the domain/service layer**, not in views or serializers.
- **Views:** thin. DRF views/viewsets handle transport, permissions, and (de)serialization; they call domain services and return results. No ML/optimization calls or business rules in views (ARCHITECTURE §4).
- **Serializers:** validate and shape; no business decisions.
- **Domain services:** plain Python service modules/classes; the only place business policy lives; orchestrate ML/optimization via their typed interfaces.
- **ML/optimization isolation:** live in separate packages, imported by the domain layer only. No Django imports inside ML/optimization code.
- **ORM:** use the ORM; avoid N+1 (`select_related`/`prefetch_related`); push spatial work to PostGIS via GeoDjango. Keep raw SQL rare, reviewed, and parameterized.
- **Settings:** split settings per environment (§13); all secrets/config from environment (§12). `DEBUG=False` outside development.
- **Security:** DRF authentication + role-based permissions (NFR-SEC-2); never disable CSRF/security middleware without justification; treat external data as untrusted (NFR-SEC-5).
- **Async/long tasks:** ingestion, training, batch scoring, and heavy optimization run on the task queue (Celery/beat), not in the request path.

---

## 8. API standards

- **Style:** RESTful JSON over HTTPS. Resource-oriented URLs, plural nouns (`/api/v1/vessels`, `/api/v1/recommendations`).
- **Versioning:** URL-versioned (`/api/v1/`). Breaking changes require a new version.
- **HTTP semantics:** correct verbs (GET/POST/PUT/PATCH/DELETE) and status codes; GET is side-effect free.
- **Requests/responses:** documented schemas; consistent field casing; ISO-8601 timestamps with timezone; explicit units and currency.
- **Pagination/filtering/sorting:** standard, documented query params; paginate list endpoints.
- **Errors:** consistent error envelope (code, message, details) — see §14. Never leak stack traces or secrets to clients.
- **Explainability:** recommendation endpoints return drivers/confidence/assumptions payloads (FR-XAI); the client renders them.
- **AuthN/Z:** authenticated by default; role-based access enforced server-side; sensitive endpoints throttled.
- **Contract & docs:** maintain an API reference (OpenAPI/schema). **Any endpoint change updates the API docs in the same PR (§1).**

---

## 9. Database migration rules

- **All schema changes go through Django migrations.** No manual, out-of-band schema edits to any shared environment.
- **Migrations are committed** with the model change in the same PR and reviewed.
- **One logical change per migration**; give data migrations clear names.
- **Backwards-compatible by default:** prefer additive changes. For destructive changes (drop/rename), use a phased approach (add → backfill → switch → remove) to avoid downtime; call out destructive migrations explicitly in the PR.
- **PostGIS:** spatial columns/indexes via GeoDjango migrations; review spatial index choices.
- **Reversibility:** migrations should be reversible where feasible; note when they are not.
- **No data loss without explicit sign-off.** Destructive or bulk-data migrations require reviewer approval and a note on reversibility (aligns with safety practices).
- **CI check:** `makemigrations --check` must show no missing migrations; migrations must apply cleanly on a fresh test database.
- **Seed/reference data** (ports, berths, lanes) managed via reviewed data migrations or documented fixtures, with effective dates (FR-PB-3).

---

## 10. ML experiment rules

ML lives in its own layer with a strict boundary from Django (ARCHITECTURE §12). Experiments must be reproducible and recorded.

- **Reproducibility:** fixed random seeds; pinned library versions; recorded feature set, data snapshot/version (§ dataset versioning), and hyperparameters.
- **Experiment tracking:** every experiment records inputs (dataset version, features), model type/params, metrics, and artifacts. Use an experiment tracker or, at minimum, a committed experiment log/registry entry. `ml`-type commits/PRs must include the metrics summary.
- **Evaluation:** report the agreed metrics (e.g. MAPE for freight forecasts — NFR-ACC-1) on a held-out/temporal validation split; never evaluate on training data. Compare against a baseline (e.g. statsmodels seasonal baseline).
- **Confidence:** models must emit uncertainty/confidence and driver attributions (feature importance / SHAP-style) for explainability (NFR-XAI, NFR-ACC-2).
- **Model registry & versioning:** every model artifact is versioned; predictions carry the model version (NFR-ACC-3). Record which model version is promoted to each environment.
- **Promotion:** a model is promoted to production only after meeting the agreed metric threshold and review. Record forecast-vs-realized for ongoing evaluation (NFR-ACC-4).
- **Boundaries:** no business rules or thresholds inside models; those belong to the domain layer. No large model binaries in Git — use artifact storage referenced by version (see §ignored files).

---

## 11. Dataset versioning

- **Datasets are versioned and immutable per version.** Reference data by version, never "latest mutable file", so experiments are reproducible.
- **Provenance:** each dataset/version records source (see [DATA_SOURCES.md](./DATA_SOURCES.md)), pull date, access classification, and any transformations (NFR-DATA-3).
- **Storage:** raw and processed datasets live in artifact/object storage (or a data-version tool such as DVC), **not** in Git. Git holds only small, licence-cleared reference data and the manifests/pointers.
- **Licensing:** never commit licensed/commercial data (e.g. Baltic Exchange) to the repo. Prototype freight labels use a lawful public proxy or clearly-labelled synthetic/curated data (see [DATA_SOURCES.md](./DATA_SOURCES.md)).
- **Manifests:** a committed manifest maps dataset version → location + checksum, so a given experiment/model can be tied to exact data.
- **CSV/XLSX imports:** tagged with source and effective date; estimated/manual data flagged as non-authoritative (NFR-DATA-4).

---

## 12. Environment variable rules

- **All configuration and secrets come from environment variables** (or a secret manager), never hard-coded (NFR-SEC-3). This includes database URLs, API keys (AISStream, data.gov.in, UN Comtrade, etc.), broker URLs, and feature flags.
- **`.env.example` (committed):** the authoritative list of every required variable with **placeholder** values and a short comment. It documents *what* is needed, never real values.
- **`.env` (never committed):** each developer's real local values. **`.env` is git-ignored.** Production secrets come from the deployment platform's secret store, not a file in the repo.
- **Rule:** adding a new variable requires updating `.env.example` (and env docs) in the same PR (§1). CI/startup should fail fast if a required variable is missing.
- **Never commit real secrets.** If a secret is ever committed, treat it as compromised: rotate it immediately and purge it from history. A secret scanner should run in CI/pre-commit.
- **Separation:** each environment (§13) has its own values and credentials; never share production secrets with development/testing.

### `.env.example` (illustrative placeholders — not real values)

```
# Django
DJANGO_ENV=development
DJANGO_SECRET_KEY=changeme-generate-a-strong-key
DJANGO_DEBUG=true
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1

# Database (PostgreSQL / PostGIS)
DATABASE_URL=postgres://vessel:changeme@localhost:5432/vessel

# Task queue / broker
CELERY_BROKER_URL=redis://localhost:6379/0

# External data providers (obtain your own keys)
AISSTREAM_API_KEY=your-aisstream-key
DATA_GOV_IN_API_KEY=your-data-gov-in-key
UN_COMTRADE_API_KEY=your-comtrade-key
# BALTIC_EXCHANGE_API_KEY=licensed-do-not-commit

# AI chatbot (OpenAI) — BACKEND ONLY, never exposed to React. Optional:
# if unset the chatbot falls back to a grounded rule-based answer.
OPENAI_API_KEY=
# OPENAI_MODEL=gpt-4o-mini

# Frontend
VITE_API_BASE_URL=http://localhost:8000/api/v1
```

### AI chatbot setup

- Put your real `OPENAI_API_KEY` **only** in `backend/.env` (or the deployment
  secret store). Never in `frontend/.env`, never in a `VITE_*` variable, never
  committed. See [SECURITY.md](./SECURITY.md).
- The endpoint is `POST /api/v1/chat/` (see [CHATBOT.md](./CHATBOT.md)).
  Without a key it still works via a grounded fallback.
- Docker: `docker-compose.yml` passes `OPENAI_API_KEY` from the host env to the
  backend container; the key is not baked into any image.

---

## 13. Development environments

Three environments, isolated in data, credentials, and configuration (NFR-DEP-2).

| Environment | Purpose | Key settings |
| --- | --- | --- |
| **development** | Local engineering: build features, run the SPA + API + DB locally. | `DJANGO_DEBUG=true`; local Postgres/PostGIS; may use sample/synthetic data and mocked feeds; verbose logging (§15). |
| **testing** | Automated tests and CI; also a shared QA/staging line. | `DEBUG=false`; disposable/ephemeral test database migrated fresh; no real production secrets; deterministic seeds; test doubles for external providers. |
| **production** | Live system for real users. | `DEBUG=false`; managed Postgres/PostGIS; secrets from the platform secret store; strict security, monitoring, backups; no debug endpoints. |

Rules:

- Config differences come from environment variables/settings modules, **not** code forks.
- Production data and secrets never flow to development/testing.
- Migrations are applied through the pipeline, not manually, in testing/production (§9).
- Model promotion to production follows §10.

---

## 14. Error-handling rules

- **Fail explicitly and meaningfully.** No silent excepts; never swallow exceptions without handling or logging.
- **Use specific exceptions**, not bare `except:`; catch the narrowest exception you can handle.
- **Boundaries translate errors:** the API layer converts domain/ingestion/ML errors into a consistent error envelope with an appropriate HTTP status; it never leaks stack traces, secrets, or internal detail to clients (§8, NFR-SEC).
- **Validate inputs** at the API boundary and treat all external/provider data as untrusted (NFR-SEC-5); reject/quarantine invalid data (NFR-DATA-2).
- **Degrade gracefully:** when a feed/model is unavailable, surface a clear, labelled fallback/estimated result rather than failing the whole request (NFR-REL-2, NFR-DATA-4).
- **ML/optimization errors** (e.g. infeasible optimization) return a structured reason to the domain layer (which constraints conflict), which the domain layer turns into an explainable message (ARCHITECTURE §11.3).
- **Idempotency & retries:** ingestion jobs handle transient failures with bounded retries and quarantine on repeated failure (NFR-REL-3); avoid duplicate side effects.
- **User-facing messages** are actionable and free of internal detail.

---

## 15. Logging rules

- **Structured logging** (key-value / JSON) with a consistent schema; centralize in production.
- **Levels:** `DEBUG` (dev detail), `INFO` (normal operations/lifecycle), `WARNING` (recoverable/degraded), `ERROR` (failed operation), `CRITICAL` (system-level failure). Development may log at `DEBUG`; production at `INFO` and above.
- **Never log secrets or sensitive data:** no API keys, tokens, passwords, or full credentials; reference secrets by name only (safety practice). Mask/omit commercially sensitive values where not needed.
- **Context:** include correlation/request IDs to trace a request across API → domain → ML/optimization; include data provenance/freshness where relevant.
- **Observability:** emit metrics/health for data freshness, job status, model performance, and errors (NFR-MNT-2); wire operational alerts on ingestion/model failures.
- **Auditing is separate from logging:** recommendation audit records (inputs, model version, timestamp) are persisted per NFR-AUD, not just logged (ARCHITECTURE §12).
- **No noisy logging** in hot paths; avoid logging inside tight loops.

---

## 16. Testing rules

- **Test with the feature.** New behaviour ships with tests; bug fixes add a regression test. PRs without appropriate tests are not merged (§4).
- **Layers:**
  - *Backend/domain:* unit tests for domain services and business math (landed cost, compatibility rules), API/integration tests for endpoints (DRF test client), and DB tests against Postgres/PostGIS.
  - *ML:* tests for feature construction and prediction interfaces, plus metric-threshold checks on a validation split (§10). Determinism via fixed seeds.
  - *Optimization:* tests for problem construction, feasibility, and known-solution cases.
  - *Frontend:* component/unit tests for logic and key views; basic accessibility checks.
- **External providers are mocked/stubbed** in tests; no live external calls in CI (deterministic, offline).
- **Coverage:** maintain a sensible coverage target on business-critical modules (domain, ML interfaces, API); coverage is a guardrail, not a goal in itself.
- **CI gate:** lint + type-check + tests + `makemigrations --check` + frontend build must pass before merge (§4, §11).
- **Verification before "done":** run the relevant build/tests locally before opening/merging a PR; a green pipeline is required but not sufficient — verify the feature meets its acceptance signals (see [FUNCTIONAL_REQUIREMENTS.md](./FUNCTIONAL_REQUIREMENTS.md)).
- **No long-running/watch commands in CI**; use single-run test modes.

---

## 17. Documentation rules

- **Docs live in `docs/`** and are versioned with the code. Keep them in sync (Golden Rule §1).
- **What to update, when:** see §1 mapping (capabilities → FRD, sources → DATA_SOURCES, architecture → ARCHITECTURE, endpoints → API reference, env vars → `.env.example` + env docs, terms → GLOSSARY, models → experiment records).
- **API reference** (OpenAPI/schema) is kept current with the API (§8).
- **READMEs:** each major package/app has a short README describing its responsibility and boundaries.
- **ADRs (optional but encouraged):** record significant architectural decisions as short Architecture Decision Records under `docs/adr/`.
- **Diagrams:** use Mermaid in Markdown (as in ARCHITECTURE.md) so diagrams are diffable and versioned.
- **Style:** clear, concise, plain language; define new terms in [GLOSSARY.md](./GLOSSARY.md). Do not create documentation files that aren't needed.
- **No secrets in docs:** examples use placeholders only.

---

## 18. Quick reference

- Branch from `main`: `feat/<desc>` → commit with Conventional Commits → PR with checklist → 1–2 approvals → squash-merge → delete branch.
- Every feature PR updates docs (§1) and tests (§16).
- All config/secrets via env; `.env.example` committed, `.env` ignored, **never commit real secrets** (§12).
- Migrations with model changes, reviewed, backwards-compatible by default (§9).
- ML: reproducible, tracked, versioned, explainable; boundary from Django enforced (§10, ARCHITECTURE §12).
- Datasets versioned and licence-clean; no licensed/commercial data or real datasets in Git (§11).

## Related documents

- [ARCHITECTURE.md](./ARCHITECTURE.md)
- [FUNCTIONAL_REQUIREMENTS.md](./FUNCTIONAL_REQUIREMENTS.md)
- [NON_FUNCTIONAL_REQUIREMENTS.md](./NON_FUNCTIONAL_REQUIREMENTS.md)
- [DATA_SOURCES.md](./DATA_SOURCES.md)
- [PROJECT_SPECIFICATION.md](./PROJECT_SPECIFICATION.md)
- [GLOSSARY.md](./GLOSSARY.md)

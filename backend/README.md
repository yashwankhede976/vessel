# Backend (Django + DRF)

The Vessel backend: Django + Django REST Framework. This is a minimal scaffold — it starts and exposes a health-check endpoint. No business features are implemented.

## Layout

```
backend/
├── config/            # project config (settings, urls, wsgi, asgi)
├── apps/              # Django apps (bounded contexts)
│   └── health/        # minimal health-check endpoint
├── manage.py
├── requirements.txt       # runtime deps (pinned)
├── requirements-dev.txt   # + test deps
└── pytest.ini
```

Business logic will live in a domain/service layer, with ML and optimization in the separate top-level `ml/` package — see [../docs/ARCHITECTURE.md](../docs/ARCHITECTURE.md) §5, §7, §12.

## Run locally

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

Or from the repo root: `./scripts/dev-backend.sh`.

## Health check

```
GET /api/v1/health/  ->  {"status": "ok", "service": "vessel-backend", "environment": "development"}
```

## Configuration

All config is environment-driven — no hard-coded credentials. Copy the template and edit it:

```bash
cp .env.example .env   # backend/.env is git-ignored; never commit real secrets
```

Defaults use SQLite so the server starts with no external services; set `DATABASE_URL` to a PostgreSQL/PostGIS URL for the real stack. In production the backend performs **safe startup validation** (`config/env_validation.py`) and refuses to boot if `SECRET_KEY`, `DATABASE_URL`, `DEBUG`, or `DJANGO_ALLOWED_HOSTS` are missing or insecure.

See [../docs/ENVIRONMENT.md](../docs/ENVIRONMENT.md) for the full variable reference (mandatory vs optional, which APIs need no key, and how missing credentials are handled), and [../docs/DEVELOPMENT_WORKFLOW.md](../docs/DEVELOPMENT_WORKFLOW.md) §12–§13.

## Test

```bash
pip install -r requirements-dev.txt
pytest
```

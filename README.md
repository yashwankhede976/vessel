# Vessel

**Intelligent Freight Forecasting & Vessel Chartering platform** — bulk cargo procurement and vessel chartering from overseas origins to India's East Coast ports. SIH 2026 project.

This repository is a full-stack scaffold: a React + TypeScript frontend, a Django + Django REST Framework backend, and separate packages for ML, optimization, and data. It currently exposes only a health check and a minimal startup page — **no business features are implemented yet.**

For the product vision, requirements, architecture, data sources, and workflow, see [`docs/`](./docs/README.md).

## Repository structure

```
vessel/
├── frontend/     # React + TypeScript SPA (Vite, React Router) — deployed independently
├── backend/      # Django + DRF API (health check only for now)
├── ml/           # ML layer (forecasting/ETA/demurrage) — pure computation, no Django
├── data/         # versioned datasets & manifests (raw/processed are git-ignored)
├── docs/         # specification, architecture, data sources, workflow
├── scripts/      # dev helper scripts
├── tests/        # cross-service / e2e tests
├── docker/       # Dockerfiles + compose (separate images for frontend & backend)
├── .env.example  # environment variable template (copy to .env; never commit .env)
└── .gitignore
```

Each major directory has its own README with details.

## Prerequisites

- Python 3.12+ and pip (backend, ML)
- Node.js 20+ and npm (frontend)
- Optionally Docker + Docker Compose, and PostgreSQL/PostGIS for the full stack

## Quick start (local, without Docker)

```bash
cp .env.example .env   # then edit values as needed (never commit .env)
```

Backend (Django + DRF):

```bash
./scripts/dev-backend.sh
# or manually:
#   cd backend && python3 -m venv .venv && source .venv/bin/activate
#   pip install -r requirements.txt && python manage.py migrate && python manage.py runserver
```

Health check: http://localhost:8000/api/v1/health/ → `{"status": "ok", ...}`

Frontend (React + TypeScript):

```bash
./scripts/dev-frontend.sh
# or manually:  cd frontend && npm install && npm run dev
```

App: http://localhost:5173 — shows "Frontend is running" and the backend connectivity status.

## Quick start (Docker)

Frontend and backend build into **separate images** and can be deployed independently. For local orchestration (adds PostGIS):

```bash
docker compose -f docker/docker-compose.yml up --build
```

- Frontend: http://localhost:8080
- Backend health: http://localhost:8000/api/v1/health/

See [`docker/README.md`](./docker/README.md).

## Configuration

All configuration and secrets come from environment variables. Copy `.env.example` to `.env` for local development. **Never commit real secrets.** By default the backend uses SQLite so it starts with no external services; set `DATABASE_URL` to a PostgreSQL/PostGIS URL for the real stack. See [`docs/DEVELOPMENT_WORKFLOW.md`](./docs/DEVELOPMENT_WORKFLOW.md) §12–§13.

## Documentation

- [Docs index](./docs/README.md)
- [Project specification](./docs/PROJECT_SPECIFICATION.md)
- [Architecture](./docs/ARCHITECTURE.md)
- [Functional requirements](./docs/FUNCTIONAL_REQUIREMENTS.md)
- [Non-functional requirements](./docs/NON_FUNCTIONAL_REQUIREMENTS.md)
- [Data sources](./docs/DATA_SOURCES.md)
- [AIS ingestion (AISStream)](./docs/DATA_INGESTION_AIS.md)
- [Weather ingestion (Open-Meteo)](./docs/DATA_INGESTION_WEATHER.md)
- [Marine/cyclone warnings ingestion (IMD)](./docs/DATA_INGESTION_IMD.md)
- [Freight dataset schema](./docs/FREIGHT_DATASET_SCHEMA.md)
- [Environment & secrets](./docs/ENVIRONMENT.md)
- [API conventions](./docs/API_CONVENTIONS.md)
- [Development workflow](./docs/DEVELOPMENT_WORKFLOW.md)
- [Glossary](./docs/GLOSSARY.md)

## Status

Scaffold only: verified that the backend starts (health endpoint + passing test) and the frontend starts and builds. Business features are not implemented.

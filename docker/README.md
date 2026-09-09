# Docker

Container build and local orchestration for the Vessel platform. Frontend and backend build into **separate images** so they can be deployed independently (the SPA as a static site behind nginx/CDN; the backend as a WSGI service).

## Files

```
docker/
├── backend.Dockerfile    # Django + DRF, served by gunicorn
├── frontend.Dockerfile   # React/Vite build -> static files served by nginx
├── nginx.conf            # SPA routing for the frontend image
└── docker-compose.yml    # local dev: db (PostGIS) + backend + frontend
```

All build contexts are the **repository root**.

## Build images separately (independent deployment)

```bash
# Backend
docker build -f docker/backend.Dockerfile -t vessel-backend .

# Frontend (API URL baked in at build time)
docker build -f docker/frontend.Dockerfile \
  --build-arg VITE_API_BASE_URL=https://api.example.com/api/v1 \
  -t vessel-frontend .
```

## Run everything locally

```bash
docker compose -f docker/docker-compose.yml up --build
```

- Frontend: http://localhost:8080
- Backend health: http://localhost:8000/api/v1/health/
- Postgres/PostGIS: localhost:5432

## Configuration & secrets

All configuration comes from environment variables (see the root `.env.example`). **Never commit real secrets.** The compose defaults are development-only placeholders; production uses the platform's secret store and real values. See [../docs/DEVELOPMENT_WORKFLOW.md](../docs/DEVELOPMENT_WORKFLOW.md) §12–§13.

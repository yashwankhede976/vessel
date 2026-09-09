# Frontend (React + TypeScript)

The Vessel web application: React + TypeScript, built with Vite, routed with React Router. This is a minimal scaffold — a single page that verifies the app starts and can reach the backend health endpoint. No business features are implemented.

## Layout

```
frontend/
├── index.html
├── package.json
├── vite.config.ts
├── tsconfig*.json
└── src/
    ├── main.tsx          # entry (BrowserRouter)
    ├── App.tsx           # routes
    ├── pages/
    │   └── HealthPage.tsx # verifies startup + backend connectivity
    └── vite-env.d.ts
```

## Run locally

```bash
npm install
npm run dev
```

Or from the repo root: `./scripts/dev-frontend.sh`. The dev server runs on http://localhost:5173.

## Build

```bash
npm run build
```

## Configuration

Copy the template and edit it:

```bash
cp .env.example .env   # frontend/.env is git-ignored
```

The backend API base URL is configurable for separate deployment via `VITE_API_BASE_URL` (defaults to `http://localhost:8000/api/v1`). Map provider settings are also available. **All `VITE_*` values are public** (inlined into the build) — never put secrets here; provider secret keys live in the backend only. See [../docs/ENVIRONMENT.md](../docs/ENVIRONMENT.md) for the full reference.

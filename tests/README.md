# Tests

Cross-cutting / end-to-end and integration tests that span more than one package.

- **Backend unit/integration tests** live with the Django code under `backend/` (per-app `tests/`).
- **Frontend component tests** live with the React code under `frontend/`.
- **ML/optimization tests** live under `ml/`.
- This top-level `tests/` directory is for **cross-service / e2e** tests that exercise the running system (frontend + backend together).

See [../docs/DEVELOPMENT_WORKFLOW.md](../docs/DEVELOPMENT_WORKFLOW.md) §16 for testing rules. No tests are implemented yet.

#!/bin/sh
# Backend container entrypoint: apply migrations and seed the curated port
# dataset before starting the app, so a fresh database is demo-ready. Seeding is
# idempotent; a failure there is non-fatal (the app still starts).
set -e

echo "[entrypoint] applying database migrations..."
python manage.py migrate --noinput

echo "[entrypoint] seeding curated East Coast ports (idempotent)..."
python manage.py seed_ports || echo "[entrypoint] seed_ports skipped/failed (non-fatal)"

echo "[entrypoint] starting gunicorn..."
exec gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 3

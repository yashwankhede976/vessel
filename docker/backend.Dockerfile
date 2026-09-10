# Backend image (Django + DRF), served by gunicorn.
# Build context is the repo root: docker build -f docker/backend.Dockerfile .
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install dependencies first (better layer caching). A generous timeout +
# retries make the build resilient to slow mirrors when fetching large wheels
# (e.g. ortools).
COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir --timeout 120 --retries 5 -r requirements.txt

# Copy the backend source.
COPY backend/ ./

# Entrypoint: migrate + seed, then run gunicorn (see backend-entrypoint.sh).
COPY docker/backend-entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

EXPOSE 8000

# Run migrations + seed, then start the WSGI app.
# DJANGO_SETTINGS_MODULE defaults to config.settings.
CMD ["/usr/local/bin/entrypoint.sh"]

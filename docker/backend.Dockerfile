# Backend image (Django + DRF), served by gunicorn.
# Build context is the repo root: docker build -f docker/backend.Dockerfile .
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install dependencies first (better layer caching).
COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the backend source.
COPY backend/ ./

EXPOSE 8000

# Collect static files at build time (no-op friendly for the scaffold).
# RUN python manage.py collectstatic --noinput

# Run the WSGI app. DJANGO_SETTINGS_MODULE defaults to config.settings.
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3"]

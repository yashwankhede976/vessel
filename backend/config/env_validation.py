"""
Startup validation for mandatory environment settings.

Fails fast (raises ImproperlyConfigured) when the process is running in
production without the settings that are unsafe to default. This runs at
settings-import time, so `manage.py`, `manage.py check`, gunicorn, and the
test runner all enforce it.

Design rules:
- Development and testing keep working with safe defaults (no friction).
- Production refuses to start when a mandatory setting is missing/insecure.
- Error messages reference variable NAMES only — never secret values.

No external API keys are validated here: provider keys are OPTIONAL and the
platform degrades gracefully without them (see docs/ENVIRONMENT.md).
"""
from __future__ import annotations

from typing import Iterable

from django.core.exceptions import ImproperlyConfigured


def validate_production_settings(
    *,
    is_production: bool,
    secret_key: str,
    dev_insecure_secret_key: str,
    debug: bool,
    database_url: str,
    allowed_hosts: Iterable[str],
) -> None:
    """Validate mandatory production settings; no-op outside production.

    Raises:
        ImproperlyConfigured: if any mandatory production setting is invalid.
    """
    if not is_production:
        return

    errors: list[str] = []

    # SECRET_KEY must be a real, non-default, sufficiently long value.
    if not secret_key or secret_key == dev_insecure_secret_key:
        errors.append(
            "SECRET_KEY is missing or using the insecure development default. "
            "Set SECRET_KEY to a strong random value in production."
        )
    elif len(secret_key) < 32:
        errors.append(
            "SECRET_KEY is too short for production (min 32 characters). "
            "Generate a longer random value."
        )

    # DEBUG must be off in production.
    if debug:
        errors.append("DEBUG must be false in production.")

    # A real (non-SQLite) database must be configured in production.
    if not database_url:
        errors.append(
            "DATABASE_URL is not set. Production requires a PostgreSQL/PostGIS "
            "database URL (SQLite is not permitted in production)."
        )
    elif database_url.startswith("sqlite"):
        errors.append(
            "DATABASE_URL points at SQLite. Production requires PostgreSQL/PostGIS."
        )

    # ALLOWED_HOSTS must be set to real hosts (not empty, not only localhost).
    hosts = [h for h in allowed_hosts if h]
    if not hosts or set(hosts) <= {"localhost", "127.0.0.1"}:
        errors.append(
            "DJANGO_ALLOWED_HOSTS must list the production host(s); "
            "localhost-only is not valid in production."
        )

    if errors:
        bullet_list = "\n".join(f"  - {message}" for message in errors)
        raise ImproperlyConfigured(
            "Invalid production configuration. Fix the following environment "
            f"settings before starting:\n{bullet_list}"
        )

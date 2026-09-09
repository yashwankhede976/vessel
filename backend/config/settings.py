"""
Django settings for the Vessel backend.

Configuration is environment-driven (see docs/DEVELOPMENT_WORKFLOW.md §12).
This is a minimal scaffold: it starts the server and exposes a health-check
endpoint. No business features are configured here.

Environments (DJANGO_ENV): development | testing | production.

By default the project uses SQLite so the backend starts with no external
services. Set DATABASE_URL to a PostgreSQL/PostGIS URL for the real stack.
"""
from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env(
    DEBUG=(bool, False),
    DJANGO_DEBUG=(bool, False),
    DJANGO_ALLOWED_HOSTS=(list, ["localhost", "127.0.0.1"]),
    CORS_ALLOWED_ORIGINS=(list, ["http://localhost:5173"]),
)

# Read a .env file if present (never committed). The per-service backend/.env
# takes precedence; a repo-root .env is read as a fallback for convenience.
# environ does not overwrite variables already set, so order matters.
for candidate in (BASE_DIR / ".env", BASE_DIR.parent / ".env"):
    if candidate.exists():
        environ.Env.read_env(str(candidate))

DJANGO_ENV = env("DJANGO_ENV", default="development")
IS_PRODUCTION = DJANGO_ENV == "production"

# SECRET_KEY is the canonical name; DJANGO_SECRET_KEY is accepted for compatibility.
# A weak dev-only fallback is used OUTSIDE production; production must set a real
# value (enforced by validate_production_settings() below).
DEV_INSECURE_SECRET_KEY = "dev-insecure-change-me"
SECRET_KEY = env(
    "SECRET_KEY",
    default=env("DJANGO_SECRET_KEY", default=DEV_INSECURE_SECRET_KEY),
)

# DEBUG is the canonical name; DJANGO_DEBUG accepted for compatibility.
DEBUG = env("DEBUG") or env("DJANGO_DEBUG")

ALLOWED_HOSTS = env("DJANGO_ALLOWED_HOSTS")

INSTALLED_APPS = [
    # Django contrib apps required by DRF (auth) and its dependencies.
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.staticfiles",
    # Third-party
    "rest_framework",
    "django_filters",
    "drf_spectacular",
    "corsheaders",
    # Local
    "apps.api",
    "apps.health",
    "apps.catalog",
    "apps.operations",
    "apps.decisions",
]

# PostGIS toggle. When true (and the GIS stack is installed), geospatial
# models use GeoDjango PointField; otherwise they fall back to lat/lon decimals.
# Enable for production on PostgreSQL/PostGIS. See apps/operations/geo.py.
USE_POSTGIS = env.bool("USE_POSTGIS", default=False)

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.common.CommonMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {"context_processors": []},
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# Database: SQLite by default; DATABASE_URL (Postgres/PostGIS) overrides.
# Track whether a real DATABASE_URL was provided so production can require it.
DATABASE_URL = env("DATABASE_URL", default="")
DATABASES = {
    "default": env.db(
        "DATABASE_URL",
        default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}",
    )
}

# Cross-origin for the separately deployed frontend.
CORS_ALLOWED_ORIGINS = env("CORS_ALLOWED_ORIGINS")

REST_FRAMEWORK = {
    # --- Rendering (consistent success envelope) ---
    "DEFAULT_RENDERER_CLASSES": [
        "apps.api.renderers.EnvelopeJSONRenderer",
        # Browsable API is convenient in development only.
        *(
            ["rest_framework.renderers.BrowsableAPIRenderer"]
            if DEBUG
            else []
        ),
    ],
    # --- API versioning (namespace-based, e.g. /api/v1/) ---
    "DEFAULT_VERSIONING_CLASS": "rest_framework.versioning.NamespaceVersioning",
    "DEFAULT_VERSION": "v1",
    "ALLOWED_VERSIONS": ["v1"],
    # --- Consistent responses & exception handling ---
    "EXCEPTION_HANDLER": "apps.api.exceptions.exception_handler",
    # --- Pagination ---
    "DEFAULT_PAGINATION_CLASS": "apps.api.pagination.StandardPagination",
    "PAGE_SIZE": 25,
    # --- Filtering & ordering ---
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.OrderingFilter",
        "rest_framework.filters.SearchFilter",
    ],
    # --- OpenAPI schema generation ---
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    # --- Content negotiation defaults ---
    "DEFAULT_PARSER_CLASSES": ["rest_framework.parsers.JSONParser"],
}

# OpenAPI / documentation (drf-spectacular).
SPECTACULAR_SETTINGS = {
    "TITLE": "Vessel API",
    "DESCRIPTION": (
        "Intelligent Freight Forecasting & Vessel Chartering platform API. "
        "See docs/API_CONVENTIONS.md for response, versioning, pagination, "
        "filtering, and error conventions."
    ),
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "SCHEMA_PATH_PREFIX": r"/api/v[0-9]+/",
}

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# =============================================================================
# External data provider configuration
# -----------------------------------------------------------------------------
# All optional: unset keys leave the corresponding integration disabled and the
# platform degrades gracefully (see docs/ENVIRONMENT.md). No client code here.
# Canonical names are read first, with legacy aliases as fallbacks.
# =============================================================================
EXTERNAL_APIS = {
    # AISStream (AIS / vessel tracking) — free, registration required.
    "AISSTREAM_API_KEY": env("AISSTREAM_API_KEY", default=""),
    # UN Comtrade (trade flows) — free public tier; key raises limits.
    "COMTRADE_API_KEY": env(
        "COMTRADE_API_KEY", default=env("UN_COMTRADE_API_KEY", default="")
    ),
    # data.gov.in (Indian open government data) — free API key.
    "DATA_GOV_API_KEY": env(
        "DATA_GOV_API_KEY", default=env("DATA_GOV_IN_API_KEY", default="")
    ),
    # Open-Meteo (weather) — works WITHOUT a key on the free tier.
    "OPEN_METEO_BASE_URL": env(
        "OPEN_METEO_BASE_URL", default="https://api.open-meteo.com/v1"
    ),
    "OPEN_METEO_API_KEY": env("OPEN_METEO_API_KEY", default=""),
    # IMD (India Meteorological Department) — optional endpoint config.
    "IMD_BASE_URL": env("IMD_BASE_URL", default=""),
    # Baltic Exchange (freight benchmark) — LICENSED/commercial; unset by default.
    "BALTIC_EXCHANGE_API_KEY": env("BALTIC_EXCHANGE_API_KEY", default=""),
}

# =============================================================================
# Production security hardening (applied only when DJANGO_ENV=production)
# =============================================================================
if IS_PRODUCTION:
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 60 * 60 * 24 * 30  # 30 days
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# =============================================================================
# Safe startup validation for mandatory production settings.
# Raises ImproperlyConfigured (fail fast) if production is misconfigured.
# Runs on settings import so `manage.py`, gunicorn, and `manage.py check` all
# enforce it. Never logs secret values — only variable names.
# =============================================================================
from config.env_validation import validate_production_settings  # noqa: E402

validate_production_settings(
    is_production=IS_PRODUCTION,
    secret_key=SECRET_KEY,
    dev_insecure_secret_key=DEV_INSECURE_SECRET_KEY,
    debug=DEBUG,
    database_url=DATABASE_URL,
    allowed_hosts=ALLOWED_HOSTS,
)

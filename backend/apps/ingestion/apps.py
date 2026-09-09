from django.apps import AppConfig


class IngestionConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.ingestion"
    verbose_name = "Ingestion (data ingestion framework)"

    def ready(self) -> None:
        # Import the sources package so every concrete source registers itself
        # in the registry (see apps/ingestion/sources/__init__.py). Wrapped so a
        # source import problem never prevents the app from starting.
        try:
            from . import sources  # noqa: F401
        except Exception:  # pragma: no cover - defensive
            import logging

            logging.getLogger("vessel.ingestion").exception(
                "Failed to auto-register ingestion sources."
            )

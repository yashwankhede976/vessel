"""List the registered ingestion sources.

Usage:
    python manage.py list_ingestion_sources
"""
from __future__ import annotations

from django.core.management.base import BaseCommand

from apps.ingestion import sources as _sources  # ensures registration
from apps.ingestion.registry import list_sources


class Command(BaseCommand):
    help = "List all registered ingestion source keys."

    def handle(self, *args, **options) -> None:
        _sources.register_all()  # idempotent; ensures registry is populated
        keys = list_sources()
        if not keys:
            self.stdout.write(self.style.WARNING("No ingestion sources registered."))
            return
        self.stdout.write(f"Registered ingestion sources ({len(keys)}):")
        for key in keys:
            tag = " (self-configuring)" if key in _sources.SELF_CONFIGURING else \
                  " (requires config)"
            self.stdout.write(f"  - {key}{tag}")

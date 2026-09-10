"""Seed a curated (SYNTHETIC) representative dry-bulk fleet.

Reads apps/catalog/seed_data/vessels.json and upserts Vessel rows, storing:
- plain particulars in the model columns (dwt, loa, beam, draft, speed, flag,
  year_built, availability_status, open_date), and
- the full per-field provenance record in Vessel.metadata (same convention as
  Port.metadata: each entry is {value, source, source_date}; UNKNOWN is kept,
  never invented).

The dataset is explicitly SYNTHETIC (demo). It is labelled as such in every
metadata entry so no value is mistaken for an observed fixture. Its purpose is
to populate the fleet across all vessel types with a spread of availability
statuses so the availability-by-type summary is meaningful for the demo.

Idempotent: safe to run repeatedly (keyed on IMO).

Usage:
    python manage.py seed_vessels
    python manage.py seed_vessels --dry-run
    python manage.py seed_vessels --file /path/to/custom.json
"""
from __future__ import annotations

import json
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.catalog.models import Vessel

DEFAULT_DATA_FILE = (
    Path(__file__).resolve().parents[2] / "seed_data" / "vessels.json"
)

VALID_TYPES = {c.value for c in Vessel.VesselType}
VALID_STATUSES = {c.value for c in Vessel.AvailabilityStatus}


def _decimal(value: Any) -> Decimal | None:
    if value in (None, "", "UNKNOWN"):
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def _parse_date(value: Any) -> date | None:
    if not value or value == "UNKNOWN":
        return None
    return date.fromisoformat(str(value))


class Command(BaseCommand):
    help = "Seed a curated SYNTHETIC representative dry-bulk fleet (idempotent)."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--file",
            default=str(DEFAULT_DATA_FILE),
            help="Path to the curated vessels JSON dataset.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Parse and report actions without writing to the database.",
        )

    def handle(self, *args, **options) -> None:
        data_path = Path(options["file"])
        dry_run = options["dry_run"]

        if not data_path.exists():
            raise CommandError(f"Dataset file not found: {data_path}")

        try:
            dataset = json.loads(data_path.read_text())
        except json.JSONDecodeError as exc:
            raise CommandError(f"Invalid JSON in {data_path}: {exc}") from exc

        vessels = dataset.get("vessels", [])
        if not vessels:
            raise CommandError("Dataset contains no 'vessels'.")

        self.stdout.write(
            f"Seeding {len(vessels)} vessels from {data_path.name}"
            + (" (dry run)" if dry_run else "")
        )

        created = updated = 0
        with transaction.atomic():
            for entry in vessels:
                _, was_created = self._upsert_vessel(entry)
                created += int(was_created)
                updated += int(not was_created)
            if dry_run:
                transaction.set_rollback(True)

        self.stdout.write(
            self.style.SUCCESS(
                f"Vessels: {created} created, {updated} updated."
            )
        )
        if dry_run:
            self.stdout.write(self.style.WARNING("Dry run — no changes committed."))

    # ------------------------------------------------------------------
    def _upsert_vessel(self, entry: dict) -> tuple[Vessel, bool]:
        imo = str(entry["imo"])
        vessel_type = entry.get("vessel_type", Vessel.VesselType.OTHER)
        if vessel_type not in VALID_TYPES:
            raise CommandError(f"Vessel {imo}: unknown vessel_type '{vessel_type}'.")

        status = entry.get("availability_status", Vessel.AvailabilityStatus.UNKNOWN)
        if status not in VALID_STATUSES:
            raise CommandError(f"Vessel {imo}: unknown availability_status '{status}'.")

        dwt = _decimal(entry.get("dwt"))
        loa = _decimal(entry.get("loa"))
        beam = _decimal(entry.get("beam"))
        draft = _decimal(entry.get("draft"))
        if None in (dwt, loa, beam, draft):
            raise CommandError(
                f"Vessel {imo}: dwt/loa/beam/draft are required and must be numeric."
            )

        defaults = {
            "name": entry["name"],
            "vessel_type": vessel_type,
            "dwt": dwt,
            "loa": loa,
            "beam": beam,
            "draft": draft,
            "flag": entry.get("flag", "") or "",
            "year_built": entry.get("year_built"),
            "speed": _decimal(entry.get("speed")),
            "availability_status": status,
            "open_date": _parse_date(entry.get("open_date")),
            "metadata": entry.get("metadata", {}),
        }

        vessel, created = Vessel.objects.update_or_create(
            imo=imo, defaults=defaults
        )
        self.stdout.write(
            f"  Vessel {entry['name']} ({vessel_type}): "
            f"{'created' if created else 'updated'}"
        )
        return vessel, created

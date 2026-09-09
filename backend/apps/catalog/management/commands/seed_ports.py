"""Seed / import the curated East Coast India port dataset.

Reads apps/catalog/seed_data/east_coast_ports.json (each field is
{value, source, source_date}) and upserts Port rows, storing:
- plain values in the model columns (coordinates, type, unlocode), and
- the full per-field provenance record in Port.metadata.

Berths are created ONLY where the required dimensions (LOA, beam, draft) are
published as concrete values. Where any required dimension is "UNKNOWN", the
berth is skipped (never invented) and the omission is reported. Berth
provenance is stored in Berth.special_constraints.

Idempotent: safe to run repeatedly (keyed on name+country / port+berth_name).

Usage:
    python manage.py seed_ports
    python manage.py seed_ports --dry-run
    python manage.py seed_ports --file /path/to/custom.json
"""
from __future__ import annotations

import json
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.catalog.models import Berth, Commodity, Port

UNKNOWN = "UNKNOWN"

DEFAULT_DATA_FILE = (
    Path(__file__).resolve().parents[2] / "seed_data" / "east_coast_ports.json"
)

# Map dataset commodity keys -> (name, Commodity.Category value).
COMMODITY_MAP = {
    "coal_thermal": ("Thermal Coal", "coal_thermal"),
    "coal_coking": ("Coking Coal", "coal_coking"),
    "iron_ore": ("Iron Ore", "iron_ore"),
    "bauxite": ("Bauxite", "bauxite"),
    "other_dry_bulk": ("Other Dry Bulk", "other"),
}


def field_value(field: Any) -> Any:
    """Return the 'value' of a {value, source, source_date} field, or the raw value."""
    if isinstance(field, dict) and "value" in field:
        return field["value"]
    return field


def is_known(value: Any) -> bool:
    return value is not None and value != UNKNOWN and value != ""


def to_decimal(value: Any) -> Decimal | None:
    if not is_known(value):
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


class Command(BaseCommand):
    help = "Seed the curated East Coast India port dataset (idempotent)."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--file",
            default=str(DEFAULT_DATA_FILE),
            help="Path to the curated JSON dataset.",
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

        ports = dataset.get("ports", [])
        if not ports:
            raise CommandError("Dataset contains no 'ports'.")

        self.stdout.write(
            f"Seeding {len(ports)} ports from {data_path.name}"
            + (" (dry run)" if dry_run else "")
        )

        created_ports = updated_ports = 0
        created_berths = skipped_berths = 0

        # Wrap in a transaction; roll back entirely on dry run.
        with transaction.atomic():
            for entry in ports:
                port, was_created = self._upsert_port(entry)
                created_ports += int(was_created)
                updated_ports += int(not was_created)

                for berth_entry in entry.get("berths", []):
                    outcome = self._upsert_berth(port, berth_entry)
                    if outcome == "created":
                        created_berths += 1
                    elif outcome == "skipped":
                        skipped_berths += 1

            if dry_run:
                transaction.set_rollback(True)

        self.stdout.write(
            self.style.SUCCESS(
                f"Ports: {created_ports} created, {updated_ports} updated. "
                f"Berths: {created_berths} created, {skipped_berths} skipped "
                f"(missing published dimensions)."
            )
        )
        if dry_run:
            self.stdout.write(self.style.WARNING("Dry run — no changes committed."))

    # ------------------------------------------------------------------
    def _upsert_port(self, entry: dict) -> tuple[Port, bool]:
        name = entry["name"]
        country = entry["country"]

        latitude = to_decimal(field_value(entry["latitude"]))
        longitude = to_decimal(field_value(entry["longitude"]))
        if latitude is None or longitude is None:
            raise CommandError(f"Port '{name}' is missing valid coordinates.")

        defaults = {
            "coast": field_value(entry.get("coast", "east_coast_india")),
            "unlocode": field_value(entry.get("unlocode", "")) or "",
            "latitude": latitude,
            "longitude": longitude,
            "port_type": field_value(entry["port_type"]),
            # Store the entire curated record (with provenance) as metadata,
            # excluding nested berths which live on Berth rows.
            "metadata": {k: v for k, v in entry.items() if k != "berths"},
        }

        port, created = Port.objects.update_or_create(
            name=name, country=country, defaults=defaults
        )
        action = "created" if created else "updated"
        self.stdout.write(f"  Port {name}: {action}")
        return port, created

    def _upsert_berth(self, port: Port, berth_entry: dict) -> str:
        berth_name = berth_entry["berth_name"]

        max_loa = to_decimal(field_value(berth_entry.get("max_loa_m")))
        max_beam = to_decimal(field_value(berth_entry.get("max_beam_m")))
        max_draft = to_decimal(field_value(berth_entry.get("max_draft_m")))

        # The Berth model requires positive LOA, beam, and draft. If any is
        # unknown we do NOT invent it — skip the berth and report it.
        missing = [
            label
            for label, val in (
                ("max_loa", max_loa),
                ("max_beam", max_beam),
                ("max_draft", max_draft),
            )
            if val is None
        ]
        if missing:
            self.stdout.write(
                f"    Berth {berth_name}: skipped (unknown {', '.join(missing)})"
            )
            return "skipped"

        handling_rate = to_decimal(field_value(berth_entry.get("handling_rate_tpd")))

        defaults = {
            "max_loa": max_loa,
            "max_beam": max_beam,
            "max_draft": max_draft,
            # handling_rate is required non-negative; default to 0 (meaning
            # "not published") rather than inventing a rate. Provenance below
            # records that it is UNKNOWN.
            "handling_rate": handling_rate if handling_rate is not None else Decimal("0"),
            "special_constraints": {"provenance": berth_entry},
        }

        berth, created = Berth.objects.update_or_create(
            port=port, berth_name=berth_name, defaults=defaults
        )

        # Attach supported commodities (get_or_create the Commodity rows).
        self._set_commodities(berth, berth_entry.get("supported_commodities", []))

        self.stdout.write(
            f"    Berth {berth_name}: {'created' if created else 'updated'}"
        )
        return "created" if created else "updated"

    def _set_commodities(self, berth: Berth, keys: list[str]) -> None:
        commodities = []
        for key in keys:
            mapping = COMMODITY_MAP.get(key)
            if not mapping:
                continue
            display_name, category = mapping
            commodity, _ = Commodity.objects.get_or_create(
                name=display_name, defaults={"category": category}
            )
            commodities.append(commodity)
        if commodities:
            berth.supported_commodities.set(commodities)

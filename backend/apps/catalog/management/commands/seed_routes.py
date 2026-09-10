"""Seed overseas origins (with a representative load port) and trade lanes.

Reads apps/catalog/seed_data/routes.json and upserts:
- an overseas load Port for each origin (REAL published coordinates),
- the Origin with that load_port attached, and
- the Route (trade lane) into an East Coast India destination port.

Purpose: give the map real, drawable origin -> destination voyage lines for
cargo ships. Destination ports must already exist (run seed_ports first); a
route whose destination is missing is skipped and reported (never invented).

Distances are ESTIMATED (approximate great-circle) and labelled as such in the
dataset; they are stored on Route.distance_nm which the app already treats as an
estimate.

Idempotent: safe to run repeatedly (keyed on port name+country, origin name,
and origin+destination).

Usage:
    python manage.py seed_routes
    python manage.py seed_routes --dry-run
"""
from __future__ import annotations

import json
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.catalog.models import Origin, Port, Route

DEFAULT_DATA_FILE = (
    Path(__file__).resolve().parents[2] / "seed_data" / "routes.json"
)


def _decimal(value: Any) -> Decimal | None:
    if value in (None, "", "UNKNOWN"):
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


class Command(BaseCommand):
    help = "Seed overseas origins + load ports + trade lanes (idempotent)."

    def add_arguments(self, parser) -> None:
        parser.add_argument("--file", default=str(DEFAULT_DATA_FILE))
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options) -> None:
        data_path = Path(options["file"])
        dry_run = options["dry_run"]

        if not data_path.exists():
            raise CommandError(f"Dataset file not found: {data_path}")

        try:
            dataset = json.loads(data_path.read_text())
        except json.JSONDecodeError as exc:
            raise CommandError(f"Invalid JSON in {data_path}: {exc}") from exc

        origins = dataset.get("origins", [])
        routes = dataset.get("routes", [])

        self.stdout.write(
            f"Seeding {len(origins)} origins and {len(routes)} routes"
            + (" (dry run)" if dry_run else "")
        )

        created_origins = created_routes = skipped_routes = 0
        with transaction.atomic():
            for entry in origins:
                _, was_created = self._upsert_origin(entry)
                created_origins += int(was_created)

            for entry in routes:
                outcome = self._upsert_route(entry)
                if outcome == "created":
                    created_routes += 1
                elif outcome == "skipped":
                    skipped_routes += 1

            if dry_run:
                transaction.set_rollback(True)

        self.stdout.write(
            self.style.SUCCESS(
                f"Origins: {created_origins} created. "
                f"Routes: {created_routes} created, {skipped_routes} skipped "
                f"(missing destination port)."
            )
        )
        if dry_run:
            self.stdout.write(self.style.WARNING("Dry run — no changes committed."))

    # ------------------------------------------------------------------
    def _upsert_origin(self, entry: dict) -> tuple[Origin, bool]:
        lp_data = entry["load_port"]
        lat = _decimal(lp_data.get("latitude"))
        lon = _decimal(lp_data.get("longitude"))
        if lat is None or lon is None:
            raise CommandError(
                f"Origin '{entry['name']}' load port lacks valid coordinates."
            )

        load_port, _ = Port.objects.update_or_create(
            name=lp_data["name"],
            country=lp_data["country"],
            defaults={
                "coast": lp_data.get("coast", "overseas"),
                "unlocode": lp_data.get("unlocode", "") or "",
                "latitude": lat,
                "longitude": lon,
                "port_type": lp_data.get("port_type", "seaport"),
                "metadata": {"source": lp_data.get("source", "REAL")},
            },
        )

        origin, created = Origin.objects.update_or_create(
            name=entry["name"],
            defaults={"country": entry["country"], "load_port": load_port},
        )
        self.stdout.write(
            f"  Origin {entry['name']} (load port {load_port.name}): "
            f"{'created' if created else 'updated'}"
        )
        return origin, created

    def _upsert_route(self, entry: dict) -> str:
        origin = Origin.objects.filter(name=entry["origin"]).first()
        destination = Port.objects.filter(name=entry["destination"]).first()
        if origin is None or destination is None:
            self.stdout.write(
                f"    Route {entry['origin']} -> {entry['destination']}: "
                f"skipped (missing {'origin' if origin is None else 'destination port'})"
            )
            return "skipped"

        _, created = Route.objects.update_or_create(
            origin=origin,
            destination_port=destination,
            defaults={
                "distance_nm": _decimal(entry.get("distance_nm")),
                "typical_transit_days": _decimal(entry.get("typical_transit_days")),
            },
        )
        self.stdout.write(
            f"    Route {entry['origin']} -> {entry['destination']}: "
            f"{'created' if created else 'updated'}"
        )
        return "created" if created else "updated"

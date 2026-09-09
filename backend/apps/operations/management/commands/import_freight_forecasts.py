"""Import freight forecasts produced by the ML layer into FreightForecast rows.

This is the backend half of the ML -> Django forecast bridge. The ML layer
(separate venv, Python 3.13) trains the XGBoost horizon models and writes a JSON
artifact via `python -m ml.models.export_forecasts`. This command reads that
artifact and upserts `operations.FreightForecast` rows for the 7/14/30-day
horizons, preserving forecast / lower_bound / upper_bound / confidence /
model_version and the generation timestamp.

The architecture boundary is respected: Django never imports the ML package or
the scientific stack — it only reads the JSON artifact on disk.

Data provenance: the artifact records `dataset_kind` (SYNTHETIC | REAL) and
`data_kind` (FORECAST). With the synthetic demo dataset the stored rows are
SYNTHETIC forecasts; this is surfaced in the command output so nobody mistakes
them for real market data.

Horizon mapping (FreightForecast.Horizon has only short_term / medium_term):
    7d, 14d  -> short_term
    30d      -> medium_term

Usage:
    python manage.py import_freight_forecasts --file ../ml/models/results/freight_forecasts.json
    python manage.py import_freight_forecasts --file <path> --create-lanes
    python manage.py import_freight_forecasts --file <path> --dry-run
"""
from __future__ import annotations

import json
from datetime import date, datetime, timezone as dt_timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.catalog.models import Origin, Port, Route
from apps.operations.models import FreightForecast

# ML horizon (days) -> FreightForecast.Horizon value.
HORIZON_MAP = {
    7: FreightForecast.Horizon.SHORT_TERM,
    14: FreightForecast.Horizon.SHORT_TERM,
    30: FreightForecast.Horizon.MEDIUM_TERM,
}


def _dec(value) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


class Command(BaseCommand):
    help = "Import ML freight forecasts (JSON artifact) into FreightForecast rows."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--file", required=True, help="Path to the ML forecast JSON artifact."
        )
        parser.add_argument(
            "--create-lanes",
            action="store_true",
            help="Create missing Origin/Route lanes (default: skip unknown lanes).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Parse and report without writing to the database.",
        )

    def handle(self, *args, **options) -> None:
        path = Path(options["file"])
        create_lanes = options["create_lanes"]
        dry_run = options["dry_run"]

        if not path.exists():
            raise CommandError(f"Forecast artifact not found: {path}")
        try:
            artifact = json.loads(path.read_text())
        except json.JSONDecodeError as exc:
            raise CommandError(f"Invalid JSON in {path}: {exc}") from exc

        rows = artifact.get("forecasts", [])
        if not rows:
            raise CommandError("Artifact contains no 'forecasts'.")

        model_name = artifact.get("model_name", "")
        model_version = artifact.get("model_version", "")
        dataset_kind = artifact.get("dataset_kind", "UNKNOWN")
        generated_at = self._parse_dt(artifact.get("generated_at"))

        self.stdout.write(
            f"Importing {len(rows)} forecasts from {path.name} "
            f"[{model_name} v{model_version}, data={dataset_kind}]"
            + (" (dry run)" if dry_run else "")
        )
        if dataset_kind != "REAL":
            self.stdout.write(
                self.style.WARNING(
                    f"  NOTE: dataset_kind={dataset_kind} — these are NOT real "
                    "market rates; they are model forecasts on non-real inputs."
                )
            )

        created = updated = skipped = 0

        with transaction.atomic():
            for row in rows:
                outcome = self._upsert_row(
                    row,
                    model_name=model_name,
                    model_version=model_version,
                    generated_at=generated_at,
                    create_lanes=create_lanes,
                )
                if outcome == "created":
                    created += 1
                elif outcome == "updated":
                    updated += 1
                else:
                    skipped += 1
            if dry_run:
                transaction.set_rollback(True)

        self.stdout.write(
            self.style.SUCCESS(
                f"Forecasts: {created} created, {updated} updated, {skipped} skipped "
                f"(unknown lane / bad horizon)."
            )
        )
        if dry_run:
            self.stdout.write(self.style.WARNING("Dry run — no changes committed."))

    # ------------------------------------------------------------------
    def _parse_dt(self, value) -> datetime:
        if not value:
            return datetime.now(dt_timezone.utc)
        try:
            dt = datetime.fromisoformat(value)
        except ValueError:
            return datetime.now(dt_timezone.utc)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=dt_timezone.utc)
        return dt

    def _resolve_route(self, origin_name, destination_name, create_lanes):
        port = Port.objects.filter(name__iexact=destination_name.strip()).first()
        if port is None:
            return None
        origin = Origin.objects.filter(name__iexact=origin_name.strip()).first()
        if origin is None:
            if not create_lanes:
                return None
            origin = Origin.objects.create(
                name=origin_name.strip(), country=origin_name.strip()
            )
        route = Route.objects.filter(origin=origin, destination_port=port).first()
        if route is None:
            if not create_lanes:
                return None
            route = Route.objects.create(origin=origin, destination_port=port)
        return route

    def _upsert_row(self, row, *, model_name, model_version, generated_at, create_lanes):
        horizon_days = row.get("horizon_days")
        horizon = HORIZON_MAP.get(horizon_days)
        if horizon is None:
            return "skipped"

        route = self._resolve_route(row["origin"], row["destination"], create_lanes)
        if route is None:
            self.stdout.write(
                f"  skip {row['origin']}->{row['destination']} "
                f"(lane not found; use --create-lanes to add)"
            )
            return "skipped"

        try:
            target_date = date.fromisoformat(row["target_date"])
        except (KeyError, ValueError):
            return "skipped"

        predicted = _dec(row.get("predicted_rate_per_tonne"))
        if predicted is None or predicted < 0:
            return "skipped"

        defaults = {
            "predicted_rate_per_tonne": predicted,
            "lower_bound": _dec(row.get("lower_bound")),
            "upper_bound": _dec(row.get("upper_bound")),
            "confidence": _dec(row.get("confidence")),
            "generated_at": generated_at,
        }

        # Natural key mirrors the model's unique constraint.
        _, created = FreightForecast.objects.update_or_create(
            route=route,
            vessel_type=row.get("vessel_type", ""),
            target_date=target_date,
            horizon=horizon,
            model_name=model_name,
            model_version=model_version,
            defaults=defaults,
        )
        return "created" if created else "updated"

"""Run a self-configuring ingestion source by its registry key.

This is the scheduler/cron entry point (and manual trigger) for the ingestion
sources that need no per-run configuration: open_meteo, world_bank, un_comtrade.
Config-driven sources (imd, incois, data_gov_in, ministry_of_coal) require a
product/dataset config and are invoked programmatically, not via this command.

The command NEVER crashes the process on a provider problem: a source that is
unavailable/failed is reported (non-zero exit only on an unexpected crash),
which is what a scheduler needs so one bad source does not abort a batch.

Usage:
    python manage.py run_ingestion open_meteo
    python manage.py run_ingestion world_bank --indicator EG.USE.PCAP.KG.OE
    python manage.py run_ingestion un_comtrade --period 2024
"""
from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from apps.ingestion import sources as _sources  # ensures registration
from apps.ingestion.registry import get_source
from apps.ingestion.exceptions import RegistryError


class Command(BaseCommand):
    help = "Run a self-configuring ingestion source by key (open_meteo/world_bank/un_comtrade)."

    def add_arguments(self, parser) -> None:
        parser.add_argument("source_key", help="Registry key of the source to run.")
        # Optional generic passthrough overrides for the self-configuring sources.
        parser.add_argument("--period", help="Comtrade period (e.g. 2024).")
        parser.add_argument("--indicator", help="World Bank indicator code.")
        parser.add_argument("--country", help="World Bank country code (e.g. WLD).")

    def handle(self, *args, **options) -> None:
        _sources.register_all()  # idempotent; ensures registry is populated
        key = options["source_key"]

        if key not in _sources.SELF_CONFIGURING:
            raise CommandError(
                f"Source '{key}' is not self-configuring and cannot be run by this "
                f"command. Self-configuring sources: "
                f"{', '.join(sorted(_sources.SELF_CONFIGURING))}. Config-driven "
                "sources (imd, incois, data_gov_in, ministry_of_coal) must be run "
                "programmatically with a config object."
            )
        if key == "aisstream":
            raise CommandError(
                "aisstream is a streaming source; use its consumer/run_session "
                "entry point, not run_ingestion."
            )

        try:
            source_cls = get_source(key)
        except RegistryError as exc:
            raise CommandError(str(exc)) from exc

        kwargs = {}
        if key == "un_comtrade" and options.get("period"):
            kwargs["period"] = options["period"]
        if key == "world_bank":
            if options.get("indicator"):
                kwargs["indicator"] = options["indicator"]
            if options.get("country"):
                kwargs["country"] = options["country"]

        self.stdout.write(f"Running ingestion source '{key}'...")
        source = source_cls(**kwargs)
        result = source.run()

        style = self.style.SUCCESS
        if result.status in ("failed",):
            style = self.style.ERROR
        elif result.status in ("partial", "source_unavailable"):
            style = self.style.WARNING

        self.stdout.write(
            style(
                f"  status={result.status} fetched={result.fetched} "
                f"valid={result.valid} invalid={result.invalid} "
                f"written={result.written} duplicate={result.duplicate} "
                f"attempts={result.attempts}"
            )
        )
        if result.error_message:
            self.stdout.write(self.style.WARNING(f"  note: {result.error_message}"))

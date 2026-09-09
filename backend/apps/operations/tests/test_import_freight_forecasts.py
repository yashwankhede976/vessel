"""Integration test for the ML -> DB freight-forecast import command."""
import json
import tempfile
from decimal import Decimal
from pathlib import Path

from django.core.management import call_command
from django.test import TestCase

from apps.catalog.models import Origin, Port, Route
from apps.operations.models import FreightForecast


class ImportFreightForecastsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.origin = Origin.objects.create(name="Australia", country="Australia")
        cls.port, _ = Port.objects.get_or_create(
            name="Paradip", country="India",
            defaults={"latitude": Decimal("20.26"), "longitude": Decimal("86.67")},
        )
        cls.route, _ = Route.objects.get_or_create(
            origin=cls.origin, destination_port=cls.port
        )

    def _artifact(self, **overrides):
        base = {
            "model_name": "freight_gbm_xgboost",
            "model_version": "0.2.0",
            "dataset_kind": "SYNTHETIC",
            "generated_at": "2026-09-01T00:00:00+00:00",
            "forecasts": [
                {"origin": "Australia", "destination": "Paradip",
                 "vessel_type": "capesize", "horizon_days": 7,
                 "target_date": "2026-09-08", "predicted_rate_per_tonne": 18.5,
                 "lower_bound": 17.0, "upper_bound": 20.0, "confidence": 0.8},
                {"origin": "Australia", "destination": "Paradip",
                 "vessel_type": "capesize", "horizon_days": 30,
                 "target_date": "2026-10-01", "predicted_rate_per_tonne": 19.0,
                 "lower_bound": 16.0, "upper_bound": 22.0, "confidence": 0.6},
            ],
        }
        base.update(overrides)
        return base

    def _write(self, artifact) -> str:
        f = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False)
        json.dump(artifact, f)
        f.close()
        return f.name

    def test_imports_forecast_rows(self):
        path = self._write(self._artifact())
        call_command("import_freight_forecasts", file=path)
        self.assertEqual(FreightForecast.objects.count(), 2)
        fc = FreightForecast.objects.get(
            route=self.route, target_date="2026-09-08"
        )
        self.assertEqual(fc.predicted_rate_per_tonne, Decimal("18.50"))
        self.assertEqual(fc.horizon, FreightForecast.Horizon.SHORT_TERM)
        # 30d maps to medium_term.
        fc30 = FreightForecast.objects.get(route=self.route, target_date="2026-10-01")
        self.assertEqual(fc30.horizon, FreightForecast.Horizon.MEDIUM_TERM)

    def test_idempotent(self):
        path = self._write(self._artifact())
        call_command("import_freight_forecasts", file=path)
        call_command("import_freight_forecasts", file=path)
        self.assertEqual(FreightForecast.objects.count(), 2)   # no duplicates

    def test_unknown_lane_skipped_without_create_lanes(self):
        art = self._artifact()
        art["forecasts"][0]["origin"] = "Neverland"
        path = self._write(art)
        call_command("import_freight_forecasts", file=path)
        # Only the known-lane (Paradip capesize 30d) row is written.
        self.assertEqual(FreightForecast.objects.count(), 1)

    def test_create_lanes_adds_missing_origin(self):
        art = self._artifact()
        art["forecasts"] = [{
            "origin": "Indonesia", "destination": "Paradip", "vessel_type": "panamax",
            "horizon_days": 7, "target_date": "2026-09-08",
            "predicted_rate_per_tonne": 14.0, "lower_bound": 13.0,
            "upper_bound": 15.0, "confidence": 0.85,
        }]
        path = self._write(art)
        call_command("import_freight_forecasts", file=path, create_lanes=True)
        self.assertTrue(Origin.objects.filter(name="Indonesia").exists())
        self.assertEqual(FreightForecast.objects.count(), 1)

    def test_dry_run_writes_nothing(self):
        path = self._write(self._artifact())
        call_command("import_freight_forecasts", file=path, dry_run=True)
        self.assertEqual(FreightForecast.objects.count(), 0)

"""Tests for the INCOIS (keyless) ocean-state adapter using injected payloads."""
from decimal import Decimal

from django.test import TestCase

from apps.catalog.models import Port
from apps.ingestion.exceptions import SourceConfigError
from apps.ingestion.models import IngestionRun
from apps.ingestion.sources.incois import INCOISProductConfig, INCOISSource
from apps.operations.models import MarineObservation


FIELD_MAP = {
    "timestamp": "time",
    "area_name": "area",
    "port_name": "port",
    "latitude": "lat",
    "longitude": "lon",
    "severity": "warning",
    "significant_wave_height_m": "swh",
    "wave_period_s": "tp",
    "swell_direction_deg": "swell_dir",
    "current_speed_kn": "cur",
    "sea_surface_temp_c": "sst",
}


def config(records_key="records"):
    return INCOISProductConfig(
        product="ocean_state",
        url="https://incois.example/ocean_state.json",
        field_map=FIELD_MAP,
        records_key=records_key,
        source_ref="INCOIS ocean-state (test)",
    )


def ocean_state_payload():
    return {"records": [
        {"time": "2026-09-01T06:00:00Z", "area": "Bay of Bengal", "port": "Paradip",
         "lat": 20.26, "lon": 86.67, "warning": "moderate",
         "swh": 2.4, "tp": 8.1, "swell_dir": 135, "cur": 1.2, "sst": 28.5},
        {"time": "2026-09-01T06:00:00Z", "area": "", "port": "",
         "lat": None, "lon": None, "warning": "low",  # no area/port/coords -> skip
         "swh": 1.0},
    ]}


def fake_http(payload, raiser=None):
    def _get(url):
        if raiser is not None:
            raise raiser
        return payload
    return _get


class INCOISIngestionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.port, _ = Port.objects.get_or_create(
            name="Paradip", country="India",
            defaults={"latitude": Decimal("20.26"), "longitude": Decimal("86.67")},
        )

    def test_ingests_ocean_state(self):
        src = INCOISSource(config(), http_get_json=fake_http(ocean_state_payload()))
        result = src.run()
        self.assertEqual(result.status, IngestionRun.Status.SUCCESS)
        # Second record has no area/port/coords -> skipped in persist.
        self.assertEqual(MarineObservation.objects.count(), 1)
        obs = MarineObservation.objects.first()
        self.assertEqual(obs.significant_wave_height_m, Decimal("2.40"))
        self.assertEqual(obs.wave_period_s, Decimal("8.10"))
        self.assertEqual(obs.current_speed_kn, Decimal("1.20"))
        self.assertEqual(obs.sea_surface_temp_c, Decimal("28.50"))
        self.assertEqual(obs.severity, "moderate")
        self.assertEqual(obs.source, "incois")
        self.assertEqual(obs.port_id, self.port.pk)
        self.assertEqual(obs.raw["swh"], 2.4)  # raw retained

    def test_is_keyless(self):
        src = INCOISSource(config(), http_get_json=fake_http(ocean_state_payload()))
        self.assertEqual(src.run().status, IngestionRun.Status.SUCCESS)

    def test_empty_records_source_unavailable(self):
        src = INCOISSource(config(), http_get_json=fake_http({"records": None}))
        self.assertEqual(src.run().status, IngestionRun.Status.SOURCE_UNAVAILABLE)

    def test_malformed_payload_source_unavailable(self):
        # records_key points into a dict, but payload is a bare list.
        src = INCOISSource(config(), http_get_json=fake_http([1, 2, 3]))
        self.assertEqual(src.run().status, IngestionRun.Status.SOURCE_UNAVAILABLE)

    def test_unknown_product_rejected(self):
        with self.assertRaises(SourceConfigError):
            INCOISProductConfig(product="nope", url="x", field_map={"a": "b"})

    def test_idempotent(self):
        INCOISSource(config(), http_get_json=fake_http(ocean_state_payload())).run()
        r2 = INCOISSource(config(), http_get_json=fake_http(ocean_state_payload())).run()
        self.assertEqual(MarineObservation.objects.count(), 1)
        self.assertEqual(r2.duplicate, 1)

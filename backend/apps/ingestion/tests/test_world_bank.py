"""Tests for the World Bank (keyless) adapter using injected mock responses."""
from datetime import date
from decimal import Decimal

from django.test import TestCase

from apps.ingestion.models import IngestionRun
from apps.ingestion.sources.world_bank import WorldBankSource
from apps.operations.models import CommodityPriceObservation


def wb_body():
    """World Bank v2 shape: [meta, [records...]]."""
    return [
        {"page": 1, "pages": 1, "per_page": 100, "total": 2},
        [
            {"indicator": {"id": "X"}, "country": {"value": "World"},
             "date": "2024", "value": 123.45},
            {"indicator": {"id": "X"}, "country": {"value": "World"},
             "date": "2023", "value": 118.0},
            {"indicator": {"id": "X"}, "country": {"value": "World"},
             "date": "2022", "value": None},  # missing value -> skipped
        ],
    ]


def fake_http(status, body):
    def _get(url, params):
        return status, body
    return _get


class WorldBankIngestionTests(TestCase):
    def test_ingests_indicator_values(self):
        src = WorldBankSource(http_get=fake_http(200, wb_body()))
        result = src.run()
        self.assertEqual(result.status, IngestionRun.Status.SUCCESS)
        # 3 records in, 1 has null value -> 2 written.
        self.assertEqual(CommodityPriceObservation.objects.count(), 2)
        obs = CommodityPriceObservation.objects.get(observed_on=date(2024, 1, 1))
        self.assertEqual(obs.price, Decimal("123.4500"))
        self.assertEqual(obs.source, "world_bank")
        self.assertIn("api.worldbank.org", obs.source_url)
        self.assertIsNotNone(obs.retrieved_at)
        self.assertFalse(obs.is_estimated)

    def test_missing_value_not_fabricated(self):
        src = WorldBankSource(http_get=fake_http(200, wb_body()))
        src.run()
        self.assertFalse(
            CommodityPriceObservation.objects.filter(observed_on=date(2022, 1, 1)).exists()
        )

    def test_is_keyless(self):
        # No settings key needed; runs with just an injected transport.
        src = WorldBankSource(http_get=fake_http(200, wb_body()))
        self.assertEqual(src.run().status, IngestionRun.Status.SUCCESS)

    def test_empty_data_array(self):
        src = WorldBankSource(http_get=fake_http(200, [{"total": 0}, []]))
        result = src.run()
        self.assertEqual(result.status, IngestionRun.Status.SUCCESS)
        self.assertEqual(CommodityPriceObservation.objects.count(), 0)

    def test_error_envelope_is_source_unavailable(self):
        # World Bank error: a single-element list with a message object.
        src = WorldBankSource(http_get=fake_http(200, [{"message": [{"value": "bad"}]}]))
        self.assertEqual(src.run().status, IngestionRun.Status.SOURCE_UNAVAILABLE)

    def test_rate_limit_is_source_unavailable(self):
        src = WorldBankSource(http_get=fake_http(429, None))
        src.backoff_seconds = 0
        self.assertEqual(src.run().status, IngestionRun.Status.SOURCE_UNAVAILABLE)

    def test_server_error_is_source_unavailable(self):
        src = WorldBankSource(http_get=fake_http(503, None))
        self.assertEqual(src.run().status, IngestionRun.Status.SOURCE_UNAVAILABLE)

    def test_idempotent(self):
        WorldBankSource(http_get=fake_http(200, wb_body())).run()
        r2 = WorldBankSource(http_get=fake_http(200, wb_body())).run()
        self.assertEqual(CommodityPriceObservation.objects.count(), 2)
        self.assertEqual(r2.duplicate, 2)

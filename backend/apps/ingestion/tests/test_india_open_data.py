"""Tests for the data.gov.in and Ministry of Coal ingestion adapters.

Uses injected HTTP / in-memory CSV — no network, no files, no scraping.
Verifies field-map-only mapping (no assumed fields), provenance storage, and
graceful SOURCE_UNAVAILABLE reporting.
"""
from datetime import date

from django.test import TestCase, override_settings

from apps.catalog.models import Commodity, Port
from apps.ingestion.exceptions import SourceUnavailableError
from apps.ingestion.models import IngestionRun
from apps.ingestion.sources.india_open_data import (
    CsvDownloadSource,
    DataGovInApiSource,
    DatasetConfig,
    MinistryOfCoalSource,
    TARGET_COMMODITY_PRICE,
    TARGET_PORT_TRAFFIC,
    TARGET_TRADE,
)
from apps.operations.models import (
    CommodityPriceObservation,
    PortTraffic,
    TradeObservation,
)


class PortTrafficApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        # "Paradip" is already seeded by a data migration; reuse it.
        cls.port, _ = Port.objects.get_or_create(
            name="Paradip",
            country="India",
            defaults={"latitude": "20.26", "longitude": "86.67"},
        )

    def _config(self):
        return DatasetConfig(
            target=TARGET_PORT_TRAFFIC,
            field_map={
                "period": "month",
                "port_name": "port",
                "throughput_tonnes": "cargo_tonnes",
                # NOTE: no vessel_count in the map -> must stay null.
            },
            source="data.gov.in — Port cargo (test)",
            source_url="https://data.gov.in/resource/test-resource",
            source_date="2026-09-01",
        )

    def test_rest_ingestion_maps_only_declared_fields_with_provenance(self):
        # The payload has extra columns the map does NOT declare; they must be
        # ignored, not stored.
        payload = {
            "records": [
                {
                    "month": "2026-08-01",
                    "port": "Paradip",
                    "cargo_tonnes": "1234567",
                    "undeclared_column": "should be ignored",
                    "vessels": "42",  # not mapped -> vessel_count stays null
                }
            ]
        }

        def fake_http(url, params):
            assert params["api-key"] == "k"  # key passed through
            return payload

        src = DataGovInApiSource(
            self._config(),
            resource_id="test-resource",
            api_key="k",
            http_get_json=fake_http,
        )
        result = src.run()

        self.assertEqual(result.status, IngestionRun.Status.SUCCESS)
        self.assertEqual(PortTraffic.objects.count(), 1)
        row = PortTraffic.objects.get()
        self.assertEqual(row.port, self.port)
        self.assertEqual(row.period, date(2026, 8, 1))
        self.assertEqual(str(row.throughput_tonnes), "1234567.00")
        # Undeclared field was not fabricated onto the model.
        self.assertIsNone(row.vessel_count)
        # Provenance stored.
        self.assertEqual(row.source, "data.gov.in — Port cargo (test)")
        self.assertEqual(row.source_url, "https://data.gov.in/resource/test-resource")
        self.assertEqual(row.source_date, date(2026, 9, 1))
        self.assertIsNotNone(row.retrieved_at)

    def test_missing_declared_column_stays_null(self):
        # Row omits 'cargo_tonnes' entirely -> throughput must be null.
        payload = {"records": [{"month": "2026-08-01", "port": "Paradip"}]}
        src = DataGovInApiSource(
            self._config(), resource_id="r", api_key="k",
            http_get_json=lambda u, p: payload,
        )
        src.run()
        self.assertIsNone(PortTraffic.objects.get().throughput_tonnes)

    def test_unresolvable_port_is_skipped_not_fabricated(self):
        payload = {"records": [{"month": "2026-08-01", "port": "Nowhere", "cargo_tonnes": "5"}]}
        src = DataGovInApiSource(
            self._config(), resource_id="r", api_key="k",
            http_get_json=lambda u, p: payload,
        )
        result = src.run()
        # Row skipped (unknown port); nothing written, run still succeeds.
        self.assertEqual(PortTraffic.objects.count(), 0)
        self.assertEqual(result.written, 0)


class SourceUnavailableTests(TestCase):
    def _config(self):
        return DatasetConfig(
            target=TARGET_PORT_TRAFFIC,
            field_map={"period": "month", "port_name": "port"},
            source="data.gov.in (test)",
            source_url="https://data.gov.in/resource/x",
        )

    def test_http_unavailable_reports_source_unavailable(self):
        def boom(url, params):
            raise SourceUnavailableError("endpoint down")

        src = DataGovInApiSource(
            self._config(), resource_id="r", api_key="k", http_get_json=boom
        )
        result = src.run()
        self.assertEqual(result.status, IngestionRun.Status.SOURCE_UNAVAILABLE)
        run = IngestionRun.objects.get(pk=result.run_id)
        self.assertEqual(run.status, IngestionRun.Status.SOURCE_UNAVAILABLE)

    def test_no_records_key_reports_source_unavailable(self):
        # A body without 'records' (e.g. an error object) is treated as unavailable.
        src = DataGovInApiSource(
            self._config(), resource_id="r", api_key="k",
            http_get_json=lambda u, p: {"message": "invalid resource"},
        )
        result = src.run()
        self.assertEqual(result.status, IngestionRun.Status.SOURCE_UNAVAILABLE)

    def test_missing_csv_file_reports_source_unavailable(self):
        src = CsvDownloadSource(
            self._config(), path="/no/such/file-xyz.csv"
        )
        result = src.run()
        self.assertEqual(result.status, IngestionRun.Status.SOURCE_UNAVAILABLE)


class TradeCsvTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.coal = Commodity.objects.create(
            name="Thermal Coal", category=Commodity.Category.COAL_THERMAL
        )

    def test_csv_download_into_trade_observation(self):
        csv_text = (
            "period,commodity,partner,qty,value\n"
            "2026-07-01,Thermal Coal,Australia,500000,45000000\n"
            "2026-07-01,Thermal Coal,Indonesia,300000,21000000\n"
        )
        config = DatasetConfig(
            target=TARGET_TRADE,
            field_map={
                "period": "period",
                "commodity_name": "commodity",
                "partner_country": "partner",
                "quantity_tonnes": "qty",
                "trade_value": "value",
            },
            constants={"currency": "USD"},
            source="data.gov.in — Coal imports (test)",
            source_url="https://data.gov.in/resource/trade",
            source_date="2026-08-15",
        )
        src = CsvDownloadSource(config, csv_text=csv_text)
        result = src.run()

        self.assertEqual(result.status, IngestionRun.Status.SUCCESS)
        self.assertEqual(TradeObservation.objects.count(), 2)
        au = TradeObservation.objects.get(partner_country="Australia")
        self.assertEqual(str(au.quantity_tonnes), "500000.00")
        self.assertEqual(au.currency, "USD")
        self.assertEqual(au.source_url, "https://data.gov.in/resource/trade")
        self.assertEqual(au.source_date, date(2026, 8, 15))
        self.assertIsNotNone(au.retrieved_at)

    def test_idempotent_reingest(self):
        csv_text = "period,commodity,qty\n2026-07-01,Thermal Coal,500000\n"
        config = DatasetConfig(
            target=TARGET_TRADE,
            field_map={"period": "period", "commodity_name": "commodity", "quantity_tonnes": "qty"},
            source="src", source_url="https://data.gov.in/x",
        )
        CsvDownloadSource(config, csv_text=csv_text).run()
        result2 = CsvDownloadSource(config, csv_text=csv_text).run()
        self.assertEqual(TradeObservation.objects.count(), 1)
        self.assertEqual(result2.duplicate, 1)


class MinistryOfCoalTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.coal = Commodity.objects.create(
            name="Coking Coal", category=Commodity.Category.COAL_COKING
        )

    def test_coal_price_csv_ingestion(self):
        csv_text = (
            "date,grade,price_inr\n"
            "2026-08-01,Coking Coal,8500\n"
        )
        config = DatasetConfig(
            target=TARGET_COMMODITY_PRICE,
            field_map={
                "observed_on": "date",
                "commodity_name": "grade",
                "price": "price_inr",
            },
            constants={"currency": "INR", "unit": "tonne"},
            source="Ministry of Coal (test export)",
            source_url="https://coal.gov.in/statistics",
            source_date="2026-08-10",
        )
        src = MinistryOfCoalSource(config, csv_text=csv_text)
        result = src.run()

        self.assertEqual(result.status, IngestionRun.Status.SUCCESS)
        self.assertEqual(src.source_kind, IngestionRun.SourceKind.FILE)
        price = CommodityPriceObservation.objects.get()
        self.assertEqual(str(price.price), "8500.0000")
        self.assertEqual(price.currency, "INR")
        self.assertEqual(price.source, "Ministry of Coal (test export)")
        self.assertEqual(price.source_date, date(2026, 8, 10))
        self.assertIsNotNone(price.retrieved_at)


@override_settings(EXTERNAL_APIS={"DATA_GOV_API_KEY": ""})
class ApiKeyConfigTests(TestCase):
    def test_missing_api_key_fails_config(self):
        config = DatasetConfig(
            target=TARGET_PORT_TRAFFIC,
            field_map={"period": "month", "port_name": "port"},
            source="s", source_url="https://data.gov.in/x",
        )
        # No injected http and no key -> SourceConfigError inside fetch -> FAILED.
        src = DataGovInApiSource(config, resource_id="r")
        result = src.run()
        self.assertEqual(result.status, IngestionRun.Status.FAILED)

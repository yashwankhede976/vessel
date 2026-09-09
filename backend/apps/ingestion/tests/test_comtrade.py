"""Tests for the UN Comtrade adapter using recorded mock API responses.

No network: a fake HTTP callable returns (status_code, json_body) so we exercise
parsing, raw+normalized storage, and rate-limit handling deterministically.
"""
from datetime import date
from decimal import Decimal

from django.test import TestCase, override_settings

from apps.catalog.models import Origin
from apps.ingestion.models import IngestionRun
from apps.ingestion.sources.comtrade import ComtradeSource
from apps.operations.models import TradeObservation


# ---- recorded mock Comtrade Plus responses (trimmed to relevant fields) ----
def coal_import_body():
    """India (699) coal (2701) imports from Australia (36) and Indonesia (360)."""
    return {
        "elapsedTime": "0.1 secs",
        "count": 2,
        "data": [
            {
                "typeCode": "C",
                "freqCode": "A",
                "period": "2024",
                "reporterCode": 699,
                "reporterDesc": "India",
                "flowCode": "M",
                "flowDesc": "Import",
                "partnerCode": 36,
                "partnerDesc": "Australia",
                "cmdCode": "2701",
                "cmdDesc": "Coal; briquettes, ovoids etc",
                "qty": 50000000,
                "qtyUnitAbbr": "kg",
                "netWgt": 50000000,
                "primaryValue": 6500000000,
            },
            {
                "period": "2024",
                "reporterCode": 699,
                "reporterDesc": "India",
                "flowCode": "M",
                "partnerCode": 360,
                "partnerDesc": "Indonesia",
                "cmdCode": "2701",
                "qty": 80000000,
                "qtyUnitAbbr": "kg",
                "netWgt": 80000000,
                "primaryValue": 7200000000,
            },
        ],
    }


def fake_http(status, body):
    calls = {"n": 0}

    def _get(url, params):
        calls["n"] += 1
        return status, body

    _get.calls = calls
    return _get


@override_settings(EXTERNAL_APIS={"COMTRADE_API_KEY": "test-key"})
class ComtradeIngestionTests(TestCase):
    def test_ingests_coal_imports_with_raw_and_normalized(self):
        src = ComtradeSource(api_key="test-key", http_get=fake_http(200, coal_import_body()))
        result = src.run()

        self.assertEqual(result.status, IngestionRun.Status.SUCCESS)
        self.assertEqual(TradeObservation.objects.count(), 2)

        au = TradeObservation.objects.get(partner_country="Australia")
        # Normalized fields.
        self.assertEqual(au.reporter_country, "India")
        self.assertEqual(au.hs_code, "2701")
        self.assertEqual(au.flow, TradeObservation.Flow.IMPORT)
        self.assertEqual(au.period, date(2024, 1, 1))
        self.assertEqual(au.net_weight_kg, Decimal("50000000.00"))
        self.assertEqual(au.quantity_tonnes, Decimal("50000.00"))  # kg -> t
        self.assertEqual(au.trade_value, Decimal("6500000000.00"))
        self.assertEqual(au.qty_unit, "kg")
        self.assertEqual(au.currency, "USD")
        # Raw stored verbatim.
        self.assertEqual(au.raw["partnerDesc"], "Australia")
        self.assertEqual(au.raw["cmdCode"], "2701")
        # Provenance.
        self.assertEqual(au.source, "un_comtrade")
        self.assertIn("comtradeapi.un.org", au.source_url)
        self.assertIsNotNone(au.retrieved_at)

    def test_links_origin_when_known(self):
        Origin.objects.create(name="Australia (Newcastle)", country="Australia")
        src = ComtradeSource(api_key="test-key", http_get=fake_http(200, coal_import_body()))
        src.run()
        au = TradeObservation.objects.get(partner_country="Australia")
        self.assertIsNotNone(au.origin)

    def test_missing_quantity_leaves_nulls_not_fabricated(self):
        body = {
            "data": [
                {
                    "period": "2024", "reporterCode": 699, "reporterDesc": "India",
                    "flowCode": "M", "partnerCode": 508, "partnerDesc": "Mozambique",
                    "cmdCode": "2701", "primaryValue": 120000000,
                    # no qty / netWgt / qtyUnitAbbr
                }
            ]
        }
        src = ComtradeSource(api_key="test-key", http_get=fake_http(200, body))
        src.run()
        mz = TradeObservation.objects.get(partner_country="Mozambique")
        self.assertIsNone(mz.quantity_tonnes)
        self.assertIsNone(mz.net_weight_kg)
        self.assertEqual(mz.trade_value, Decimal("120000000.00"))

    def test_non_coal_hs_is_ignored(self):
        body = {"data": [{
            "period": "2024", "reporterCode": 699, "flowCode": "M",
            "partnerCode": 36, "partnerDesc": "Australia", "cmdCode": "1001",  # wheat
            "primaryValue": 1,
        }]}
        src = ComtradeSource(api_key="test-key", http_get=fake_http(200, body))
        result = src.run()
        self.assertEqual(TradeObservation.objects.count(), 0)
        self.assertEqual(result.written, 0)

    def test_idempotent_reingest(self):
        src1 = ComtradeSource(api_key="test-key", http_get=fake_http(200, coal_import_body()))
        src1.run()
        src2 = ComtradeSource(api_key="test-key", http_get=fake_http(200, coal_import_body()))
        result2 = src2.run()
        self.assertEqual(TradeObservation.objects.count(), 2)
        self.assertEqual(result2.duplicate, 2)


@override_settings(EXTERNAL_APIS={"COMTRADE_API_KEY": "test-key"})
class ComtradeRateLimitTests(TestCase):
    def test_rate_limit_retries_then_succeeds(self):
        # First two calls 429, third 200.
        seq = {"n": 0}

        def flaky_get(url, params):
            seq["n"] += 1
            if seq["n"] < 3:
                return 429, {"message": "rate limit"}
            return 200, coal_import_body()

        src = ComtradeSource(api_key="test-key", http_get=flaky_get)
        src.backoff_seconds = 0  # no real sleeping
        result = src.run()
        self.assertEqual(result.status, IngestionRun.Status.SUCCESS)
        self.assertEqual(seq["n"], 3)

    def test_rate_limit_exhausted_reports_source_unavailable(self):
        src = ComtradeSource(api_key="test-key", http_get=fake_http(429, {"message": "rate limit"}))
        src.backoff_seconds = 0
        result = src.run()
        self.assertEqual(result.status, IngestionRun.Status.SOURCE_UNAVAILABLE)

    def test_server_error_reports_source_unavailable(self):
        src = ComtradeSource(api_key="test-key", http_get=fake_http(503, {}))
        src.backoff_seconds = 0
        result = src.run()
        self.assertEqual(result.status, IngestionRun.Status.SOURCE_UNAVAILABLE)

    def test_no_data_key_reports_source_unavailable(self):
        src = ComtradeSource(api_key="test-key", http_get=fake_http(200, {"message": "no data"}))
        result = src.run()
        self.assertEqual(result.status, IngestionRun.Status.SOURCE_UNAVAILABLE)

    def test_auth_failure_is_config_error(self):
        src = ComtradeSource(api_key="test-key", http_get=fake_http(403, {}))
        result = src.run()
        self.assertEqual(result.status, IngestionRun.Status.FAILED)


class ComtradeConfigTests(TestCase):
    @override_settings(EXTERNAL_APIS={"COMTRADE_API_KEY": ""})
    def test_missing_key_fails(self):
        src = ComtradeSource()  # no key, no injected http
        result = src.run()
        self.assertEqual(result.status, IngestionRun.Status.FAILED)

    @override_settings(EXTERNAL_APIS={"COMTRADE_API_KEY": "secret"})
    def test_query_params_include_scope_and_key(self):
        src = ComtradeSource()
        params = src._query_params()
        self.assertEqual(params["reporterCode"], "699")  # India
        self.assertEqual(params["subscription-key"], "secret")
        self.assertIn("2701", params["cmdCode"])
        # All five origins present.
        for code in ("36", "360", "508", "842", "643"):
            self.assertIn(code, params["partnerCode"])

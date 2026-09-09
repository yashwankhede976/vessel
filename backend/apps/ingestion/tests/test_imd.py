"""Tests for the IMD adapter using mocked product responses.

No network: http_get_json is injected. Covers each marine product type,
cyclone track + wind warning, missing-data handling, and unavailability.
"""
from datetime import datetime, timezone as dt_tz
from decimal import Decimal

from django.test import TestCase

from apps.catalog.models import Port
from apps.ingestion.models import IngestionRun
from apps.ingestion.sources.imd import (
    IMDProductConfig,
    IMDSource,
    PRODUCT_COASTAL_BULLETIN,
    PRODUCT_CYCLONE_TRACK,
    PRODUCT_CYCLONE_WIND_WARNING,
    PRODUCT_PORT_WARNING,
    PRODUCT_SEA_AREA_BULLETIN,
)
from apps.operations.models import (
    CycloneObservation,
    MarineObservation,
    MarineWarningType,
    WarningSeverity,
)


def http_returning(payload):
    def _get(url):
        return payload

    return _get


class PortWarningTests(TestCase):
    def _config(self):
        return IMDProductConfig(
            product=PRODUCT_PORT_WARNING,
            url="https://mausam.imd.gov.in/port-warnings.json",
            field_map={
                "issue_time": "issued",
                "valid_from": "from",
                "valid_to": "to",
                "port_name": "port",
                "severity": "warning_level",
                "headline": "text",
            },
            source_ref="IMD-PORT-BULLETIN",
        )

    def test_port_warning_maps_to_marine_observation(self):
        payload = [
            {
                "issued": "2026-09-09T06:00:00Z",
                "from": "2026-09-09T06:00:00Z",
                "to": "2026-09-10T06:00:00Z",
                "port": "Paradip",
                "warning_level": "orange",
                "text": "Signal number three hoisted.",
                "extra_field": "ignored",
            }
        ]
        src = IMDSource(self._config(), http_get_json=http_returning(payload))
        result = src.run()
        self.assertEqual(result.status, IngestionRun.Status.SUCCESS)

        obs = MarineObservation.objects.get()
        self.assertEqual(obs.warning_type, MarineWarningType.PORT_WARNING)
        self.assertEqual(obs.port, Port.objects.get(name="Paradip"))
        self.assertEqual(obs.severity, WarningSeverity.MODERATE)  # orange -> moderate
        self.assertEqual(obs.headline, "Signal number three hoisted.")
        self.assertEqual(obs.issue_time, datetime(2026, 9, 9, 6, 0, tzinfo=dt_tz.utc))
        self.assertEqual(obs.valid_to, datetime(2026, 9, 10, 6, 0, tzinfo=dt_tz.utc))
        self.assertEqual(obs.source_ref, "IMD-PORT-BULLETIN")
        # Raw retained; undeclared field lives only in raw, not on the model.
        self.assertEqual(obs.raw["extra_field"], "ignored")

    def test_unknown_severity_text_maps_to_unknown(self):
        payload = [{"issued": "2026-09-09T06:00:00Z", "port": "Paradip", "warning_level": "purple"}]
        IMDSource(self._config(), http_get_json=http_returning(payload)).run()
        self.assertEqual(MarineObservation.objects.get().severity, WarningSeverity.UNKNOWN)


class SeaAreaAndCoastalTests(TestCase):
    def test_sea_area_bulletin_by_area(self):
        config = IMDProductConfig(
            product=PRODUCT_SEA_AREA_BULLETIN,
            url="https://mausam.imd.gov.in/sea-area.json",
            field_map={
                "issue_time": "issued", "area_name": "area", "severity": "sev",
                "significant_wave_height_m": "wave_m",
            },
            records_key="bulletins",
        )
        payload = {"bulletins": [
            {"issued": "2026-09-09T03:00:00Z", "area": "Northwest Bay of Bengal",
             "sev": "high", "wave_m": "3.5"},
        ]}
        src = IMDSource(config, http_get_json=http_returning(payload))
        result = src.run()
        self.assertEqual(result.status, IngestionRun.Status.SUCCESS)
        obs = MarineObservation.objects.get()
        self.assertEqual(obs.warning_type, MarineWarningType.SEA_AREA_BULLETIN)
        self.assertEqual(obs.area_name, "Northwest Bay of Bengal")
        self.assertEqual(obs.severity, WarningSeverity.HIGH)
        self.assertEqual(obs.significant_wave_height_m, Decimal("3.50"))
        self.assertIsNone(obs.port)  # area-level, no port
        self.assertIsNone(obs.latitude)  # not provided -> null, not fabricated

    def test_coastal_bulletin(self):
        config = IMDProductConfig(
            product=PRODUCT_COASTAL_BULLETIN,
            url="https://mausam.imd.gov.in/coastal.json",
            field_map={"issue_time": "issued", "area_name": "coast", "severity": "sev"},
        )
        payload = [{"issued": "2026-09-09T03:00:00Z", "coast": "Odisha coast", "sev": "low"}]
        IMDSource(config, http_get_json=http_returning(payload)).run()
        obs = MarineObservation.objects.get()
        self.assertEqual(obs.warning_type, MarineWarningType.COASTAL_BULLETIN)
        self.assertEqual(obs.area_name, "Odisha coast")

    def test_record_without_area_or_port_skipped(self):
        config = IMDProductConfig(
            product=PRODUCT_COASTAL_BULLETIN,
            url="https://x/y.json",
            field_map={"issue_time": "issued", "severity": "sev"},
        )
        payload = [{"issued": "2026-09-09T03:00:00Z", "sev": "low"}]  # no area/port
        result = IMDSource(config, http_get_json=http_returning(payload)).run()
        self.assertEqual(MarineObservation.objects.count(), 0)
        self.assertEqual(result.written, 0)


class CycloneTests(TestCase):
    def test_cyclone_track_points(self):
        config = IMDProductConfig(
            product=PRODUCT_CYCLONE_TRACK,
            url="https://mausam.imd.gov.in/cyclone-track.json",
            field_map={
                "system_name": "name", "advisory_no": "adv", "timestamp": "time",
                "latitude": "lat", "longitude": "lon", "category": "cat",
                "max_wind_kn": "wind_kn", "central_pressure_hpa": "pressure",
            },
            records_key="track",
        )
        payload = {"track": [
            {"name": "CycloneX", "adv": "12", "time": "2026-09-09T00:00:00Z",
             "lat": "15.5", "lon": "88.0", "cat": "Severe Cyclonic Storm",
             "wind_kn": "75", "pressure": "980"},
            {"name": "CycloneX", "adv": "13", "time": "2026-09-09T06:00:00Z",
             "lat": "16.2", "lon": "87.5", "cat": "Very Severe Cyclonic Storm",
             "wind_kn": "95", "pressure": "965"},
        ]}
        src = IMDSource(config, http_get_json=http_returning(payload))
        result = src.run()
        self.assertEqual(result.status, IngestionRun.Status.SUCCESS)
        self.assertEqual(CycloneObservation.objects.count(), 2)
        pt = CycloneObservation.objects.get(advisory_no="13")
        self.assertEqual(pt.category, CycloneObservation.Category.VERY_SEVERE)
        self.assertEqual(pt.max_wind_kn, Decimal("95.00"))
        self.assertEqual(pt.bulletin_kind, CycloneObservation.BulletinKind.TRACK)
        self.assertEqual(pt.latitude, Decimal("16.200000"))

    def test_cyclone_wind_warning(self):
        config = IMDProductConfig(
            product=PRODUCT_CYCLONE_WIND_WARNING,
            url="https://mausam.imd.gov.in/wind-warning.json",
            field_map={
                "system_name": "name", "timestamp": "time", "severity": "sev",
                "max_wind_kn": "sustained_kn", "gust_kn": "gust_kn",
            },
        )
        payload = [{"name": "CycloneX", "time": "2026-09-09T06:00:00Z",
                    "sev": "red", "sustained_kn": "95", "gust_kn": "115"}]
        src = IMDSource(config, http_get_json=http_returning(payload))
        src.run()
        w = CycloneObservation.objects.get()
        self.assertEqual(w.bulletin_kind, CycloneObservation.BulletinKind.WIND_WARNING)
        self.assertEqual(w.severity, WarningSeverity.SEVERE)  # red -> severe
        self.assertEqual(w.gust_kn, Decimal("115.00"))
        self.assertIsNone(w.latitude)  # wind warning has no track point
        self.assertFalse(w.is_forecast)

    def test_cyclone_missing_name_or_time_skipped(self):
        config = IMDProductConfig(
            product=PRODUCT_CYCLONE_TRACK, url="https://x/y.json",
            field_map={"system_name": "name", "timestamp": "time"},
        )
        payload = [{"name": "", "time": "2026-09-09T00:00:00Z"},
                   {"name": "CycloneY", "time": None}]
        result = IMDSource(config, http_get_json=http_returning(payload)).run()
        self.assertEqual(CycloneObservation.objects.count(), 0)
        self.assertEqual(result.written, 0)


class UnavailableAndConfigTests(TestCase):
    def _marine_config(self):
        return IMDProductConfig(
            product=PRODUCT_PORT_WARNING, url="https://x/y.json",
            field_map={"issue_time": "issued", "port_name": "port"},
        )

    def test_no_records_reports_source_unavailable(self):
        src = IMDSource(self._marine_config(), http_get_json=lambda u: {"message": "down"})
        # records_key is "" so payload must be a list; a dict without list -> unavailable
        result = src.run()
        self.assertEqual(result.status, IngestionRun.Status.SOURCE_UNAVAILABLE)

    def test_http_error_reports_source_unavailable(self):
        from apps.ingestion.exceptions import SourceUnavailableError

        def boom(url):
            raise SourceUnavailableError("404")

        result = IMDSource(self._marine_config(), http_get_json=boom).run()
        self.assertEqual(result.status, IngestionRun.Status.SOURCE_UNAVAILABLE)

    def test_invalid_product_raises_config_error(self):
        with self.assertRaises(Exception):
            IMDProductConfig(product="nonsense", url="x", field_map={"a": "b"})

    def test_idempotent_reingest(self):
        config = IMDProductConfig(
            product=PRODUCT_PORT_WARNING, url="https://x/y.json",
            field_map={"issue_time": "issued", "port_name": "port", "severity": "sev"},
        )
        payload = [{"issued": "2026-09-09T06:00:00Z", "port": "Paradip", "sev": "low"}]
        IMDSource(config, http_get_json=http_returning(payload)).run()
        result2 = IMDSource(config, http_get_json=http_returning(payload)).run()
        self.assertEqual(MarineObservation.objects.count(), 1)
        self.assertEqual(result2.duplicate, 1)

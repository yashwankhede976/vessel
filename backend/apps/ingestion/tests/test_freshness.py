"""Tests for the data-freshness classifier and external-service health."""
from datetime import timedelta
from decimal import Decimal

from django.test import TestCase, override_settings
from django.utils import timezone

from apps.catalog.models import Vessel
from apps.ingestion.freshness import (
    FRESH,
    UNKNOWN,
    VERY_STALE,
    classify_age,
    data_freshness,
    external_services,
)
from apps.ingestion.models import IngestionRun
from apps.operations.models import AISPosition


class ClassifyAgeTests(TestCase):
    def test_levels(self):
        self.assertEqual(classify_age(None, (6, 24)), UNKNOWN)
        self.assertEqual(classify_age(2, (6, 24)), FRESH)
        self.assertEqual(classify_age(12, (6, 24)), "STALE")
        self.assertEqual(classify_age(100, (6, 24)), VERY_STALE)


class DataFreshnessTests(TestCase):
    def test_unknown_when_no_data(self):
        entries = {e.dataset: e for e in data_freshness()}
        self.assertEqual(entries["ais_positions"].level, UNKNOWN)
        self.assertIsNone(entries["ais_positions"].latest_at)

    def test_fresh_when_recent(self):
        v = Vessel.objects.create(
            imo="9000001", name="Fresh", dwt=Decimal("50000"),
            loa=Decimal("190"), beam=Decimal("30"), draft=Decimal("11"),
        )
        AISPosition.objects.create(
            vessel=v, mmsi="123456789", timestamp=timezone.now(),
            latitude=Decimal("20"), longitude=Decimal("86"),
        )
        entries = {e.dataset: e for e in data_freshness()}
        self.assertEqual(entries["ais_positions"].level, FRESH)
        self.assertEqual(entries["ais_positions"].record_count, 1)

    def test_very_stale_when_old(self):
        v = Vessel.objects.create(
            imo="9000002", name="Old", dwt=Decimal("50000"),
            loa=Decimal("190"), beam=Decimal("30"), draft=Decimal("11"),
        )
        AISPosition.objects.create(
            vessel=v, mmsi="223456789",
            timestamp=timezone.now() - timedelta(days=5),
            latitude=Decimal("20"), longitude=Decimal("86"),
        )
        entries = {e.dataset: e for e in data_freshness()}
        self.assertEqual(entries["ais_positions"].level, VERY_STALE)


class ExternalServicesTests(TestCase):
    @override_settings(EXTERNAL_APIS={"AISSTREAM_API_KEY": "", "DATA_GOV_API_KEY": ""})
    def test_keyless_providers_always_configured(self):
        services = {s.provider: s for s in external_services()}
        # Keyless providers are configured regardless of settings.
        self.assertTrue(services["open_meteo"].configured)
        self.assertTrue(services["world_bank"].configured)
        self.assertTrue(services["incois"].configured)
        # Key-required providers with empty keys are NOT configured.
        self.assertFalse(services["aisstream"].configured)
        self.assertFalse(services["data_gov_in"].configured)

    @override_settings(EXTERNAL_APIS={"AISSTREAM_API_KEY": "present"})
    def test_key_present_marks_configured(self):
        services = {s.provider: s for s in external_services()}
        self.assertTrue(services["aisstream"].configured)

    def test_never_exposes_api_keys(self):
        for s in external_services():
            payload = str(s.to_dict()).lower()
            self.assertNotIn("api_key", payload)
            self.assertNotIn("secret", payload)

    def test_last_success_from_ingestion_run(self):
        IngestionRun.objects.create(
            source_key="open_meteo", status=IngestionRun.Status.SUCCESS,
            finished_at=timezone.now(),
        )
        services = {s.provider: s for s in external_services()}
        self.assertIsNotNone(services["open_meteo"].last_success)
        self.assertIsNone(services["open_meteo"].last_failure)

    def test_last_failure_from_ingestion_run(self):
        IngestionRun.objects.create(
            source_key="un_comtrade", status=IngestionRun.Status.SOURCE_UNAVAILABLE,
            finished_at=timezone.now(),
        )
        services = {s.provider: s for s in external_services()}
        self.assertIsNotNone(services["un_comtrade"].last_failure)

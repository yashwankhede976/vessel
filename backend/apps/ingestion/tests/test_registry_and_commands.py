"""Tests for registry autodiscovery and the ingestion management commands."""
from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from apps.ingestion import sources as _sources
from apps.ingestion.registry import get_source, list_sources


class RegistryAutodiscoveryTests(TestCase):
    def setUp(self):
        # Other test modules may clear() the registry; re-populate defensively.
        _sources.register_all()

    def test_all_sources_registered(self):
        # Importing apps.ingestion.sources registers every concrete source.
        keys = set(list_sources())
        expected = {
            "aisstream", "un_comtrade", "data_gov_in", "india_csv_download",
            "ministry_of_coal", "open_meteo", "imd", "incois", "world_bank",
        }
        self.assertTrue(expected <= keys, f"missing: {expected - keys}")

    def test_get_source_resolves_class(self):
        self.assertEqual(get_source("world_bank").key, "world_bank")

    def test_self_configuring_set(self):
        self.assertIn("open_meteo", _sources.SELF_CONFIGURING)
        self.assertIn("world_bank", _sources.SELF_CONFIGURING)
        self.assertNotIn("imd", _sources.SELF_CONFIGURING)


class ListCommandTests(TestCase):
    def test_lists_sources(self):
        out = StringIO()
        call_command("list_ingestion_sources", stdout=out)
        text = out.getvalue()
        self.assertIn("world_bank", text)
        self.assertIn("incois", text)
        self.assertIn("requires config", text)


class RunCommandTests(TestCase):
    def test_config_driven_source_rejected(self):
        with self.assertRaises(CommandError):
            call_command("run_ingestion", "imd")

    def test_unknown_source_rejected(self):
        with self.assertRaises(CommandError):
            call_command("run_ingestion", "does_not_exist")

    def test_aisstream_streaming_rejected(self):
        with self.assertRaises(CommandError):
            call_command("run_ingestion", "aisstream")

    def test_world_bank_runs_but_degrades_without_network(self):
        # No injected transport and no 'requests' behaviour in tests -> the run
        # records SOURCE_UNAVAILABLE / FAILED but MUST NOT crash the command.
        out = StringIO()
        try:
            call_command("run_ingestion", "world_bank", stdout=out)
        except CommandError:
            self.fail("run_ingestion should not raise for an unavailable provider")

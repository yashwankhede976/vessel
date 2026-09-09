"""Tests for the seed_ports management command."""
from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from apps.catalog.models import Berth, Port


class SeedPortsCommandTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        # Run the importer once against the shipped curated dataset.
        call_command("seed_ports", stdout=StringIO())

    def test_all_seven_ports_present(self):
        expected = {
            "Paradip",
            "Visakhapatnam",
            "Gangavaram",
            "Gopalpur",
            "Dhamra",
            "Sagar/Sandheads",
            "Haldia",
        }
        names = set(Port.objects.values_list("name", flat=True))
        self.assertTrue(expected.issubset(names))

    def test_metadata_has_field_provenance(self):
        paradip = Port.objects.get(name="Paradip")
        draft = paradip.metadata["max_draft_m"]
        self.assertEqual(draft["value"], "16.50")
        self.assertIn("paradipport", draft["source"].lower())
        self.assertEqual(draft["source_date"], "2026-09-08")

    def test_unknown_values_preserved_not_estimated(self):
        dhamra = Port.objects.get(name="Dhamra")
        self.assertEqual(dhamra.metadata["max_draft_m"]["value"], "UNKNOWN")
        sandheads = Port.objects.get(name="Sagar/Sandheads")
        self.assertEqual(sandheads.metadata["cargo_types"]["value"], "UNKNOWN")
        self.assertEqual(sandheads.port_type, "anchorage")

    def test_berth_created_only_with_published_dimensions(self):
        # Vizag EQ1 has published LOA/beam/draft -> created.
        eq1 = Berth.objects.get(berth_name="EQ1 (Inner Harbour)")
        self.assertEqual(str(eq1.max_loa), "230.00")
        self.assertEqual(str(eq1.max_draft), "14.50")
        # Provenance is retained on the berth.
        self.assertIn("provenance", eq1.special_constraints)
        # Berths missing a published dimension (beam) are NOT created.
        self.assertFalse(
            Berth.objects.filter(berth_name="HDC Berth 1").exists()
        )

    def test_idempotent(self):
        before = Port.objects.count()
        call_command("seed_ports", stdout=StringIO())
        self.assertEqual(Port.objects.count(), before)

    def test_dry_run_makes_no_changes(self):
        Berth.objects.all().delete()
        Port.objects.all().delete()
        call_command("seed_ports", "--dry-run", stdout=StringIO())
        self.assertEqual(Port.objects.count(), 0)

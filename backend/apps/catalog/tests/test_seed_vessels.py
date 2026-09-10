"""Tests for the seed_vessels management command."""
from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from apps.catalog.models import Vessel


class SeedVesselsCommandTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_vessels", stdout=StringIO())

    def test_seeds_all_vessel_types(self):
        types = set(Vessel.objects.values_list("vessel_type", flat=True))
        expected = {
            "handysize", "supramax", "ultramax", "panamax",
            "kamsarmax", "post_panamax", "capesize",
        }
        self.assertTrue(expected.issubset(types))

    def test_columns_and_metadata_populated(self):
        v = Vessel.objects.get(imo="9700007")  # Paradip Panamax
        self.assertEqual(v.name, "Paradip Panamax")
        self.assertEqual(v.vessel_type, "panamax")
        self.assertEqual(str(v.draft), "14.00")
        self.assertEqual(v.availability_status, "open")
        # Provenance metadata stored, labelled SYNTHETIC.
        self.assertEqual(v.metadata["class_society"]["value"], "ABS")
        self.assertIn("SYNTHETIC", v.metadata["class_society"]["source"])

    def test_unknown_metadata_preserved_not_estimated(self):
        v = Vessel.objects.get(imo="9700001")  # Kolkata Trader
        self.assertEqual(v.metadata["ice_class"]["value"], "UNKNOWN")

    def test_mixed_availability_statuses_present(self):
        statuses = set(Vessel.objects.values_list("availability_status", flat=True))
        # The dataset intentionally spreads statuses for the summary demo.
        self.assertTrue({"open", "laden", "ballast", "fixed"}.issubset(statuses))

    def test_idempotent(self):
        before = Vessel.objects.count()
        call_command("seed_vessels", stdout=StringIO())
        self.assertEqual(Vessel.objects.count(), before)

    def test_dry_run_makes_no_changes(self):
        Vessel.objects.all().delete()
        call_command("seed_vessels", "--dry-run", stdout=StringIO())
        self.assertEqual(Vessel.objects.count(), 0)

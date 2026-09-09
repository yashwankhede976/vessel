"""Tests for the ingestion framework: run lifecycle, retry, validation,
normalization, deduplication, registry, and task wrappers."""
from datetime import date
from decimal import Decimal

from django.test import TestCase, SimpleTestCase

from apps.ingestion import normalizers as N
from apps.ingestion import validators as V
from apps.ingestion.dedup import dedupe, make_key
from apps.ingestion.exceptions import (
    FetchError,
    NormalizationError,
    RegistryError,
    ValidationError,
)
from apps.ingestion.models import IngestionRun
from apps.ingestion import registry
from apps.ingestion.tasks import run_source

from .fakes import FakeFatalRestSource, FakeFileSource, FakeRestSource


def _rest_payload():
    return [
        {"route": "AU-PARADIP", "observed_on": "2026-09-01", "rate": " 18.75 "},
        {"route": "ID-VIZAG", "observed_on": "2026-09-01", "rate": "15.20"},
    ]


class RunLifecycleTests(TestCase):
    def test_successful_run_records_status_and_counts(self):
        source = FakeRestSource(payload=_rest_payload())
        result = source.run()

        self.assertEqual(result.status, IngestionRun.Status.SUCCESS)
        self.assertEqual(result.fetched, 2)
        self.assertEqual(result.valid, 2)
        self.assertEqual(result.invalid, 0)
        self.assertEqual(result.written, 2)

        run = IngestionRun.objects.get(pk=result.run_id)
        self.assertEqual(run.status, IngestionRun.Status.SUCCESS)
        self.assertIsNotNone(run.started_at)
        self.assertIsNotNone(run.finished_at)
        self.assertEqual(run.source_kind, IngestionRun.SourceKind.REST)
        self.assertIsNotNone(run.duration_seconds)

    def test_normalization_applied(self):
        source = FakeRestSource(payload=_rest_payload())
        source.run()
        rec = source.persisted[0]
        # rate renamed + Decimal, string trimmed, date parsed.
        self.assertEqual(rec["rate_per_tonne"], Decimal("18.75"))
        self.assertEqual(rec["observed_on"], date(2026, 9, 1))

    def test_invalid_records_make_run_partial(self):
        payload = _rest_payload() + [
            {"route": "", "observed_on": "2026-09-02", "rate": "10"},  # missing route
            {"route": "X", "observed_on": "2026-09-02", "rate": "-5"},  # negative rate
        ]
        source = FakeRestSource(payload=payload)
        result = source.run()
        self.assertEqual(result.status, IngestionRun.Status.PARTIAL)
        self.assertEqual(result.invalid, 2)
        self.assertEqual(result.valid, 2)
        run = IngestionRun.objects.get(pk=result.run_id)
        self.assertEqual(len(run.errors), 2)
        # Error tracking carries field + type.
        self.assertTrue(any(e.get("field") == "route" for e in run.errors))


class RetryTests(TestCase):
    def test_retries_then_succeeds(self):
        source = FakeRestSource(payload=_rest_payload(), fail_times=2)
        result = source.run()
        self.assertEqual(result.status, IngestionRun.Status.SUCCESS)
        self.assertEqual(result.attempts, 3)  # 2 failures + 1 success

    def test_exhausts_retries_and_fails(self):
        source = FakeRestSource(payload=_rest_payload(), fail_times=5)  # > max_attempts
        result = source.run()
        self.assertEqual(result.status, IngestionRun.Status.FAILED)
        self.assertEqual(result.attempts, 3)
        self.assertIn("transient boom", result.error_message)

    def test_non_retryable_fetch_fails_immediately(self):
        source = FakeFatalRestSource(payload=_rest_payload())
        result = source.run()
        self.assertEqual(result.status, IngestionRun.Status.FAILED)
        self.assertEqual(result.attempts, 1)  # no retries for non-retryable


class DedupTests(TestCase):
    def test_in_batch_dedup(self):
        payload = _rest_payload() + [
            # Exact duplicate of the first record (same route+date).
            {"route": "AU-PARADIP", "observed_on": "2026-09-01", "rate": "99"},
        ]
        source = FakeRestSource(payload=payload)
        result = source.run()
        self.assertEqual(result.fetched, 3)
        self.assertEqual(result.duplicate, 1)  # one dropped in-batch
        self.assertEqual(result.written, 2)

    def test_dedupe_helper(self):
        rows = [{"a": 1}, {"a": 1}, {"a": 2}]
        unique, dups = dedupe(rows, make_key("a"))
        self.assertEqual(len(unique), 2)
        self.assertEqual(dups, 1)


class FileSourceTests(TestCase):
    def test_file_source_runs(self):
        source = FakeFileSource(rows=[{"name": "x", "value": "3.5"}])
        result = source.run()
        self.assertEqual(result.status, IngestionRun.Status.SUCCESS)
        self.assertEqual(source.persisted[0]["value"], Decimal("3.5"))
        run = IngestionRun.objects.get(pk=result.run_id)
        self.assertEqual(run.source_kind, IngestionRun.SourceKind.FILE)


class ValidatorNormalizerUnitTests(SimpleTestCase):
    def test_require_fields_raises(self):
        with self.assertRaises(ValidationError):
            V.require_fields("a")({"b": 1})

    def test_numeric_range_bounds(self):
        with self.assertRaises(ValidationError):
            V.numeric_range("x", minimum=0)({"x": "-1"})
        # in-range passes through
        self.assertEqual(V.numeric_range("x", maximum=10)({"x": "5"})["x"], "5")

    def test_to_decimal_bad_value_raises(self):
        with self.assertRaises(NormalizationError):
            N.to_decimal("x")({"x": "not-a-number"})

    def test_rename_and_defaults(self):
        out = N.chain(N.rename_fields({"a": "b"}), N.set_defaults(c=1))({"a": 5})
        self.assertEqual(out, {"b": 5, "c": 1})


class RegistryTests(SimpleTestCase):
    def setUp(self):
        registry.clear()
        self.addCleanup(registry.clear)

    def test_register_and_get(self):
        registry.register(FakeRestSource)
        self.assertIs(registry.get_source("fake_rest"), FakeRestSource)
        self.assertIn("fake_rest", registry.list_sources())

    def test_duplicate_key_raises(self):
        registry.register(FakeRestSource)

        class Other(FakeRestSource):
            pass

        Other.key = "fake_rest"
        with self.assertRaises(RegistryError):
            registry.register(Other)

    def test_unknown_key_raises(self):
        with self.assertRaises(RegistryError):
            registry.get_source("nope")


class TaskWrapperTests(TestCase):
    def setUp(self):
        registry.clear()
        registry.register(FakeRestSource)
        self.addCleanup(registry.clear)

    def test_run_source_by_key(self):
        result = run_source("fake_rest", payload=_rest_payload())
        self.assertEqual(result.status, IngestionRun.Status.SUCCESS)
        self.assertEqual(result.written, 2)

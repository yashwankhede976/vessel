"""Fake in-memory ingestion sources for testing the framework.

These are test doubles, not provider-specific ingestion — they let us exercise
the base pipeline (fetch/retry/normalize/validate/dedup/persist) without any
network or file I/O.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any, Iterable

from apps.ingestion.base import FileIngestionSource, RESTIngestionSource
from apps.ingestion.dedup import make_key
from apps.ingestion.exceptions import FetchError
from apps.ingestion import normalizers as N
from apps.ingestion import validators as V

Record = dict[str, Any]


class FakeRestSource(RESTIngestionSource):
    """A REST source whose HTTP payload is injected in-memory."""

    key = "fake_rest"
    endpoint = "https://example.test/data"
    max_attempts = 3
    backoff_seconds = 0  # no real sleeping in tests

    normalizer = staticmethod(
        N.chain(
            N.strip_strings(),
            N.rename_fields({"rate": "rate_per_tonne"}),
            N.to_decimal("rate_per_tonne"),
            N.to_date("observed_on"),
        )
    )
    validator = staticmethod(
        V.chain(
            V.require_fields("route", "observed_on", "rate_per_tonne"),
            V.numeric_range("rate_per_tonne", minimum=0),
        )
    )
    dedup_key = staticmethod(make_key("route", "observed_on"))

    def __init__(self, payload=None, fail_times: int = 0, **ctx):
        super().__init__(**ctx)
        self._payload = payload if payload is not None else []
        self._fail_times = fail_times
        self._calls = 0
        self.persisted: list[Record] = []

    def _http_get(self):
        self._calls += 1
        if self._calls <= self._fail_times:
            raise FetchError("transient boom", retryable=True)
        return self._payload

    def parse(self, payload) -> Iterable[Record]:
        return payload

    def persist(self, records: list[Record]) -> tuple[int, int]:
        # Persist-level dedup on the natural key.
        seen = {(r["route"], r["observed_on"]) for r in self.persisted}
        written = duplicate = 0
        for r in records:
            k = (r["route"], r["observed_on"])
            if k in seen:
                duplicate += 1
                continue
            seen.add(k)
            self.persisted.append(r)
            written += 1
        return written, duplicate


class FakeFatalRestSource(FakeRestSource):
    key = "fake_rest_fatal"
    max_attempts = 3

    def _http_get(self):
        raise FetchError("permanent boom", retryable=False)


class FakeFileSource(FileIngestionSource):
    """A file source whose rows are injected in-memory (no real file)."""

    key = "fake_file"

    normalizer = staticmethod(N.chain(N.strip_strings(), N.to_decimal("value")))
    validator = staticmethod(V.require_fields("name", "value"))

    def __init__(self, rows=None, **ctx):
        super().__init__(**ctx)
        self.path = "in-memory"
        self._rows = rows or []
        self.persisted: list[Record] = []

    def parse_file(self, path: str) -> Iterable[Record]:
        return self._rows

    def persist(self, records: list[Record]) -> tuple[int, int]:
        self.persisted.extend(records)
        return len(records), 0

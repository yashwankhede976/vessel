"""Base ingestion interface, source adapters, and the run orchestrator.

Pipeline for a run:
    fetch() -> raw records
      -> in-batch dedup (optional natural key)
      -> normalize (each record; failures tracked)
      -> validate  (each record; failures tracked)
      -> persist() (source-owned upsert; returns written/duplicate counts)

Cross-cutting concerns handled here:
- retry handling for fetch (transient FetchError, with backoff)
- ingestion status + timestamps + counters + error tracking via IngestionRun
- structured logging

Provider-specific behaviour is added by subclassing RESTIngestionSource or
FileIngestionSource and implementing the abstract hooks. No provider-specific
ingestion is implemented in this framework module.
"""
from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Iterable, Optional

from django.utils import timezone

from .dedup import KeyFn, dedupe
from .exceptions import (
    FetchError,
    IngestionError,
    NormalizationError,
    SourceConfigError,
    SourceUnavailableError,
    ValidationError,
)
from .models import IngestionRun
from .normalizers import Normalizer
from .validators import Validator

logger = logging.getLogger("vessel.ingestion")

Record = dict[str, Any]


@dataclass
class RunResult:
    """In-memory summary of a completed run (mirrors the IngestionRun row)."""

    run_id: Optional[int]
    status: str
    fetched: int = 0
    valid: int = 0
    invalid: int = 0
    written: int = 0
    duplicate: int = 0
    attempts: int = 0
    errors: list[dict] = field(default_factory=list)
    error_message: str = ""


class BaseIngestionSource(ABC):
    """Abstract ingestion source.

    Subclasses declare a unique `key`, a `source_kind`, and implement `fetch`
    and `persist`. They may also provide a `normalizer`, `validator`, and a
    `dedup_key` for the shared pipeline.
    """

    #: Unique registry key, e.g. "aisstream".
    key: str = ""
    #: One of IngestionRun.SourceKind values.
    source_kind: str = IngestionRun.SourceKind.OTHER

    #: Retry configuration for fetch().
    max_attempts: int = 3
    backoff_seconds: float = 0.5

    #: Optional pipeline hooks (set by subclasses).
    normalizer: Optional[Normalizer] = None
    validator: Optional[Validator] = None
    dedup_key: Optional[KeyFn] = None

    def __init__(self, **context: Any):
        if not self.key:
            raise SourceConfigError("Ingestion source must define a non-empty 'key'.")
        self.context = context

    # --- abstract hooks -------------------------------------------------
    @abstractmethod
    def fetch(self) -> Iterable[Record]:
        """Return raw records from the source. May raise FetchError (retryable)."""

    @abstractmethod
    def persist(self, records: list[Record]) -> tuple[int, int]:
        """Upsert normalized+validated records.

        Returns (written_count, duplicate_count). Implementations should upsert
        on a natural key so re-runs do not create duplicates.
        """

    # --- pipeline -------------------------------------------------------
    def _fetch_with_retry(self, run: IngestionRun) -> list[Record]:
        attempt = 0
        while True:
            attempt += 1
            run.attempts = attempt
            try:
                records = list(self.fetch())
                logger.info(
                    "ingestion.fetch ok source=%s attempt=%d count=%d",
                    self.key, attempt, len(records),
                )
                return records
            except FetchError as exc:
                retryable = getattr(exc, "retryable", True)
                if not retryable or attempt >= self.max_attempts:
                    logger.warning(
                        "ingestion.fetch failed source=%s attempt=%d retryable=%s: %s",
                        self.key, attempt, retryable, exc,
                    )
                    raise
                sleep_for = self.backoff_seconds * (2 ** (attempt - 1))
                logger.info(
                    "ingestion.fetch retry source=%s attempt=%d sleep=%.2fs",
                    self.key, attempt, sleep_for,
                )
                time.sleep(sleep_for)

    def _process(self, raw: list[Record], run: IngestionRun) -> list[Record]:
        """Dedup -> normalize -> validate, tracking per-record errors."""
        # In-batch deduplication.
        if self.dedup_key is not None:
            raw, duplicates = dedupe(raw, self.dedup_key)
            run.records_duplicate += duplicates

        processed: list[Record] = []
        for index, record in enumerate(raw):
            try:
                if self.normalizer is not None:
                    record = self.normalizer(record)
                if self.validator is not None:
                    record = self.validator(record)
            except (ValidationError, NormalizationError) as exc:
                run.records_invalid += 1
                run.errors.append(
                    {
                        "index": index,
                        "type": type(exc).__name__,
                        "field": getattr(exc, "field", None),
                        "detail": str(exc),
                    }
                )
                continue
            processed.append(record)

        run.records_valid = len(processed)
        return processed

    def run(self) -> RunResult:
        """Execute the full ingestion pipeline, recording an IngestionRun."""
        run = IngestionRun.objects.create(
            source_key=self.key,
            source_kind=self.source_kind,
            status=IngestionRun.Status.RUNNING,
            started_at=timezone.now(),
            context=self.context or {},
        )
        logger.info("ingestion.run start source=%s run_id=%s", self.key, run.pk)

        try:
            raw = self._fetch_with_retry(run)
            run.records_fetched = len(raw)

            processed = self._process(raw, run)

            written, duplicate = self.persist(processed)
            run.records_written = written
            run.records_duplicate += duplicate

            # Partial if some records were dropped during processing.
            if run.records_invalid > 0:
                run.status = IngestionRun.Status.PARTIAL
                run.error_message = f"{run.records_invalid} record(s) failed validation."
            else:
                run.status = IngestionRun.Status.SUCCESS
        except SourceUnavailableError as exc:
            # The provider/endpoint is unavailable — report distinctly, not as a
            # hard failure of the adapter.
            run.status = IngestionRun.Status.SOURCE_UNAVAILABLE
            run.error_message = str(exc)
            run.errors.append({"type": "SourceUnavailable", "detail": str(exc)})
            logger.warning(
                "ingestion.run source_unavailable source=%s run_id=%s: %s",
                self.key, run.pk, exc,
            )
        except IngestionError as exc:
            run.status = IngestionRun.Status.FAILED
            run.error_message = str(exc)
            run.errors.append({"type": type(exc).__name__, "detail": str(exc)})
            logger.exception("ingestion.run failed source=%s run_id=%s", self.key, run.pk)
        except Exception as exc:  # unexpected — record and re-raise after saving
            run.status = IngestionRun.Status.FAILED
            run.error_message = f"Unexpected error: {exc}"
            run.errors.append({"type": type(exc).__name__, "detail": str(exc)})
            run.finished_at = timezone.now()
            run.save()
            logger.exception("ingestion.run crashed source=%s run_id=%s", self.key, run.pk)
            raise
        finally:
            if run.finished_at is None:
                run.finished_at = timezone.now()
                run.save()

        logger.info(
            "ingestion.run done source=%s run_id=%s status=%s fetched=%d valid=%d "
            "invalid=%d written=%d duplicate=%d",
            self.key, run.pk, run.status, run.records_fetched, run.records_valid,
            run.records_invalid, run.records_written, run.records_duplicate,
        )

        return RunResult(
            run_id=run.pk,
            status=run.status,
            fetched=run.records_fetched,
            valid=run.records_valid,
            invalid=run.records_invalid,
            written=run.records_written,
            duplicate=run.records_duplicate,
            attempts=run.attempts,
            errors=run.errors,
            error_message=run.error_message,
        )


class RESTIngestionSource(BaseIngestionSource):
    """Base for REST-API sources.

    Subclasses set `endpoint` (and optionally `params`/`headers`) and implement
    `parse(payload)` to turn the HTTP JSON body into raw records. The HTTP call
    is isolated in `_http_get` so it can be overridden or mocked; the framework
    itself adds no hard HTTP dependency.
    """

    source_kind = IngestionRun.SourceKind.REST

    endpoint: str = ""
    params: dict[str, Any] = {}
    headers: dict[str, str] = {}
    timeout_seconds: float = 15.0

    def _http_get(self) -> Any:
        """Perform the HTTP GET and return the parsed JSON payload.

        Not implemented in the framework (no provider-specific HTTP here).
        Concrete sources override this, or inject an http client, so the
        framework stays dependency-free and testable.
        """
        raise NotImplementedError(
            "Concrete REST sources must implement _http_get() (or override fetch())."
        )

    @abstractmethod
    def parse(self, payload: Any) -> Iterable[Record]:
        """Convert an HTTP payload into raw records."""

    def fetch(self) -> Iterable[Record]:
        if not self.endpoint:
            raise SourceConfigError(f"REST source '{self.key}' has no endpoint.")
        try:
            payload = self._http_get()
        except NotImplementedError:
            raise
        except FetchError:
            # Already a fetch error — preserve its retryable flag.
            raise
        except Exception as exc:  # normalize any other transport error
            raise FetchError(f"HTTP fetch failed for '{self.key}': {exc}") from exc
        return self.parse(payload)


class FileIngestionSource(BaseIngestionSource):
    """Base for file-based sources (CSV/XLSX/JSON).

    Subclasses set `path` and implement `parse_file(path)` to yield raw records.
    Reading is wrapped so file I/O errors surface as FetchError.
    """

    source_kind = IngestionRun.SourceKind.FILE

    path: str = ""

    @abstractmethod
    def parse_file(self, path: str) -> Iterable[Record]:
        """Read the file at `path` and yield raw records."""

    def fetch(self) -> Iterable[Record]:
        if not self.path:
            raise SourceConfigError(f"File source '{self.key}' has no path.")
        try:
            return list(self.parse_file(self.path))
        except FileNotFoundError as exc:
            # Missing file is not transient — do not retry.
            raise FetchError(
                f"File not found for '{self.key}': {self.path}", retryable=False
            ) from exc
        except OSError as exc:
            raise FetchError(f"File read failed for '{self.key}': {exc}") from exc

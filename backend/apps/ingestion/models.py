"""Ingestion run tracking model.

An IngestionRun records each execution of an ingestion source: its status,
timestamps, per-stage record counts, and any error details. This provides the
ingestion status / timestamp / error tracking required by the framework and
supports observability (docs/NON_FUNCTIONAL_REQUIREMENTS.md NFR-MNT).
"""
from __future__ import annotations

from django.db import models

from apps.catalog.models import TimeStampedModel


class IngestionRun(TimeStampedModel):
    """A single execution of an ingestion source."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        RUNNING = "running", "Running"
        SUCCESS = "success", "Success"
        PARTIAL = "partial", "Partial success"  # some records failed validation
        FAILED = "failed", "Failed"
        SOURCE_UNAVAILABLE = "source_unavailable", "Source unavailable"

    class SourceKind(models.TextChoices):
        REST = "rest", "REST API"
        FILE = "file", "File"
        OTHER = "other", "Other"

    # Which source produced this run (registry key, e.g. "aisstream").
    source_key = models.CharField(max_length=100, db_index=True)
    source_kind = models.CharField(
        max_length=8, choices=SourceKind.choices, default=SourceKind.OTHER
    )

    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True
    )

    # Lifecycle timestamps (created_at/updated_at come from the base).
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    # Per-stage counters for observability.
    records_fetched = models.PositiveIntegerField(default=0)
    records_valid = models.PositiveIntegerField(default=0)
    records_invalid = models.PositiveIntegerField(default=0)
    records_written = models.PositiveIntegerField(default=0)
    records_duplicate = models.PositiveIntegerField(default=0)

    # How many fetch attempts were made (retry handling).
    attempts = models.PositiveSmallIntegerField(default=0)

    # Error tracking. `error_message` is a short summary; `errors` holds a
    # structured list of per-record/field problems (never secrets).
    error_message = models.TextField(blank=True)
    errors = models.JSONField(default=list, blank=True)

    # Free-form context (params used, source metadata) — no secrets.
    context = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["source_key", "-created_at"], name="ingrun_source_idx"),
            models.Index(fields=["status", "-created_at"], name="ingrun_status_idx"),
        ]

    def __str__(self) -> str:
        return f"IngestionRun[{self.source_key}] {self.status} ({self.pk})"

    @property
    def duration_seconds(self) -> float | None:
        if self.started_at and self.finished_at:
            return (self.finished_at - self.started_at).total_seconds()
        return None

"""Exception hierarchy for the ingestion framework.

Distinguishing exception types lets the runner decide what is retryable
(transient fetch failures) versus fatal (validation/config errors), and lets
callers handle failures precisely.
"""
from __future__ import annotations


class IngestionError(Exception):
    """Base class for all ingestion errors."""


class SourceConfigError(IngestionError):
    """The source is misconfigured (missing URL, path, credentials, etc.).

    Fatal — not retryable.
    """


class FetchError(IngestionError):
    """A source could not be fetched (network, HTTP, file I/O).

    Typically transient and retryable.
    """

    def __init__(self, message: str, *, retryable: bool = True):
        super().__init__(message)
        self.retryable = retryable


class SourceUnavailableError(FetchError):
    """The upstream source/endpoint is unavailable (unreachable, 404/5xx, or the
    file/download does not exist).

    Reported distinctly as SOURCE_UNAVAILABLE (not a hard failure) so a desk can
    tell "the provider is down" apart from "the adapter is broken". Non-retryable
    by default — the runner records the run as SOURCE_UNAVAILABLE rather than
    retrying indefinitely.
    """

    def __init__(self, message: str, *, retryable: bool = False):
        super().__init__(message, retryable=retryable)


class ValidationError(IngestionError):
    """A record failed validation. Carries the field/reason for error tracking."""

    def __init__(self, message: str, *, field: str | None = None):
        super().__init__(message)
        self.field = field


class NormalizationError(IngestionError):
    """A record could not be normalized into the canonical shape."""


class RegistryError(IngestionError):
    """A source key was not found or was registered twice."""

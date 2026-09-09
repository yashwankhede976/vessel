"""Task wrappers for running ingestion sources.

These are the entry points a scheduler (Celery beat) or a management command
calls to run a source by its registry key. They are written as plain callables
so they work today without a broker; if Celery is installed they are also
registered as shared tasks (so `.delay()` works). This keeps the framework
dependency-free while being Celery-ready (see docs/ARCHITECTURE.md §13).
"""
from __future__ import annotations

import logging
from typing import Any, Callable

from .base import RunResult
from .registry import get_source

logger = logging.getLogger("vessel.ingestion")


# Optional Celery integration: use shared_task if available, else a no-op
# decorator that leaves the function as a normal callable.
try:  # pragma: no cover - depends on optional dependency
    from celery import shared_task  # type: ignore
except Exception:  # Celery not installed — degrade to a plain decorator.
    def shared_task(*dargs: Any, **dkwargs: Any):  # type: ignore
        def _wrap(func: Callable) -> Callable:
            return func

        # Support both @shared_task and @shared_task(...) usage.
        if len(dargs) == 1 and callable(dargs[0]) and not dkwargs:
            return dargs[0]
        return _wrap


def run_source(source_key: str, **context: Any) -> RunResult:
    """Instantiate and run the registered source for `source_key`.

    Returns the RunResult. Raises RegistryError if the key is unknown, and
    propagates unexpected errors after they have been recorded on the run.
    """
    source_cls = get_source(source_key)
    source = source_cls(**context)
    logger.info("ingestion.task run_source key=%s", source_key)
    return source.run()


@shared_task(name="ingestion.run_source")
def run_source_task(source_key: str, **context: Any) -> dict:
    """Celery entry point: run a source and return a JSON-serializable summary."""
    result = run_source(source_key, **context)
    return {
        "run_id": result.run_id,
        "status": result.status,
        "fetched": result.fetched,
        "valid": result.valid,
        "invalid": result.invalid,
        "written": result.written,
        "duplicate": result.duplicate,
        "attempts": result.attempts,
    }

"""Source registry.

Concrete ingestion sources register themselves by their unique `key`, so tasks
and management commands can run a source by name without importing it directly.

Usage:
    from apps.ingestion.registry import register, get_source

    @register
    class MyThing(RESTIngestionSource):
        key = "my_thing"
        ...

    source_cls = get_source("my_thing")
"""
from __future__ import annotations

from typing import Type

from .base import BaseIngestionSource
from .exceptions import RegistryError

_REGISTRY: dict[str, Type[BaseIngestionSource]] = {}


def register(source_cls: Type[BaseIngestionSource]) -> Type[BaseIngestionSource]:
    """Class decorator / function to register a source by its `key`."""
    key = getattr(source_cls, "key", "")
    if not key:
        raise RegistryError(
            f"{source_cls.__name__} must define a non-empty 'key' to register."
        )
    if key in _REGISTRY and _REGISTRY[key] is not source_cls:
        raise RegistryError(f"Ingestion source key '{key}' is already registered.")
    _REGISTRY[key] = source_cls
    return source_cls


def get_source(key: str) -> Type[BaseIngestionSource]:
    """Return the registered source class for `key`, or raise RegistryError."""
    try:
        return _REGISTRY[key]
    except KeyError as exc:
        raise RegistryError(f"No ingestion source registered for key '{key}'.") from exc


def list_sources() -> list[str]:
    """Return all registered source keys (sorted)."""
    return sorted(_REGISTRY)


def unregister(key: str) -> None:
    """Remove a source from the registry (mainly for tests)."""
    _REGISTRY.pop(key, None)


def clear() -> None:
    """Clear the registry (mainly for tests)."""
    _REGISTRY.clear()

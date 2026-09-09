"""Deduplication support.

Two layers:
1. In-batch dedup — drop records that repeat within a single fetch, keyed by a
   caller-provided natural key.
2. Persistence dedup — the concrete source's `persist()` should upsert on the
   same natural key (e.g. Django update_or_create) so re-runs don't duplicate.

This module provides the in-batch layer and the key helper; persistence dedup
is the source's responsibility since it owns the models.
"""
from __future__ import annotations

from typing import Any, Callable, Iterable, Iterator

Record = dict[str, Any]
KeyFn = Callable[[Record], tuple]


def make_key(*fields: str) -> KeyFn:
    """Build a natural-key function from record fields."""

    def _key(record: Record) -> tuple:
        return tuple(record.get(f) for f in fields)

    return _key


def dedupe(records: Iterable[Record], key_fn: KeyFn) -> tuple[list[Record], int]:
    """Return (unique_records, duplicate_count), keeping first occurrence."""
    seen: set[tuple] = set()
    unique: list[Record] = []
    duplicates = 0
    for record in records:
        key = key_fn(record)
        if key in seen:
            duplicates += 1
            continue
        seen.add(key)
        unique.append(record)
    return unique, duplicates


def iter_unique(records: Iterable[Record], key_fn: KeyFn) -> Iterator[Record]:
    """Lazily yield unique records (first occurrence wins)."""
    seen: set[tuple] = set()
    for record in records:
        key = key_fn(record)
        if key in seen:
            continue
        seen.add(key)
        yield record

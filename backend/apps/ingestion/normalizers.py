"""Normalization layer.

Normalizers transform a raw source record into the canonical shape the rest of
the platform expects: consistent field names, units, types, and provenance.
Like validators, they are composable via `chain`. Generic building blocks only
— provider-specific mapping lives in concrete sources.
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Callable

from django.utils.dateparse import parse_date, parse_datetime

from .exceptions import NormalizationError

Record = dict[str, Any]
Normalizer = Callable[[Record], Record]


def chain(*normalizers: Normalizer) -> Normalizer:
    """Compose normalizers left-to-right."""

    def _run(record: Record) -> Record:
        for normalizer in normalizers:
            record = normalizer(record)
        return record

    return _run


def rename_fields(mapping: dict[str, str]) -> Normalizer:
    """Rename source keys to canonical keys ({source_key: canonical_key})."""

    def _normalize(record: Record) -> Record:
        out = dict(record)
        for src, dst in mapping.items():
            if src in out:
                out[dst] = out.pop(src)
        return out

    return _normalize


def to_decimal(*fields: str) -> Normalizer:
    """Coerce the given fields to Decimal (None left as-is)."""

    def _normalize(record: Record) -> Record:
        out = dict(record)
        for field in fields:
            value = out.get(field)
            if value is None or value == "":
                out[field] = None
                continue
            try:
                out[field] = Decimal(str(value))
            except (InvalidOperation, ValueError) as exc:
                raise NormalizationError(
                    f"Field '{field}' cannot be converted to Decimal: {value!r}"
                ) from exc
        return out

    return _normalize


def to_date(*fields: str) -> Normalizer:
    """Parse the given fields into datetime.date (ISO strings or date objects)."""

    def _normalize(record: Record) -> Record:
        out = dict(record)
        for field in fields:
            value = out.get(field)
            if value in (None, "") or isinstance(value, date):
                continue
            parsed = parse_date(str(value))
            if parsed is None:
                raise NormalizationError(f"Field '{field}' is not a valid date: {value!r}")
            out[field] = parsed
        return out

    return _normalize


def to_datetime(*fields: str) -> Normalizer:
    """Parse the given fields into timezone-aware/naive datetime."""

    def _normalize(record: Record) -> Record:
        out = dict(record)
        for field in fields:
            value = out.get(field)
            if value in (None, "") or isinstance(value, datetime):
                continue
            parsed = parse_datetime(str(value))
            if parsed is None:
                raise NormalizationError(
                    f"Field '{field}' is not a valid datetime: {value!r}"
                )
            out[field] = parsed
        return out

    return _normalize


def strip_strings() -> Normalizer:
    """Trim whitespace on all string values."""

    def _normalize(record: Record) -> Record:
        return {
            k: (v.strip() if isinstance(v, str) else v) for k, v in record.items()
        }

    return _normalize


def set_defaults(**defaults: Any) -> Normalizer:
    """Fill missing/None fields with default values."""

    def _normalize(record: Record) -> Record:
        out = dict(record)
        for key, value in defaults.items():
            if out.get(key) is None:
                out[key] = value
        return out

    return _normalize

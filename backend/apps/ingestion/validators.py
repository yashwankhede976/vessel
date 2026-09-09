"""Validation layer.

A Validator inspects a single normalized-or-raw record and either returns it
(valid) or raises ValidationError. Validators are composable: `chain` runs
several in order. The framework is generic — provider-specific rules are added
by concrete sources, not here.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any, Callable, Iterable

from .exceptions import ValidationError

Record = dict[str, Any]
Validator = Callable[[Record], Record]


def chain(*validators: Validator) -> Validator:
    """Compose validators left-to-right into a single validator."""

    def _run(record: Record) -> Record:
        for validator in validators:
            record = validator(record)
        return record

    return _run


def require_fields(*fields: str) -> Validator:
    """Every listed field must be present and not None/empty-string."""

    def _validate(record: Record) -> Record:
        for field in fields:
            if field not in record or record[field] in (None, ""):
                raise ValidationError(f"Missing required field '{field}'.", field=field)
        return record

    return _validate


def numeric_range(
    field: str,
    *,
    minimum: Decimal | float | None = None,
    maximum: Decimal | float | None = None,
    allow_none: bool = True,
) -> Validator:
    """A numeric field must parse and fall within [minimum, maximum]."""

    def _validate(record: Record) -> Record:
        value = record.get(field)
        if value is None:
            if allow_none:
                return record
            raise ValidationError(f"Field '{field}' must not be null.", field=field)
        try:
            num = Decimal(str(value))
        except (InvalidOperation, ValueError):
            raise ValidationError(f"Field '{field}' is not numeric.", field=field)
        if minimum is not None and num < Decimal(str(minimum)):
            raise ValidationError(
                f"Field '{field}' {num} is below minimum {minimum}.", field=field
            )
        if maximum is not None and num > Decimal(str(maximum)):
            raise ValidationError(
                f"Field '{field}' {num} exceeds maximum {maximum}.", field=field
            )
        return record

    return _validate


def one_of(field: str, allowed: Iterable[Any], *, allow_none: bool = True) -> Validator:
    """A field's value must be one of an allowed set."""
    allowed_set = set(allowed)

    def _validate(record: Record) -> Record:
        value = record.get(field)
        if value is None and allow_none:
            return record
        if value not in allowed_set:
            raise ValidationError(
                f"Field '{field}' value '{value}' is not allowed.", field=field
            )
        return record

    return _validate

"""Validation layer.

A Validator inspects a single normalized-or-raw record and either returns it
(valid) or raises ValidationError. Validators are composable: `chain` runs
several in order. The framework is generic — provider-specific rules are added
by concrete sources, not here.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any, Callable, Iterable, Optional

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


# ---------------------------------------------------------------------------
# Data-quality validators (item: DATA QUALITY).
#
# These reject records that are physically impossible or internally
# inconsistent, so bad data never reaches the analytical tables. A rejected
# record raises ValidationError; the base pipeline records it on the
# IngestionRun (index/type/field/detail) so the ingestion error is preserved
# for diagnosis while the record is kept out of the sink.
# ---------------------------------------------------------------------------
from datetime import date, datetime, timezone as _dt_timezone  # noqa: E402


def valid_coordinates(
    lat_field: str = "latitude",
    lon_field: str = "longitude",
    *,
    allow_none: bool = True,
) -> Validator:
    """Latitude in [-90, 90] and longitude in [-180, 180]. Rejects impossible
    coordinates (e.g. lat 999)."""

    def _validate(record: Record) -> Record:
        lat = record.get(lat_field)
        lon = record.get(lon_field)
        for name, value, lo, hi in (
            (lat_field, lat, Decimal("-90"), Decimal("90")),
            (lon_field, lon, Decimal("-180"), Decimal("180")),
        ):
            if value is None:
                if allow_none:
                    continue
                raise ValidationError(f"Field '{name}' must not be null.", field=name)
            try:
                num = Decimal(str(value))
            except (InvalidOperation, ValueError):
                raise ValidationError(f"Field '{name}' is not numeric.", field=name)
            if num < lo or num > hi:
                raise ValidationError(
                    f"Impossible coordinate '{name}'={num} (expected [{lo}, {hi}]).",
                    field=name,
                )
        return record

    return _validate


def non_negative(*fields: str, allow_none: bool = True) -> Validator:
    """Each listed numeric field must be >= 0. Rejects negative cargo
    quantities, distances, prices, etc."""

    def _validate(record: Record) -> Record:
        for field in fields:
            value = record.get(field)
            if value is None:
                if allow_none:
                    continue
                raise ValidationError(f"Field '{field}' must not be null.", field=field)
            try:
                num = Decimal(str(value))
            except (InvalidOperation, ValueError):
                raise ValidationError(f"Field '{field}' is not numeric.", field=field)
            if num < 0:
                raise ValidationError(
                    f"Field '{field}' {num} must not be negative.", field=field
                )
        return record

    return _validate


def _coerce_datetime(value) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day, tzinfo=_dt_timezone.utc)
    try:
        text = str(value).replace("Z", "+00:00")
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def no_future_timestamp(
    *fields: str,
    allow_none: bool = True,
    skew_seconds: int = 3600,
) -> Validator:
    """Timestamp fields must not be implausibly in the future.

    A small `skew_seconds` tolerance (default 1h) absorbs clock skew and
    legitimately-forecast rows near "now"; anything beyond that is rejected as an
    invalid/future timestamp. Forecast rows with far-future target dates should
    NOT use this validator on their target-date field.
    """

    def _validate(record: Record) -> Record:
        now = datetime.now(_dt_timezone.utc)
        for field in fields:
            value = record.get(field)
            if value is None:
                if allow_none:
                    continue
                raise ValidationError(f"Field '{field}' must not be null.", field=field)
            dt = _coerce_datetime(value)
            if dt is None:
                raise ValidationError(
                    f"Field '{field}' is not a valid date/datetime.", field=field
                )
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=_dt_timezone.utc)
            if (dt - now).total_seconds() > skew_seconds:
                raise ValidationError(
                    f"Field '{field}' {dt.isoformat()} is in the future.", field=field
                )
        return record

    return _validate


def valid_date_order(earlier_field: str, later_field: str) -> Validator:
    """`earlier_field` must not be after `later_field` (both present)."""

    def _validate(record: Record) -> Record:
        a = _coerce_datetime(record.get(earlier_field))
        b = _coerce_datetime(record.get(later_field))
        if a is not None and b is not None and a > b:
            raise ValidationError(
                f"'{earlier_field}' must not be after '{later_field}'.",
                field=earlier_field,
            )
        return record

    return _validate


def valid_vessel_dimensions(
    *,
    loa_field: str = "loa",
    beam_field: str = "beam",
    draft_field: str = "draft",
    dwt_field: str = "dwt",
    allow_none: bool = True,
) -> Validator:
    """Vessel dimensions must be positive and within plausible bulk-carrier
    bounds. Rejects zero/negative or absurd dimensions."""

    # Generous physical upper bounds (largest bulk carriers): LOA ~365m,
    # beam ~65m, draft ~24m, DWT ~450,000 t. Documented, deliberately loose.
    bounds = {
        loa_field: (Decimal("1"), Decimal("400")),
        beam_field: (Decimal("1"), Decimal("70")),
        draft_field: (Decimal("0.5"), Decimal("30")),
        dwt_field: (Decimal("1"), Decimal("500000")),
    }

    def _validate(record: Record) -> Record:
        for field, (lo, hi) in bounds.items():
            value = record.get(field)
            if value is None:
                if allow_none:
                    continue
                raise ValidationError(f"Field '{field}' must not be null.", field=field)
            try:
                num = Decimal(str(value))
            except (InvalidOperation, ValueError):
                raise ValidationError(f"Field '{field}' is not numeric.", field=field)
            if num < lo or num > hi:
                raise ValidationError(
                    f"Invalid vessel dimension '{field}'={num} "
                    f"(expected [{lo}, {hi}]).",
                    field=field,
                )
        return record

    return _validate


def valid_freight_rate(
    field: str = "rate_per_tonne",
    *,
    minimum: Decimal | float = 0,
    maximum: Decimal | float = 1000,
    allow_none: bool = True,
) -> Validator:
    """A freight rate (currency/tonne) must be non-negative and within a
    plausible ceiling. Rejects negative or absurd rates. The default ceiling
    (1000/t) is a generous documented sanity bound for dry-bulk freight."""

    return numeric_range(field, minimum=minimum, maximum=maximum, allow_none=allow_none)

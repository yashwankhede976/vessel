"""AISStream message parsing and mapping to canonical records.

AISStream delivers JSON messages over a WebSocket. The two message types we
consume:

- "PositionReport"  -> dynamic data (position, speed, course, heading, status)
- "ShipStaticData"  -> static data (IMO, ship name, dimensions)

Both carry a shared "MetaData" block with MMSI, ShipName, latitude/longitude
and a UTC timestamp. This module turns a raw AISStream message into a flat,
normalized record; the adapter then maps it to Vessel + AISPosition.

Reference: aisstream.io message schema (consulted 2026-09-08). Field names
below follow AISStream's documented casing.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any, Optional

from django.utils.dateparse import parse_datetime

from apps.ingestion.exceptions import NormalizationError, ValidationError

Record = dict[str, Any]

POSITION_REPORT = "PositionReport"
SHIP_STATIC_DATA = "ShipStaticData"

# AIS navigational status code -> human label (subset; unknown falls through).
NAV_STATUS = {
    0: "under way using engine",
    1: "at anchor",
    2: "not under command",
    3: "restricted manoeuvrability",
    4: "constrained by draught",
    5: "moored",
    6: "aground",
    7: "engaged in fishing",
    8: "under way sailing",
    15: "undefined",
}


def _dec(value: Any) -> Optional[Decimal]:
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def _clean_str(value: Any) -> str:
    """AIS strings are often padded with '@' and spaces."""
    if value is None:
        return ""
    return str(value).replace("@", "").strip()


def parse_message(message: dict) -> Record:
    """Turn a raw AISStream message dict into a flat normalized record.

    Raises NormalizationError for structurally unusable messages (the adapter
    treats these as malformed and skips them).
    """
    if not isinstance(message, dict):
        raise NormalizationError("AIS message is not an object.")

    msg_type = message.get("MessageType")
    meta = message.get("MetaData") or {}
    body = (message.get("Message") or {}).get(msg_type) or {}

    if msg_type not in (POSITION_REPORT, SHIP_STATIC_DATA):
        raise NormalizationError(f"Unsupported AIS message type: {msg_type!r}")

    # MMSI is the one field we always require; it keys the vessel.
    mmsi = meta.get("MMSI") or body.get("UserID")
    if mmsi is None:
        raise NormalizationError("AIS message has no MMSI.")

    record: Record = {
        "message_type": msg_type,
        "mmsi": str(mmsi),
        "vessel_name": _clean_str(meta.get("ShipName") or body.get("Name")),
        "timestamp": _parse_time(meta.get("time_utc") or meta.get("TimeUtc")),
    }

    if msg_type == POSITION_REPORT:
        record.update(
            {
                "latitude": _dec(meta.get("latitude") or body.get("Latitude")),
                "longitude": _dec(meta.get("longitude") or body.get("Longitude")),
                "sog": _dec(body.get("Sog")),
                "cog": _dec(body.get("Cog")),
                "heading": _heading(body.get("TrueHeading")),
                "nav_status": NAV_STATUS.get(
                    body.get("NavigationalStatus"),
                    str(body.get("NavigationalStatus") or ""),
                ),
            }
        )
    else:  # ShipStaticData
        imo = body.get("ImoNumber")
        record["imo"] = str(imo) if imo else ""

    return record


def _parse_time(value: Any):
    if not value:
        return None
    # AISStream time_utc looks like "2026-09-08 12:34:56.789 +0000 UTC"; try to
    # coerce to something parse_datetime understands.
    text = str(value).replace(" UTC", "").strip()
    parsed = parse_datetime(text)
    return parsed


def _heading(value: Any) -> Optional[Decimal]:
    # AIS uses 511 to mean "heading not available".
    if value in (None, "", 511):
        return None
    return _dec(value)


def validate_position(record: Record) -> Record:
    """Validate a PositionReport-derived record before it becomes an AISPosition."""
    lat = record.get("latitude")
    lon = record.get("longitude")
    if lat is None or lon is None:
        raise ValidationError("Position report missing latitude/longitude.")
    if not (Decimal("-90") <= lat <= Decimal("90")):
        raise ValidationError(f"Latitude out of range: {lat}", field="latitude")
    if not (Decimal("-180") <= lon <= Decimal("180")):
        raise ValidationError(f"Longitude out of range: {lon}", field="longitude")
    if record.get("timestamp") is None:
        raise ValidationError("Position report missing timestamp.")
    return record

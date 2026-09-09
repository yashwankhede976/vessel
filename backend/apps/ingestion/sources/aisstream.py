"""AISStream ingestion adapter.

Consumes the AISStream server-side WebSocket (wss://stream.aisstream.io/v0/stream),
processing PositionReport and ShipStaticData messages and mapping them onto the
Vessel and AISPosition models.

Credentials
-----------
The API key is read ONLY from settings.EXTERNAL_APIS["AISSTREAM_API_KEY"]
(sourced from the AISSTREAM_API_KEY environment variable). It is placed in the
WebSocket subscription payload (AISStream carries the key in the subscribe
message, not an HTTP header). It is never exposed to the frontend.

Design
------
AIS is a stream, not a batch, so this adapter does not use BaseIngestionSource's
one-shot run(); instead it processes messages one at a time via `process_message`
and manages its own reconnecting consume loop. It still records an IngestionRun
per session for status/timestamps/error tracking, and reuses the framework's
mapping/validation helpers.

Testability
-----------
The consume loop reads from an injectable async message iterator, so tests feed
mocked messages without any real socket. The `websockets` dependency is imported
lazily inside `connect()` and is only needed to run against the live service.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, AsyncIterator, Optional

from django.conf import settings
from django.utils import timezone

from apps.catalog.models import Vessel
from apps.ingestion.exceptions import NormalizationError, SourceConfigError, ValidationError
from apps.ingestion.models import IngestionRun
from apps.operations.models import AISPosition

from . import ais_mapping

logger = logging.getLogger("vessel.ingestion.ais")

AIS_WS_URL = "wss://stream.aisstream.io/v0/stream"

# Default bounding box: Bay of Bengal / East Coast India approaches.
# AISStream expects [[[lat1, lon1], [lat2, lon2]]] (SW then NE corners).
DEFAULT_BBOX = [[[5.0, 78.0], [23.0, 95.0]]]


@dataclass
class ConsumeStats:
    """Counters for one consume session (mirrored onto the IngestionRun)."""

    fetched: int = 0
    positions_written: int = 0
    static_applied: int = 0
    malformed: int = 0
    invalid: int = 0
    duplicate: int = 0
    reconnects: int = 0
    errors: list[dict] = field(default_factory=list)


class AISStreamSource:
    """AISStream WebSocket consumer/adapter."""

    key = "aisstream"
    source_kind = IngestionRun.SourceKind.OTHER  # streaming, not batch REST/file

    # Reconnect policy.
    max_reconnects: int = 5
    reconnect_backoff_seconds: float = 1.0

    def __init__(
        self,
        *,
        bounding_boxes: Optional[list] = None,
        api_key: Optional[str] = None,
    ):
        # Credentials come from settings (env), never a hard-coded/default value.
        self.api_key = api_key or settings.EXTERNAL_APIS.get("AISSTREAM_API_KEY", "")
        self.bounding_boxes = bounding_boxes or DEFAULT_BBOX

    # ------------------------------------------------------------------
    # Subscription
    # ------------------------------------------------------------------
    def subscription_payload(self) -> dict:
        """The JSON subscribe message AISStream expects (carries the API key)."""
        if not self.api_key:
            raise SourceConfigError(
                "AISSTREAM_API_KEY is not set. Provide it via the environment; "
                "the adapter will not connect without a key."
            )
        return {
            "APIKey": self.api_key,
            "BoundingBoxes": self.bounding_boxes,
            "FilterMessageTypes": [
                ais_mapping.POSITION_REPORT,
                ais_mapping.SHIP_STATIC_DATA,
            ],
        }

    # ------------------------------------------------------------------
    # Per-message processing (pure enough to unit-test directly)
    # ------------------------------------------------------------------
    def process_message(self, raw: Any, stats: ConsumeStats) -> None:
        """Process a single raw AIS message (str/bytes/dict), updating stats.

        Handles malformed messages (skip + count), duplicates (upsert), missing
        IMO (vessel keyed by MMSI), and missing vessel (position retained with
        raw MMSI/name). Never raises for bad data — records and continues.
        """
        stats.fetched += 1

        # Decode JSON if we were handed a raw frame.
        try:
            message = raw if isinstance(raw, dict) else json.loads(raw)
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            stats.malformed += 1
            stats.errors.append({"type": "malformed", "detail": str(exc)})
            logger.warning("ais.malformed could not decode message: %s", exc)
            return

        # Parse into a flat record.
        try:
            record = ais_mapping.parse_message(message)
        except NormalizationError as exc:
            stats.malformed += 1
            stats.errors.append({"type": "malformed", "detail": str(exc)})
            logger.debug("ais.malformed %s", exc)
            return

        if record["message_type"] == ais_mapping.SHIP_STATIC_DATA:
            self._apply_static(record, stats)
        else:
            self._apply_position(record, stats)

    def _apply_static(self, record: dict, stats: ConsumeStats) -> None:
        """ShipStaticData: enrich a known vessel with IMO/name if we can match it.

        We do NOT create a full Vessel from AIS alone (Vessel requires IMO and
        physical specs AIS does not provide). We only enrich an existing vessel
        matched by MMSI, or link an existing vessel matched by IMO to this MMSI.
        """
        mmsi = record["mmsi"]
        imo = record.get("imo") or ""
        name = record.get("vessel_name") or ""

        vessel = Vessel.objects.filter(mmsi=mmsi).first()
        if vessel is None and imo:
            vessel = Vessel.objects.filter(imo=imo).first()
            if vessel and not vessel.mmsi:
                vessel.mmsi = mmsi

        if vessel is None:
            # No known vessel to enrich; static data is retained implicitly via
            # future position rows (which carry MMSI/name). Not an error.
            logger.debug("ais.static no matching vessel for MMSI %s", mmsi)
            return

        changed = False
        if name and vessel.name != name:
            vessel.name = name
            changed = True
        if imo and vessel.imo != imo:
            # Only set IMO if currently empty-ish; do not overwrite a real IMO.
            if not vessel.imo or vessel.imo == mmsi:
                vessel.imo = imo
                changed = True
        if changed:
            vessel.save()
            stats.static_applied += 1
            logger.debug("ais.static enriched vessel id=%s mmsi=%s", vessel.pk, mmsi)

    def _apply_position(self, record: dict, stats: ConsumeStats) -> None:
        """PositionReport: validate and upsert an AISPosition (dedup on MMSI+ts)."""
        try:
            ais_mapping.validate_position(record)
        except ValidationError as exc:
            stats.invalid += 1
            stats.errors.append(
                {"type": "invalid", "field": exc.field, "detail": str(exc)}
            )
            logger.debug("ais.invalid position mmsi=%s: %s", record.get("mmsi"), exc)
            return

        mmsi = record["mmsi"]
        vessel = Vessel.objects.filter(mmsi=mmsi).first()  # may be None (missing vessel)

        _, created = AISPosition.objects.update_or_create(
            mmsi=mmsi,
            timestamp=record["timestamp"],
            defaults={
                "vessel": vessel,
                "vessel_name": record.get("vessel_name") or "",
                "latitude": record["latitude"],
                "longitude": record["longitude"],
                "sog": record.get("sog"),
                "cog": record.get("cog"),
                "heading": record.get("heading"),
                "nav_status": record.get("nav_status") or "",
                "source": self.key,
            },
        )
        if created:
            stats.positions_written += 1
        else:
            # Same MMSI+timestamp already stored -> duplicate (idempotent upsert).
            stats.duplicate += 1

    # ------------------------------------------------------------------
    # Consume loop (synchronous) with reconnect handling
    # ------------------------------------------------------------------
    def consume(
        self,
        message_iterator_factory,
        stats: Optional[ConsumeStats] = None,
        *,
        max_messages: Optional[int] = None,
    ) -> ConsumeStats:
        """Consume messages from an injectable *sync* iterable factory.

        `message_iterator_factory()` returns an iterable of raw messages (one
        "connection"). If it raises or ends, we reconnect up to
        `max_reconnects` times with exponential backoff. Message processing is
        synchronous (ORM writes), which keeps Django's ORM out of any event
        loop. The live WebSocket transport is bridged to a sync iterable by
        `connect_sync`, so this loop is identical for tests and production.
        """
        import time

        stats = stats or ConsumeStats()
        attempt = 0
        processed = 0

        while True:
            try:
                iterator = message_iterator_factory()
                for raw in iterator:
                    self.process_message(raw, stats)
                    processed += 1
                    if max_messages is not None and processed >= max_messages:
                        return stats
                # Iterator ended cleanly (e.g. server closed): reconnect.
                raise ConnectionError("AIS stream ended")
            except Exception as exc:  # noqa: BLE001 - reconnect on any stream error
                attempt += 1
                if attempt > self.max_reconnects:
                    logger.error("ais.consume giving up after %d reconnects: %s", attempt - 1, exc)
                    raise
                stats.reconnects += 1
                backoff = self.reconnect_backoff_seconds * (2 ** (attempt - 1))
                logger.warning(
                    "ais.consume reconnect %d/%d after error: %s (backoff %.1fs)",
                    attempt, self.max_reconnects, exc, backoff,
                )
                time.sleep(backoff)

    async def _connect_async(self) -> AsyncIterator[Any]:
        """Live async connection: yield raw text frames from the WebSocket.

        Imports `websockets` lazily so the dependency is only required to run
        against the live service (not for tests or the rest of the app).
        """
        try:
            import websockets  # type: ignore
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise SourceConfigError(
                "The 'websockets' package is required to run the live AIS "
                "consumer. Install it (see backend/requirements.txt)."
            ) from exc

        payload = self.subscription_payload()  # raises if no API key
        async with websockets.connect(AIS_WS_URL) as ws:  # pragma: no cover - network
            await ws.send(json.dumps(payload))
            logger.info("ais.connect subscribed bbox=%s", self.bounding_boxes)
            async for message in ws:
                yield message

    def connect_sync(self):  # pragma: no cover - requires live network
        """Bridge the async WebSocket to a synchronous generator of frames.

        Lets the synchronous `consume` loop drive the live transport without an
        event loop wrapping the ORM writes. One call == one connection; when the
        socket closes the generator ends and `consume` reconnects.
        """
        import asyncio

        loop = asyncio.new_event_loop()
        try:
            agen = self._connect_async().__aiter__()
            while True:
                try:
                    yield loop.run_until_complete(agen.__anext__())
                except StopAsyncIteration:
                    return
        finally:
            loop.close()

    # ------------------------------------------------------------------
    # Session orchestration with IngestionRun tracking
    # ------------------------------------------------------------------
    def run_session(
        self,
        message_iterator_factory=None,
        *,
        max_messages: Optional[int] = None,
    ) -> IngestionRun:
        """Run a consume session synchronously, recording an IngestionRun.

        Used by tests and by a management command / worker. `run_session`
        drives the (synchronous) consume loop to completion (bounded by
        max_messages for tests; unbounded for live use until stopped).
        """
        run = IngestionRun.objects.create(
            source_key=self.key,
            source_kind=self.source_kind,
            status=IngestionRun.Status.RUNNING,
            started_at=timezone.now(),
            context={"bounding_boxes": self.bounding_boxes},
        )
        stats = ConsumeStats()
        factory = message_iterator_factory or self.connect_sync

        try:
            self.consume(factory, stats, max_messages=max_messages)
            status = IngestionRun.Status.SUCCESS
        except SourceConfigError as exc:
            status = IngestionRun.Status.FAILED
            stats.errors.append({"type": "config", "detail": str(exc)})
            logger.error("ais.session config error: %s", exc)
        except Exception as exc:  # noqa: BLE001
            status = IngestionRun.Status.FAILED
            stats.errors.append({"type": type(exc).__name__, "detail": str(exc)})
            logger.exception("ais.session failed")
        finally:
            # Partial if we saw malformed/invalid messages but still wrote some.
            if status == IngestionRun.Status.SUCCESS and (
                stats.malformed or stats.invalid
            ):
                status = IngestionRun.Status.PARTIAL
            run.status = status
            run.finished_at = timezone.now()
            run.records_fetched = stats.fetched
            run.records_valid = stats.positions_written + stats.static_applied
            run.records_invalid = stats.invalid + stats.malformed
            run.records_written = stats.positions_written
            run.records_duplicate = stats.duplicate
            run.errors = stats.errors[:200]  # cap stored errors
            if stats.errors and not run.error_message:
                run.error_message = f"{len(stats.errors)} message issue(s) during session."
            run.context = {
                **run.context,
                "reconnects": stats.reconnects,
                "static_applied": stats.static_applied,
            }
            run.save()

        logger.info(
            "ais.session done run_id=%s status=%s fetched=%d positions=%d "
            "static=%d dup=%d malformed=%d invalid=%d reconnects=%d",
            run.pk, run.status, stats.fetched, stats.positions_written,
            stats.static_applied, stats.duplicate, stats.malformed, stats.invalid,
            stats.reconnects,
        )
        return run

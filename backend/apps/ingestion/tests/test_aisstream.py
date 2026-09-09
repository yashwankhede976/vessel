"""Tests for the AISStream adapter using mocked WebSocket messages.

No real socket or `websockets` dependency: messages are fed through an
injectable async iterator factory.
"""
from decimal import Decimal

from django.test import TestCase, override_settings

from apps.catalog.models import Vessel
from apps.ingestion.exceptions import SourceConfigError
from apps.ingestion.models import IngestionRun
from apps.ingestion.sources.aisstream import AISStreamSource, ConsumeStats
from apps.operations.models import AISPosition


# ---- mocked AISStream message builders ----
def position_msg(mmsi, *, lat=15.0, lon=85.0, name="TEST VESSEL", ts="2026-09-08 10:00:00.000 +0000 UTC", sog=12.3):
    return {
        "MessageType": "PositionReport",
        "MetaData": {"MMSI": mmsi, "ShipName": name, "latitude": lat, "longitude": lon, "time_utc": ts},
        "Message": {
            "PositionReport": {
                "UserID": mmsi,
                "Latitude": lat,
                "Longitude": lon,
                "Sog": sog,
                "Cog": 180.0,
                "TrueHeading": 179,
                "NavigationalStatus": 0,
            }
        },
    }


def static_msg(mmsi, *, imo="9111222", name="ENRICHED NAME", ts="2026-09-08 10:00:05.000 +0000 UTC"):
    return {
        "MessageType": "ShipStaticData",
        "MetaData": {"MMSI": mmsi, "ShipName": name, "time_utc": ts},
        "Message": {"ShipStaticData": {"UserID": mmsi, "ImoNumber": imo, "Name": name}},
    }


def sync_factory(messages):
    """Return a factory producing a sync iterator over `messages` once."""

    def factory():
        return iter(list(messages))

    return factory


@override_settings(EXTERNAL_APIS={"AISSTREAM_API_KEY": "test-key"})
class AISProcessingTests(TestCase):
    def test_position_creates_aisposition_without_vessel(self):
        src = AISStreamSource(api_key="test-key")
        stats = ConsumeStats()
        src.process_message(position_msg("111111111"), stats)

        self.assertEqual(stats.positions_written, 1)
        pos = AISPosition.objects.get(mmsi="111111111")
        self.assertIsNone(pos.vessel)  # missing vessel handled: stored anyway
        self.assertEqual(pos.vessel_name, "TEST VESSEL")
        self.assertEqual(pos.latitude, Decimal("15.000000"))
        self.assertEqual(pos.sog, Decimal("12.30"))
        self.assertEqual(pos.nav_status, "under way using engine")
        self.assertEqual(pos.source, "aisstream")

    def test_position_links_to_existing_vessel_by_mmsi(self):
        vessel = Vessel.objects.create(
            imo="9000001", mmsi="222222222", name="Known", dwt=Decimal("80000"),
            loa=Decimal("225"), beam=Decimal("32"), draft=Decimal("14"),
        )
        src = AISStreamSource(api_key="test-key")
        src.process_message(position_msg("222222222"), ConsumeStats())
        pos = AISPosition.objects.get(mmsi="222222222")
        self.assertEqual(pos.vessel_id, vessel.id)

    def test_duplicate_message_is_upserted_not_duplicated(self):
        src = AISStreamSource(api_key="test-key")
        stats = ConsumeStats()
        msg = position_msg("333333333")
        src.process_message(msg, stats)
        src.process_message(msg, stats)  # same MMSI + timestamp
        self.assertEqual(AISPosition.objects.filter(mmsi="333333333").count(), 1)
        self.assertEqual(stats.positions_written, 1)
        self.assertEqual(stats.duplicate, 1)

    def test_malformed_message_is_skipped(self):
        src = AISStreamSource(api_key="test-key")
        stats = ConsumeStats()
        src.process_message("{not json", stats)  # bad JSON string
        src.process_message({"MessageType": "Unknown"}, stats)  # unsupported type
        src.process_message({"MessageType": "PositionReport", "MetaData": {}, "Message": {}}, stats)  # no MMSI
        self.assertEqual(stats.malformed, 3)
        self.assertEqual(AISPosition.objects.count(), 0)

    def test_invalid_position_out_of_range(self):
        src = AISStreamSource(api_key="test-key")
        stats = ConsumeStats()
        src.process_message(position_msg("444444444", lat=999.0), stats)
        self.assertEqual(stats.invalid, 1)
        self.assertEqual(AISPosition.objects.count(), 0)

    def test_static_data_enriches_existing_vessel_missing_imo(self):
        # Vessel exists (created via non-AIS path) with MMSI but placeholder name.
        vessel = Vessel.objects.create(
            imo="9000002", mmsi="555555555", name="Old Name", dwt=Decimal("80000"),
            loa=Decimal("225"), beam=Decimal("32"), draft=Decimal("14"),
        )
        src = AISStreamSource(api_key="test-key")
        stats = ConsumeStats()
        src.process_message(static_msg("555555555", imo="9000002", name="New Name"), stats)
        vessel.refresh_from_db()
        self.assertEqual(vessel.name, "New Name")
        self.assertEqual(stats.static_applied, 1)

    def test_static_data_no_matching_vessel_is_noop(self):
        src = AISStreamSource(api_key="test-key")
        stats = ConsumeStats()
        src.process_message(static_msg("666666666"), stats)
        self.assertEqual(stats.static_applied, 0)  # nothing to enrich, not an error
        self.assertEqual(stats.malformed, 0)


@override_settings(EXTERNAL_APIS={"AISSTREAM_API_KEY": "test-key"})
class AISSessionTests(TestCase):
    def test_run_session_processes_stream_and_records_run(self):
        messages = [
            position_msg("777777777", ts="2026-09-08 10:00:00.000 +0000 UTC"),
            position_msg("777777777", ts="2026-09-08 10:05:00.000 +0000 UTC"),
            static_msg("777777777"),
            "{malformed",
        ]
        src = AISStreamSource(api_key="test-key")
        run = src.run_session(sync_factory(messages), max_messages=len(messages))

        # One malformed -> PARTIAL.
        self.assertEqual(run.status, IngestionRun.Status.PARTIAL)
        self.assertEqual(run.records_fetched, 4)
        self.assertEqual(run.records_written, 2)  # two distinct positions
        self.assertEqual(AISPosition.objects.filter(mmsi="777777777").count(), 2)

    def test_reconnect_on_stream_error(self):
        # First connection raises; second yields a message. consume() should
        # reconnect and still process.
        calls = {"n": 0}

        def flaky_factory():
            calls["n"] += 1
            if calls["n"] == 1:
                def boom():
                    raise ConnectionError("dropped")
                    yield  # pragma: no cover
                return boom()

            def good():
                yield position_msg("888888888")

            return good()

        src = AISStreamSource(api_key="test-key")
        src.reconnect_backoff_seconds = 0  # no real sleeping
        run = src.run_session(flaky_factory, max_messages=1)
        self.assertEqual(run.status, IngestionRun.Status.SUCCESS)
        self.assertEqual(AISPosition.objects.filter(mmsi="888888888").count(), 1)
        self.assertGreaterEqual(run.context.get("reconnects", 0), 1)


class AISConfigTests(TestCase):
    @override_settings(EXTERNAL_APIS={"AISSTREAM_API_KEY": ""})
    def test_missing_api_key_raises_config_error(self):
        src = AISStreamSource()
        with self.assertRaises(SourceConfigError):
            src.subscription_payload()

    @override_settings(EXTERNAL_APIS={"AISSTREAM_API_KEY": "secret-key"})
    def test_subscription_payload_contains_key_and_filters(self):
        src = AISStreamSource()
        payload = src.subscription_payload()
        self.assertEqual(payload["APIKey"], "secret-key")
        self.assertIn("PositionReport", payload["FilterMessageTypes"])
        self.assertIn("ShipStaticData", payload["FilterMessageTypes"])

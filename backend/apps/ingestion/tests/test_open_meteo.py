"""Tests for the Open-Meteo weather adapter using mocked responses.

No network: a fake http_get_json returns recorded Open-Meteo payloads. Verifies
hourly expansion, WMO condition mapping, WeatherObservation normalization,
caching (repeat requests avoided), dedup, and graceful unavailability.
"""
from decimal import Decimal

from django.core.cache import cache
from django.test import TestCase

from apps.catalog.models import Port
from apps.ingestion.models import IngestionRun
from apps.ingestion.sources.open_meteo import OpenMeteoSource
from apps.operations.models import WeatherObservation


def meteo_payload(times, temps, precip, codes, wspd, wdir):
    return {
        "latitude": 20.26,
        "longitude": 86.67,
        "hourly": {
            "time": times,
            "temperature_2m": temps,
            "precipitation": precip,
            "weathercode": codes,
            "windspeed_10m": wspd,
            "winddirection_10m": wdir,
        },
    }


SAMPLE = meteo_payload(
    times=["2026-09-09T00:00", "2026-09-09T01:00", "2026-09-09T02:00"],
    temps=[28.5, 28.1, 27.9],
    precip=[0.0, 1.2, 3.4],
    codes=[0, 61, 95],  # clear, slight rain, thunderstorm
    wspd=[10.0, 14.5, 22.0],
    wdir=[180, 200, 210],
)


def counting_http(payload):
    calls = {"n": 0}

    def _get(url, params):
        calls["n"] += 1
        return payload

    _get.calls = calls
    return _get


def one_location():
    return [("Paradip", Decimal("20.264000"), Decimal("86.670000"))]


class OpenMeteoIngestionTests(TestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)

    def test_expands_hourly_into_observations(self):
        src = OpenMeteoSource(
            locations=one_location(), http_get_json=counting_http(SAMPLE)
        )
        result = src.run()
        self.assertEqual(result.status, IngestionRun.Status.SUCCESS)
        self.assertEqual(WeatherObservation.objects.count(), 3)
        for obs in WeatherObservation.objects.all():
            self.assertTrue(obs.is_forecast)
            self.assertEqual(obs.source, "open_meteo")

    def test_condition_mapping_and_fields(self):
        src = OpenMeteoSource(locations=one_location(), http_get_json=counting_http(SAMPLE))
        src.run()
        first = WeatherObservation.objects.order_by("timestamp").first()
        self.assertEqual(first.temperature_c, Decimal("28.50"))
        self.assertEqual(first.wind_speed_kn, Decimal("10.00"))
        self.assertEqual(first.wind_dir_deg, Decimal("180.00"))
        self.assertEqual(first.precipitation_mm, Decimal("0.00"))
        self.assertEqual(first.weather_code, 0)
        self.assertEqual(first.weather_condition, "Clear sky")
        storm = WeatherObservation.objects.get(weather_code=95)
        self.assertEqual(storm.weather_condition, "Thunderstorm")

    def test_links_port_when_name_matches(self):
        # Paradip is seeded; the observation should link to it.
        src = OpenMeteoSource(locations=one_location(), http_get_json=counting_http(SAMPLE))
        src.run()
        paradip = Port.objects.get(name="Paradip")
        self.assertTrue(WeatherObservation.objects.filter(port=paradip).exists())

    def test_caching_avoids_second_external_call(self):
        http = counting_http(SAMPLE)
        # First run hits the "network".
        OpenMeteoSource(locations=one_location(), http_get_json=http).run()
        self.assertEqual(http.calls["n"], 1)
        # Second run (same location, within TTL) should use the cache.
        src2 = OpenMeteoSource(locations=one_location(), http_get_json=http)
        src2.run()
        self.assertEqual(http.calls["n"], 1)  # no new external call
        self.assertEqual(src2._cache_hits, 1)

    def test_cache_can_be_disabled(self):
        http = counting_http(SAMPLE)
        OpenMeteoSource(locations=one_location(), http_get_json=http, use_cache=False).run()
        OpenMeteoSource(locations=one_location(), http_get_json=http, use_cache=False).run()
        self.assertEqual(http.calls["n"], 2)  # both call out

    def test_dedup_reingest_upserts(self):
        OpenMeteoSource(locations=one_location(), http_get_json=counting_http(SAMPLE), use_cache=False).run()
        result2 = OpenMeteoSource(
            locations=one_location(), http_get_json=counting_http(SAMPLE), use_cache=False
        ).run()
        self.assertEqual(WeatherObservation.objects.count(), 3)
        self.assertEqual(result2.duplicate, 3)

    def test_missing_variable_leaves_null(self):
        payload = {
            "latitude": 20.26, "longitude": 86.67,
            "hourly": {
                "time": ["2026-09-09T00:00"],
                "temperature_2m": [28.0],
                # no precipitation / weathercode / wind arrays
            },
        }
        src = OpenMeteoSource(locations=one_location(), http_get_json=counting_http(payload))
        src.run()
        obs = WeatherObservation.objects.get()
        self.assertEqual(obs.temperature_c, Decimal("28.00"))
        self.assertIsNone(obs.precipitation_mm)
        self.assertIsNone(obs.wind_speed_kn)
        self.assertIsNone(obs.weather_code)
        self.assertEqual(obs.weather_condition, "")

    def test_unavailable_when_no_hourly_block(self):
        src = OpenMeteoSource(
            locations=one_location(), http_get_json=counting_http({"error": True})
        )
        result = src.run()
        self.assertEqual(result.status, IngestionRun.Status.SOURCE_UNAVAILABLE)

    def test_all_seven_locations_default(self):
        src = OpenMeteoSource()  # default locations
        names = [loc[0] for loc in src.locations]
        for expected in [
            "Paradip", "Dhamra", "Gopalpur", "Visakhapatnam",
            "Gangavaram", "Haldia", "Sagar/Sandheads",
        ]:
            self.assertIn(expected, names)

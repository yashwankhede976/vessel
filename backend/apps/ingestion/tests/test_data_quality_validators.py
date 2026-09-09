"""Unit tests for the data-quality validators."""
from django.test import SimpleTestCase

from apps.ingestion.exceptions import ValidationError
from apps.ingestion.validators import (
    no_future_timestamp,
    non_negative,
    valid_coordinates,
    valid_date_order,
    valid_freight_rate,
    valid_vessel_dimensions,
)


class CoordinateValidatorTests(SimpleTestCase):
    def test_valid_coords_pass(self):
        v = valid_coordinates()
        self.assertEqual(v({"latitude": 20.0, "longitude": 86.0})["latitude"], 20.0)

    def test_impossible_latitude_rejected(self):
        with self.assertRaises(ValidationError):
            valid_coordinates()({"latitude": 999, "longitude": 0})

    def test_impossible_longitude_rejected(self):
        with self.assertRaises(ValidationError):
            valid_coordinates()({"latitude": 0, "longitude": 500})

    def test_none_allowed_by_default(self):
        v = valid_coordinates()
        self.assertEqual(v({"latitude": None, "longitude": None}), {"latitude": None, "longitude": None})


class NonNegativeTests(SimpleTestCase):
    def test_negative_rejected(self):
        with self.assertRaises(ValidationError):
            non_negative("qty")({"qty": -1})

    def test_zero_and_positive_ok(self):
        v = non_negative("qty")
        self.assertEqual(v({"qty": 0})["qty"], 0)
        self.assertEqual(v({"qty": 5})["qty"], 5)


class FutureTimestampTests(SimpleTestCase):
    def test_future_rejected(self):
        with self.assertRaises(ValidationError):
            no_future_timestamp("ts")({"ts": "2999-01-01T00:00:00+00:00"})

    def test_past_ok(self):
        v = no_future_timestamp("ts")
        self.assertEqual(v({"ts": "2020-01-01T00:00:00+00:00"})["ts"], "2020-01-01T00:00:00+00:00")


class DateOrderTests(SimpleTestCase):
    def test_out_of_order_rejected(self):
        with self.assertRaises(ValidationError):
            valid_date_order("start", "end")(
                {"start": "2026-02-01", "end": "2026-01-01"}
            )

    def test_in_order_ok(self):
        v = valid_date_order("start", "end")
        rec = {"start": "2026-01-01", "end": "2026-02-01"}
        self.assertEqual(v(rec), rec)


class VesselDimensionTests(SimpleTestCase):
    def test_valid_dimensions_pass(self):
        v = valid_vessel_dimensions()
        rec = {"loa": 200, "beam": 32, "draft": 12.5, "dwt": 58000}
        self.assertEqual(v(rec), rec)

    def test_absurd_draft_rejected(self):
        with self.assertRaises(ValidationError):
            valid_vessel_dimensions()({"draft": 999})

    def test_zero_loa_rejected(self):
        with self.assertRaises(ValidationError):
            valid_vessel_dimensions()({"loa": 0})


class FreightRateTests(SimpleTestCase):
    def test_negative_rate_rejected(self):
        with self.assertRaises(ValidationError):
            valid_freight_rate("rate")({"rate": -5})

    def test_absurd_rate_rejected(self):
        with self.assertRaises(ValidationError):
            valid_freight_rate("rate")({"rate": 100000})

    def test_reasonable_rate_ok(self):
        v = valid_freight_rate("rate")
        self.assertEqual(v({"rate": 22})["rate"], 22)

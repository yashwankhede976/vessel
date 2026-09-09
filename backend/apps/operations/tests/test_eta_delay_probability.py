"""Unit tests for the ETA delay_probability / delay_reasons extension."""
from apps.operations.services.eta import ETAInput, predict_eta


def test_clean_voyage_low_delay_probability():
    r = predict_eta(ETAInput(route_distance_nm=5000, speed_kn=14))
    assert 0.0 <= r.delay_probability <= 1.0
    # No weather/congestion/waiting -> low probability of material lateness.
    assert r.delay_probability < 0.5
    assert r.delay_reasons == []


def test_heavy_delays_high_probability_and_reasons():
    r = predict_eta(ETAInput(
        route_distance_nm=6500, speed_kn=12, weather_risk=0.6,
        destination_congestion=80, expected_port_waiting_days=4,
    ))
    assert r.delay_probability > 0.5
    # The material causes are surfaced, largest first.
    assert "destination_congestion" in r.delay_reasons
    assert set(r.delay_reasons) <= {"weather", "destination_congestion", "port_waiting"}


def test_delay_probability_monotonic_in_congestion():
    low = predict_eta(ETAInput(route_distance_nm=6000, speed_kn=13, destination_congestion=10))
    high = predict_eta(ETAInput(route_distance_nm=6000, speed_kn=13, destination_congestion=90))
    assert high.delay_probability >= low.delay_probability


def test_backward_compatible_fields_present():
    r = predict_eta(ETAInput(route_distance_nm=5000, speed_kn=14))
    d = r.to_dict()
    # New fields exist alongside the original ones.
    for f in ("eta", "eta_p50", "eta_p80", "eta_p95", "delay_causes",
              "delay_probability", "delay_reasons"):
        assert f in d

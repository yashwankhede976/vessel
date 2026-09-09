"""Uncertainty estimation for freight forecasts.

The prediction interval comes from **quantile regression** — we train separate
XGBoost models for a lower and an upper quantile (e.g. 0.1 and 0.9), giving a
data-derived interval that captures the model's dispersion at each point. This
is not a Gaussian assumption and not an arbitrary +/- band.

The **confidence score** is derived deterministically from the *relative* width
of that interval — a tight interval (relative to the prediction) means high
confidence, a wide interval means low confidence. The exact formula is below and
in docs/FREIGHT_FORECAST_UNCERTAINTY.md; it contains no hand-picked magic
confidence values.

confidence = 1 / (1 + (relative_width / k))

where
    relative_width = (upper - lower) / max(|predicted|, eps)
    k              = a fixed scale constant (relative width at which confidence
                     = 0.5). Documented, not tuned per-forecast.

Properties (why this is principled):
- monotonic: wider interval => lower confidence, strictly.
- bounded: confidence in (0, 1].
- scale-free: uses relative (not absolute) width, so it behaves consistently
  across lanes/vessel classes with different rate levels.
- a zero-width interval => confidence = 1.0 (maximal certainty).
"""
from __future__ import annotations

from dataclasses import dataclass, asdict

# Relative interval width at which confidence == 0.5. Chosen as a single, fixed,
# documented constant: a prediction interval spanning 20% of the predicted value
# is treated as "half-confident". This is the ONLY tunable and it is explicit.
CONFIDENCE_SCALE_K = 0.20

_EPS = 1e-9


@dataclass
class ForecastResult:
    """A single forecast with a data-derived prediction interval + confidence."""

    predicted: float
    lower: float
    upper: float
    confidence: float
    # Provenance of the interval so the number is never "arbitrary".
    lower_quantile: float
    upper_quantile: float
    confidence_scale_k: float = CONFIDENCE_SCALE_K

    def to_dict(self) -> dict:
        return asdict(self)


def relative_width(predicted: float, lower: float, upper: float) -> float:
    """Interval width as a fraction of the (absolute) predicted value."""
    return (upper - lower) / max(abs(predicted), _EPS)


def confidence_from_interval(
    predicted: float, lower: float, upper: float, *, k: float = CONFIDENCE_SCALE_K
) -> float:
    """Map a prediction interval to a confidence in (0, 1] (see module docstring)."""
    rw = max(0.0, relative_width(predicted, lower, upper))
    return 1.0 / (1.0 + (rw / k))


def build_forecast_result(
    predicted: float,
    lower: float,
    upper: float,
    *,
    lower_quantile: float,
    upper_quantile: float,
    k: float = CONFIDENCE_SCALE_K,
    round_to: int = 2,
) -> ForecastResult:
    """Assemble a ForecastResult, enforcing lower <= predicted <= upper.

    Quantile models are trained independently, so on rare points the raw
    quantiles can cross or the point estimate can fall just outside them. We
    clamp to restore the ordering guarantee before computing confidence, so the
    returned structure is always coherent.
    """
    lo, hi = float(lower), float(upper)
    if lo > hi:  # quantile crossing — repair by swapping
        lo, hi = hi, lo
    pred = float(predicted)
    # Ensure the point estimate sits within the interval.
    pred = min(max(pred, lo), hi)

    conf = confidence_from_interval(pred, lo, hi, k=k)

    r = round_to
    return ForecastResult(
        predicted=round(pred, r),
        lower=round(lo, r),
        upper=round(hi, r),
        confidence=round(conf, r),
        lower_quantile=lower_quantile,
        upper_quantile=upper_quantile,
        confidence_scale_k=k,
    )

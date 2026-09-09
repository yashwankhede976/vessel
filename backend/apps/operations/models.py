"""
Operational-intelligence models for the Vessel platform.

Covers observed data (AIS, port calls, congestion, weather, marine, cyclone,
prices, trade, bunkers) and derived outputs (freight/ETA forecasts, risk
scores, recommendations).

Design notes:
- Reuses catalog.TimeStampedModel for created_at/updated_at.
- Monetary and precise physical values use DecimalField (no float columns).
- Geospatial data is PostGIS-compatible: every geo model carries portable
  latitude/longitude DecimalFields, and additionally a `geom` PointField when
  settings.USE_POSTGIS is enabled (see apps/operations/geo.py).
- Indexes are declared for timestamp, vessel, port, route, origin, destination
  access patterns as required by the query layer.

No ingestion logic and no API endpoints are defined here (data modelling only).
"""
from __future__ import annotations

from decimal import Decimal

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from apps.catalog.models import TimeStampedModel

from .geo import geo_point_field

# Validators reused across models.
LAT = [MinValueValidator(Decimal("-90")), MaxValueValidator(Decimal("90"))]
LON = [MinValueValidator(Decimal("-180")), MaxValueValidator(Decimal("180"))]
NON_NEGATIVE = [MinValueValidator(Decimal("0"))]
PCT = [MinValueValidator(Decimal("0")), MaxValueValidator(Decimal("100"))]
SCORE = [MinValueValidator(Decimal("0")), MaxValueValidator(Decimal("1"))]


# ===========================================================================
# Vessel movement
# ===========================================================================
class AISPosition(TimeStampedModel):
    """A timestamped AIS position report for a vessel."""

    vessel = models.ForeignKey(
        "catalog.Vessel", on_delete=models.CASCADE, related_name="positions"
    )
    timestamp = models.DateTimeField()

    latitude = models.DecimalField(max_digits=9, decimal_places=6, validators=LAT)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, validators=LON)
    # PostGIS point (only present when USE_POSTGIS); portable lat/lon always kept.
    geom = geo_point_field()

    # Speed over ground (knots), course/heading (degrees).
    sog = models.DecimalField(
        "SOG (kn)", max_digits=5, decimal_places=2, null=True, blank=True,
        validators=NON_NEGATIVE,
    )
    cog = models.DecimalField(
        "COG (deg)", max_digits=5, decimal_places=2, null=True, blank=True,
        validators=[MinValueValidator(Decimal("0")), MaxValueValidator(Decimal("360"))],
    )
    heading = models.DecimalField(
        "heading (deg)", max_digits=5, decimal_places=2, null=True, blank=True,
        validators=[MinValueValidator(Decimal("0")), MaxValueValidator(Decimal("360"))],
    )
    nav_status = models.CharField(max_length=64, blank=True)
    source = models.CharField(max_length=64, blank=True)

    class Meta:
        ordering = ["-timestamp"]
        constraints = [
            models.UniqueConstraint(
                fields=["vessel", "timestamp"], name="uq_ais_vessel_ts"
            ),
        ]
        indexes = [
            models.Index(fields=["vessel", "-timestamp"], name="ais_vessel_ts_idx"),
            models.Index(fields=["timestamp"], name="ais_ts_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.vessel_id} @ {self.timestamp:%Y-%m-%d %H:%M}"


class PortCall(TimeStampedModel):
    """A vessel's arrival/berthing/departure event at a port."""

    class Event(models.TextChoices):
        ARRIVAL = "arrival", "Arrival (anchorage)"
        BERTHED = "berthed", "Berthed"
        DEPARTURE = "departure", "Departure"

    vessel = models.ForeignKey(
        "catalog.Vessel", on_delete=models.CASCADE, related_name="port_calls"
    )
    port = models.ForeignKey(
        "catalog.Port", on_delete=models.CASCADE, related_name="port_calls"
    )
    berth = models.ForeignKey(
        "catalog.Berth", on_delete=models.SET_NULL, related_name="port_calls",
        null=True, blank=True,
    )

    arrival_at = models.DateTimeField(null=True, blank=True)
    berthed_at = models.DateTimeField(null=True, blank=True)
    departure_at = models.DateTimeField(null=True, blank=True)
    event = models.CharField(max_length=10, choices=Event.choices, default=Event.ARRIVAL)
    source = models.CharField(max_length=64, blank=True)

    class Meta:
        ordering = ["-arrival_at"]
        indexes = [
            models.Index(fields=["vessel", "-arrival_at"], name="portcall_vessel_idx"),
            models.Index(fields=["port", "-arrival_at"], name="portcall_port_idx"),
            models.Index(fields=["arrival_at"], name="portcall_arrival_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.vessel_id} @ {self.port_id} ({self.event})"


# ===========================================================================
# Port congestion
# ===========================================================================
class PortCongestionObservation(TimeStampedModel):
    """A dated snapshot of congestion / expected waiting at a port."""

    port = models.ForeignKey(
        "catalog.Port", on_delete=models.CASCADE, related_name="congestion_observations"
    )
    observed_at = models.DateTimeField()

    vessels_waiting = models.PositiveIntegerField(null=True, blank=True)
    avg_wait_days = models.DecimalField(
        "avg wait (days)", max_digits=6, decimal_places=2, null=True, blank=True,
        validators=NON_NEGATIVE,
    )
    berth_occupancy_pct = models.DecimalField(
        "berth occupancy (%)", max_digits=5, decimal_places=2, null=True, blank=True,
        validators=PCT,
    )
    source = models.CharField(max_length=64, blank=True)
    is_estimated = models.BooleanField(default=False)

    class Meta:
        ordering = ["-observed_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["port", "observed_at", "source"],
                name="uq_congestion_port_ts_source",
            ),
        ]
        indexes = [
            models.Index(fields=["port", "-observed_at"], name="cong_port_ts_idx"),
            models.Index(fields=["observed_at"], name="cong_ts_idx"),
        ]

    def __str__(self) -> str:
        return f"congestion {self.port_id} @ {self.observed_at:%Y-%m-%d}"


# ===========================================================================
# Weather / marine / cyclone
# ===========================================================================
class WeatherObservation(TimeStampedModel):
    """A weather observation/forecast point (wind, precipitation, etc.)."""

    # Optional association to a port; otherwise a free lat/lon point.
    port = models.ForeignKey(
        "catalog.Port", on_delete=models.SET_NULL, related_name="weather_observations",
        null=True, blank=True,
    )
    timestamp = models.DateTimeField()
    latitude = models.DecimalField(max_digits=9, decimal_places=6, validators=LAT)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, validators=LON)
    geom = geo_point_field()

    wind_speed_kn = models.DecimalField(
        "wind speed (kn)", max_digits=6, decimal_places=2, null=True, blank=True,
        validators=NON_NEGATIVE,
    )
    wind_dir_deg = models.DecimalField(
        "wind dir (deg)", max_digits=5, decimal_places=2, null=True, blank=True,
        validators=[MinValueValidator(Decimal("0")), MaxValueValidator(Decimal("360"))],
    )
    precipitation_mm = models.DecimalField(
        "precipitation (mm)", max_digits=7, decimal_places=2, null=True, blank=True,
        validators=NON_NEGATIVE,
    )
    temperature_c = models.DecimalField(
        "temperature (C)", max_digits=5, decimal_places=2, null=True, blank=True,
    )
    is_forecast = models.BooleanField(default=False)
    source = models.CharField(max_length=64, blank=True)

    class Meta:
        ordering = ["-timestamp"]
        indexes = [
            models.Index(fields=["port", "-timestamp"], name="wx_port_ts_idx"),
            models.Index(fields=["timestamp"], name="wx_ts_idx"),
        ]

    def __str__(self) -> str:
        return f"weather @ {self.latitude},{self.longitude} {self.timestamp:%Y-%m-%d}"


class MarineObservation(TimeStampedModel):
    """A marine/ocean-state observation (waves, currents, sea state)."""

    port = models.ForeignKey(
        "catalog.Port", on_delete=models.SET_NULL, related_name="marine_observations",
        null=True, blank=True,
    )
    timestamp = models.DateTimeField()
    latitude = models.DecimalField(max_digits=9, decimal_places=6, validators=LAT)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, validators=LON)
    geom = geo_point_field()

    significant_wave_height_m = models.DecimalField(
        "sig. wave height (m)", max_digits=5, decimal_places=2, null=True, blank=True,
        validators=NON_NEGATIVE,
    )
    wave_period_s = models.DecimalField(
        "wave period (s)", max_digits=5, decimal_places=2, null=True, blank=True,
        validators=NON_NEGATIVE,
    )
    swell_direction_deg = models.DecimalField(
        "swell dir (deg)", max_digits=5, decimal_places=2, null=True, blank=True,
        validators=[MinValueValidator(Decimal("0")), MaxValueValidator(Decimal("360"))],
    )
    current_speed_kn = models.DecimalField(
        "current speed (kn)", max_digits=5, decimal_places=2, null=True, blank=True,
        validators=NON_NEGATIVE,
    )
    sea_surface_temp_c = models.DecimalField(
        "SST (C)", max_digits=5, decimal_places=2, null=True, blank=True,
    )
    is_forecast = models.BooleanField(default=False)
    source = models.CharField(max_length=64, blank=True)

    class Meta:
        ordering = ["-timestamp"]
        indexes = [
            models.Index(fields=["port", "-timestamp"], name="marine_port_ts_idx"),
            models.Index(fields=["timestamp"], name="marine_ts_idx"),
        ]

    def __str__(self) -> str:
        return f"marine @ {self.latitude},{self.longitude} {self.timestamp:%Y-%m-%d}"


class CycloneObservation(TimeStampedModel):
    """A cyclone track/advisory point (Bay of Bengal and relevant basins)."""

    class Category(models.TextChoices):
        LOW = "low", "Low"
        DEPRESSION = "depression", "Depression"
        CYCLONIC_STORM = "cyclonic_storm", "Cyclonic Storm"
        SEVERE = "severe", "Severe Cyclonic Storm"
        VERY_SEVERE = "very_severe", "Very Severe Cyclonic Storm"
        SUPER = "super", "Super Cyclonic Storm"

    # Identifier for the storm system (advisories share a name/id).
    system_name = models.CharField(max_length=120)
    advisory_no = models.CharField(max_length=32, blank=True)
    timestamp = models.DateTimeField()

    latitude = models.DecimalField(max_digits=9, decimal_places=6, validators=LAT)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, validators=LON)
    geom = geo_point_field()

    category = models.CharField(
        max_length=16, choices=Category.choices, default=Category.LOW
    )
    max_wind_kn = models.DecimalField(
        "max wind (kn)", max_digits=6, decimal_places=2, null=True, blank=True,
        validators=NON_NEGATIVE,
    )
    central_pressure_hpa = models.DecimalField(
        "central pressure (hPa)", max_digits=7, decimal_places=2, null=True, blank=True,
        validators=NON_NEGATIVE,
    )
    is_forecast = models.BooleanField(default=False)
    source = models.CharField(max_length=64, blank=True)

    class Meta:
        ordering = ["-timestamp"]
        constraints = [
            models.UniqueConstraint(
                fields=["system_name", "timestamp", "source"],
                name="uq_cyclone_system_ts_source",
            ),
        ]
        indexes = [
            models.Index(fields=["system_name", "-timestamp"], name="cyclone_system_idx"),
            models.Index(fields=["timestamp"], name="cyclone_ts_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.system_name} {self.category} @ {self.timestamp:%Y-%m-%d %H:%M}"


# ===========================================================================
# Market / trade data
# ===========================================================================
class CommodityPriceObservation(TimeStampedModel):
    """A dated commodity price (e.g. coal), financial value as Decimal."""

    commodity = models.ForeignKey(
        "catalog.Commodity", on_delete=models.CASCADE, related_name="price_observations"
    )
    observed_on = models.DateField()
    price = models.DecimalField(max_digits=14, decimal_places=4, validators=NON_NEGATIVE)
    currency = models.CharField(max_length=3, default="USD")
    unit = models.CharField(max_length=16, default="tonne")
    source = models.CharField(max_length=64, blank=True)
    is_estimated = models.BooleanField(default=False)

    class Meta:
        ordering = ["-observed_on"]
        constraints = [
            models.UniqueConstraint(
                fields=["commodity", "observed_on", "source"],
                name="uq_commprice_natural",
            ),
        ]
        indexes = [
            models.Index(fields=["commodity", "-observed_on"], name="commprice_comm_idx"),
            models.Index(fields=["observed_on"], name="commprice_date_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.commodity_id} {self.price}/{self.currency} on {self.observed_on}"


class TradeObservation(TimeStampedModel):
    """A trade-flow observation (e.g. UN Comtrade): volume/value by lane."""

    commodity = models.ForeignKey(
        "catalog.Commodity", on_delete=models.CASCADE, related_name="trade_observations"
    )
    origin = models.ForeignKey(
        "catalog.Origin", on_delete=models.SET_NULL, related_name="trade_observations",
        null=True, blank=True,
    )
    destination_port = models.ForeignKey(
        "catalog.Port", on_delete=models.SET_NULL, related_name="trade_observations",
        null=True, blank=True,
    )
    reporter_country = models.CharField(max_length=80, blank=True)
    partner_country = models.CharField(max_length=80, blank=True)
    period = models.DateField(help_text="First day of the reporting period.")

    quantity_tonnes = models.DecimalField(
        "quantity (t)", max_digits=16, decimal_places=2, null=True, blank=True,
        validators=NON_NEGATIVE,
    )
    trade_value = models.DecimalField(
        "trade value", max_digits=18, decimal_places=2, null=True, blank=True,
        validators=NON_NEGATIVE,
    )
    currency = models.CharField(max_length=3, default="USD")
    source = models.CharField(max_length=64, blank=True)

    class Meta:
        ordering = ["-period"]
        indexes = [
            models.Index(fields=["commodity", "-period"], name="trade_comm_period_idx"),
            models.Index(fields=["origin"], name="trade_origin_idx"),
            models.Index(fields=["destination_port"], name="trade_dest_idx"),
            models.Index(fields=["period"], name="trade_period_idx"),
        ]

    def __str__(self) -> str:
        return f"trade {self.commodity_id} {self.period}"


class BunkerPriceObservation(TimeStampedModel):
    """A dated bunker (marine fuel) price at a location/hub."""

    class FuelGrade(models.TextChoices):
        VLSFO = "vlsfo", "VLSFO"
        HSFO = "hsfo", "HSFO"
        MGO = "mgo", "MGO"
        LSMGO = "lsmgo", "LSMGO"

    # Optional port/hub the price is quoted at.
    port = models.ForeignKey(
        "catalog.Port", on_delete=models.SET_NULL, related_name="bunker_prices",
        null=True, blank=True,
    )
    hub = models.CharField(max_length=80, blank=True)
    fuel_grade = models.CharField(
        max_length=8, choices=FuelGrade.choices, default=FuelGrade.VLSFO
    )
    observed_on = models.DateField()
    price_per_tonne = models.DecimalField(
        "price/t", max_digits=12, decimal_places=2, validators=NON_NEGATIVE
    )
    currency = models.CharField(max_length=3, default="USD")
    source = models.CharField(max_length=64, blank=True)

    class Meta:
        ordering = ["-observed_on"]
        constraints = [
            models.UniqueConstraint(
                fields=["port", "hub", "fuel_grade", "observed_on", "source"],
                name="uq_bunker_natural",
            ),
        ]
        indexes = [
            models.Index(fields=["port", "-observed_on"], name="bunker_port_idx"),
            models.Index(fields=["fuel_grade", "-observed_on"], name="bunker_grade_idx"),
            models.Index(fields=["observed_on"], name="bunker_date_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.fuel_grade} {self.price_per_tonne}/{self.currency} on {self.observed_on}"


# ===========================================================================
# Derived outputs: forecasts, risk, recommendations
# ===========================================================================
class FreightForecast(TimeStampedModel):
    """A model-produced freight-rate forecast for a route/horizon.

    Prediction only (produced by the ML layer); no business rules here.
    """

    class Horizon(models.TextChoices):
        SHORT_TERM = "short_term", "Short-term (days-weeks)"
        MEDIUM_TERM = "medium_term", "Medium-term (weeks-months)"

    route = models.ForeignKey(
        "catalog.Route", on_delete=models.CASCADE, related_name="freight_forecasts"
    )
    vessel_type = models.CharField(max_length=14, blank=True)
    # When the forecast was generated vs the date it targets.
    generated_at = models.DateTimeField()
    target_date = models.DateField()
    horizon = models.CharField(
        max_length=12, choices=Horizon.choices, default=Horizon.SHORT_TERM
    )

    predicted_rate_per_tonne = models.DecimalField(
        "predicted rate/t", max_digits=12, decimal_places=2, validators=NON_NEGATIVE
    )
    # Confidence band bounds (financial → Decimal).
    lower_bound = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True, validators=NON_NEGATIVE
    )
    upper_bound = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True, validators=NON_NEGATIVE
    )
    currency = models.CharField(max_length=3, default="USD")

    model_name = models.CharField(max_length=80, blank=True)
    model_version = models.CharField(max_length=40, blank=True)

    class Meta:
        ordering = ["-generated_at", "target_date"]
        constraints = [
            models.UniqueConstraint(
                fields=["route", "vessel_type", "target_date", "horizon",
                        "model_name", "model_version"],
                name="uq_freight_forecast_natural",
            ),
        ]
        indexes = [
            models.Index(fields=["route", "target_date"], name="ff_route_target_idx"),
            models.Index(fields=["generated_at"], name="ff_generated_idx"),
            models.Index(fields=["target_date"], name="ff_target_idx"),
        ]

    def __str__(self) -> str:
        return f"forecast {self.route_id} {self.target_date} {self.predicted_rate_per_tonne}"


class ETAForecast(TimeStampedModel):
    """A predicted arrival time for a vessel at a destination port."""

    vessel = models.ForeignKey(
        "catalog.Vessel", on_delete=models.CASCADE, related_name="eta_forecasts"
    )
    destination_port = models.ForeignKey(
        "catalog.Port", on_delete=models.CASCADE, related_name="eta_forecasts"
    )
    # Optional route/port-call context.
    route = models.ForeignKey(
        "catalog.Route", on_delete=models.SET_NULL, related_name="eta_forecasts",
        null=True, blank=True,
    )

    generated_at = models.DateTimeField()
    predicted_eta = models.DateTimeField()
    # Uncertainty as a +/- window in hours.
    uncertainty_hours = models.DecimalField(
        "uncertainty (h)", max_digits=7, decimal_places=2, null=True, blank=True,
        validators=NON_NEGATIVE,
    )
    model_name = models.CharField(max_length=80, blank=True)
    model_version = models.CharField(max_length=40, blank=True)

    class Meta:
        ordering = ["-generated_at"]
        indexes = [
            models.Index(fields=["vessel", "-generated_at"], name="eta_vessel_idx"),
            models.Index(fields=["destination_port", "-generated_at"], name="eta_dest_idx"),
            models.Index(fields=["predicted_eta"], name="eta_predicted_idx"),
            models.Index(fields=["generated_at"], name="eta_generated_idx"),
        ]

    def __str__(self) -> str:
        return f"ETA {self.vessel_id} -> {self.destination_port_id} {self.predicted_eta:%Y-%m-%d}"


class RiskScore(TimeStampedModel):
    """A derived risk score (demurrage, weather, geopolitical, etc.).

    Scores are normalized 0..1. The subject is described generically so a score
    can attach to a route, port, vessel, or a cargo requirement.
    """

    class RiskType(models.TextChoices):
        DEMURRAGE = "demurrage", "Demurrage"
        WEATHER = "weather", "Weather / marine"
        CONGESTION = "congestion", "Port congestion"
        GEOPOLITICAL = "geopolitical", "Geopolitical / disruption"

    class Level(models.TextChoices):
        LOW = "low", "Low"
        MEDIUM = "medium", "Medium"
        HIGH = "high", "High"

    risk_type = models.CharField(max_length=14, choices=RiskType.choices)
    generated_at = models.DateTimeField()

    # Optional subjects (any combination) the score applies to.
    route = models.ForeignKey(
        "catalog.Route", on_delete=models.CASCADE, related_name="risk_scores",
        null=True, blank=True,
    )
    port = models.ForeignKey(
        "catalog.Port", on_delete=models.CASCADE, related_name="risk_scores",
        null=True, blank=True,
    )
    vessel = models.ForeignKey(
        "catalog.Vessel", on_delete=models.CASCADE, related_name="risk_scores",
        null=True, blank=True,
    )
    origin = models.ForeignKey(
        "catalog.Origin", on_delete=models.CASCADE, related_name="risk_scores",
        null=True, blank=True,
    )
    cargo_requirement = models.ForeignKey(
        "catalog.CargoRequirement", on_delete=models.CASCADE,
        related_name="risk_scores", null=True, blank=True,
    )

    # Normalized score 0..1 and a categorical level.
    score = models.DecimalField(max_digits=4, decimal_places=3, validators=SCORE)
    level = models.CharField(max_length=6, choices=Level.choices, default=Level.LOW)
    # Explainability: main contributing drivers.
    drivers = models.JSONField(default=dict, blank=True)

    model_name = models.CharField(max_length=80, blank=True)
    model_version = models.CharField(max_length=40, blank=True)

    class Meta:
        ordering = ["-generated_at"]
        indexes = [
            models.Index(fields=["risk_type", "-generated_at"], name="risk_type_idx"),
            models.Index(fields=["route", "-generated_at"], name="risk_route_idx"),
            models.Index(fields=["port", "-generated_at"], name="risk_port_idx"),
            models.Index(fields=["vessel", "-generated_at"], name="risk_vessel_idx"),
            models.Index(fields=["origin", "-generated_at"], name="risk_origin_idx"),
            models.Index(fields=["generated_at"], name="risk_generated_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.risk_type} risk {self.score} ({self.level})"


class Recommendation(TimeStampedModel):
    """A decision recommendation with explainability and an audit trail.

    Produced by the domain layer from forecasts/optimization; persisted with
    inputs, confidence, and model version for audit (NFR-XAI, NFR-AUD).
    """

    class RecType(models.TextChoices):
        MARKET_ENTRY = "market_entry", "Market-entry timing"
        CONTRACT_TYPE = "contract_type", "Contract type"
        LAYCAN = "laycan", "Laycan window"
        ALT_PORT = "alt_port", "Alternative port"
        SOURCING = "sourcing", "Multi-origin sourcing"
        IDLE_VESSEL = "idle_vessel", "Idle-vessel employment"

    rec_type = models.CharField(max_length=14, choices=RecType.choices)
    generated_at = models.DateTimeField()

    # Optional subjects the recommendation concerns.
    cargo_requirement = models.ForeignKey(
        "catalog.CargoRequirement", on_delete=models.CASCADE,
        related_name="recommendations", null=True, blank=True,
    )
    route = models.ForeignKey(
        "catalog.Route", on_delete=models.SET_NULL, related_name="recommendations",
        null=True, blank=True,
    )
    origin = models.ForeignKey(
        "catalog.Origin", on_delete=models.SET_NULL, related_name="recommendations",
        null=True, blank=True,
    )
    destination_port = models.ForeignKey(
        "catalog.Port", on_delete=models.SET_NULL, related_name="recommendations",
        null=True, blank=True,
    )
    vessel = models.ForeignKey(
        "catalog.Vessel", on_delete=models.SET_NULL, related_name="recommendations",
        null=True, blank=True,
    )

    # Human-readable summary + confidence 0..1.
    summary = models.CharField(max_length=255)
    confidence = models.DecimalField(
        max_digits=4, decimal_places=3, null=True, blank=True, validators=SCORE
    )
    # Estimated financial impact (e.g. expected saving), Decimal.
    estimated_impact = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True
    )
    currency = models.CharField(max_length=3, default="USD")

    # Explainability + audit payloads.
    explanation = models.JSONField(default=dict, blank=True)
    inputs = models.JSONField(default=dict, blank=True)
    model_name = models.CharField(max_length=80, blank=True)
    model_version = models.CharField(max_length=40, blank=True)

    class Meta:
        ordering = ["-generated_at"]
        indexes = [
            models.Index(fields=["rec_type", "-generated_at"], name="rec_type_idx"),
            models.Index(fields=["cargo_requirement", "-generated_at"], name="rec_cargo_idx"),
            models.Index(fields=["route", "-generated_at"], name="rec_route_idx"),
            models.Index(fields=["origin", "-generated_at"], name="rec_origin_idx"),
            models.Index(fields=["destination_port", "-generated_at"], name="rec_dest_idx"),
            models.Index(fields=["vessel", "-generated_at"], name="rec_vessel_idx"),
            models.Index(fields=["generated_at"], name="rec_generated_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.rec_type}: {self.summary[:40]}"

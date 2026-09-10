"""
Core domain models for the Vessel platform.

Design notes:
- All monetary/financial and precise physical measurements use DecimalField
  (never floating-point DB columns) to avoid rounding error.
- Every model carries created_at / updated_at via TimeStampedModel.
- Constraints (unique, check) and indexes are declared explicitly.
- Field-level validators enforce domain ranges (e.g. IMO 7 digits,
  latitude/longitude bounds, positive dimensions).

No API endpoints are defined here (see docs/ARCHITECTURE.md — this is Layer 7
data modelling only).
"""
from __future__ import annotations

from decimal import Decimal

from django.core.validators import (
    MaxValueValidator,
    MinValueValidator,
    RegexValidator,
)
from django.db import models


# ---------------------------------------------------------------------------
# Shared base
# ---------------------------------------------------------------------------
class TimeStampedModel(models.Model):
    """Abstract base adding creation/update timestamps to every model."""

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


# ---------------------------------------------------------------------------
# Reusable validators
# ---------------------------------------------------------------------------
imo_validator = RegexValidator(
    regex=r"^\d{7}$",
    message="IMO number must be exactly 7 digits.",
)
mmsi_validator = RegexValidator(
    regex=r"^\d{9}$",
    message="MMSI must be exactly 9 digits.",
)

# Positive (> 0) constraint for physical dimensions.
POSITIVE = [MinValueValidator(Decimal("0.01"))]
NON_NEGATIVE = [MinValueValidator(Decimal("0"))]


# ---------------------------------------------------------------------------
# Commodity
# ---------------------------------------------------------------------------
class Commodity(TimeStampedModel):
    """A bulk commodity traded on the platform (primarily coal)."""

    class Category(models.TextChoices):
        COAL_THERMAL = "coal_thermal", "Coal — Thermal"
        COAL_COKING = "coal_coking", "Coal — Coking"
        IRON_ORE = "iron_ore", "Iron Ore"
        BAUXITE = "bauxite", "Bauxite"
        FERTILIZER = "fertilizer", "Fertilizer"
        GRAIN = "grain", "Grain"
        OTHER = "other", "Other"

    name = models.CharField(max_length=120, unique=True)
    category = models.CharField(
        max_length=20, choices=Category.choices, default=Category.COAL_THERMAL
    )
    # HS code (Harmonized System) — optional, up to 10 digits.
    hs_code = models.CharField(max_length=10, blank=True)
    description = models.TextField(blank=True)

    class Meta:
        verbose_name_plural = "commodities"
        ordering = ["name"]
        indexes = [
            models.Index(fields=["category"], name="commodity_category_idx"),
        ]

    def __str__(self) -> str:
        return self.name


# ---------------------------------------------------------------------------
# Port
# ---------------------------------------------------------------------------
class Port(TimeStampedModel):
    """A seaport. Destination ports are on the East Coast of India."""

    class PortType(models.TextChoices):
        SEAPORT = "seaport", "Seaport"
        RIVER = "river", "River port"
        ANCHORAGE = "anchorage", "Anchorage / lightening"
        TERMINAL = "terminal", "Private terminal"

    class Coast(models.TextChoices):
        EAST_COAST_INDIA = "east_coast_india", "East Coast (India)"
        WEST_COAST_INDIA = "west_coast_india", "West Coast (India)"
        OVERSEAS = "overseas", "Overseas (origin)"
        OTHER = "other", "Other"

    name = models.CharField(max_length=120)
    country = models.CharField(max_length=80)
    coast = models.CharField(
        max_length=16, choices=Coast.choices, default=Coast.EAST_COAST_INDIA
    )
    # UN/LOCODE — optional standard code (e.g. INPRT for Paradip).
    unlocode = models.CharField(max_length=5, blank=True)
    latitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        validators=[MinValueValidator(Decimal("-90")), MaxValueValidator(Decimal("90"))],
    )
    longitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        validators=[MinValueValidator(Decimal("-180")), MaxValueValidator(Decimal("180"))],
    )
    port_type = models.CharField(
        max_length=12, choices=PortType.choices, default=PortType.SEAPORT
    )
    # Curated, per-field provenance for this port and its constraints.
    # Each entry is {"value": ..., "source": "...", "source_date": "YYYY-MM-DD"}.
    # Values that are unavailable from official sources are recorded as
    # "UNKNOWN" rather than estimated. Populated by the seed importer.
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["name", "country"], name="uq_port_name_country"
            ),
        ]
        indexes = [
            models.Index(fields=["country"], name="port_country_idx"),
            models.Index(fields=["port_type"], name="port_type_idx"),
            models.Index(fields=["coast"], name="port_coast_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.name}, {self.country}"


# ---------------------------------------------------------------------------
# Berth
# ---------------------------------------------------------------------------
class Berth(TimeStampedModel):
    """A berth within a port, with physical and operational constraints."""

    port = models.ForeignKey(
        Port, on_delete=models.CASCADE, related_name="berths"
    )
    berth_name = models.CharField(max_length=120)

    # Physical limits (metres). Decimal for precision, not float.
    max_loa = models.DecimalField(
        "max LOA (m)", max_digits=7, decimal_places=2, validators=POSITIVE
    )
    max_beam = models.DecimalField(
        "max beam (m)", max_digits=6, decimal_places=2, validators=POSITIVE
    )
    max_draft = models.DecimalField(
        "max draft (m)", max_digits=6, decimal_places=2, validators=POSITIVE
    )

    # Cargo handling rate in tonnes per day.
    handling_rate = models.DecimalField(
        "handling rate (t/day)",
        max_digits=12,
        decimal_places=2,
        validators=NON_NEGATIVE,
    )

    # Commodities this berth can handle.
    supported_commodities = models.ManyToManyField(
        Commodity, related_name="berths", blank=True
    )

    # Free-form / structured operational constraints (tidal windows, etc.).
    special_constraints = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["port__name", "berth_name"]
        constraints = [
            models.UniqueConstraint(
                fields=["port", "berth_name"], name="uq_berth_port_name"
            ),
        ]
        indexes = [
            models.Index(fields=["port"], name="berth_port_idx"),
            models.Index(fields=["max_draft"], name="berth_max_draft_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.port.name} — {self.berth_name}"


# ---------------------------------------------------------------------------
# Vessel
# ---------------------------------------------------------------------------
class Vessel(TimeStampedModel):
    """A bulk carrier that can be chartered."""

    class VesselType(models.TextChoices):
        HANDYSIZE = "handysize", "Handysize"
        SUPRAMAX = "supramax", "Supramax"
        ULTRAMAX = "ultramax", "Ultramax"
        PANAMAX = "panamax", "Panamax"
        KAMSARMAX = "kamsarmax", "Kamsarmax"
        POST_PANAMAX = "post_panamax", "Post-Panamax"
        CAPESIZE = "capesize", "Capesize"
        OTHER = "other", "Other"

    # IMO is the stable global identifier; unique when present.
    imo = models.CharField(
        "IMO number",
        max_length=7,
        unique=True,
        validators=[imo_validator],
    )
    # MMSI can change; unique when present but optional.
    mmsi = models.CharField(
        "MMSI",
        max_length=9,
        blank=True,
        null=True,
        unique=True,
        validators=[mmsi_validator],
    )
    name = models.CharField(max_length=120)
    vessel_type = models.CharField(
        max_length=14, choices=VesselType.choices, default=VesselType.PANAMAX
    )

    # Deadweight tonnage (tonnes).
    dwt = models.DecimalField(
        "DWT (t)", max_digits=12, decimal_places=2, validators=POSITIVE
    )
    # Dimensions in metres.
    loa = models.DecimalField(
        "LOA (m)", max_digits=7, decimal_places=2, validators=POSITIVE
    )
    beam = models.DecimalField(
        "beam (m)", max_digits=6, decimal_places=2, validators=POSITIVE
    )
    draft = models.DecimalField(
        "draft (m)", max_digits=6, decimal_places=2, validators=POSITIVE
    )

    flag = models.CharField(max_length=80, blank=True)
    year_built = models.PositiveSmallIntegerField(
        blank=True,
        null=True,
        validators=[MinValueValidator(1900), MaxValueValidator(2100)],
    )
    # Service speed in knots.
    speed = models.DecimalField(
        "service speed (kn)",
        max_digits=5,
        decimal_places=2,
        blank=True,
        null=True,
        validators=POSITIVE,
    )

    class AvailabilityStatus(models.TextChoices):
        OPEN = "open", "Open / available"
        LADEN = "laden", "Laden (on voyage)"
        BALLAST = "ballast", "Ballast (repositioning)"
        FIXED = "fixed", "Fixed (committed)"
        UNKNOWN = "unknown", "Unknown"

    availability_status = models.CharField(
        max_length=8,
        choices=AvailabilityStatus.choices,
        default=AvailabilityStatus.UNKNOWN,
    )
    # Date the vessel becomes/became open for its next employment.
    open_date = models.DateField(blank=True, null=True)

    # Curated, per-field provenance for supplementary vessel particulars that do
    # not warrant dedicated columns (e.g. class society, P&I club, registered
    # owner/operator, ice class, gear/cranes, holds/hatches, TPC, grain/bale
    # capacity). Same convention as Port.metadata: each entry is
    # {"value": ..., "source": "...", "source_date": "YYYY-MM-DD"}. Values that
    # are unavailable from official sources are recorded as "UNKNOWN" rather than
    # estimated. Populated by the seed importer / ingestion.
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["name"]
        indexes = [
            models.Index(fields=["vessel_type"], name="vessel_type_idx"),
            models.Index(fields=["name"], name="vessel_name_idx"),
            models.Index(fields=["dwt"], name="vessel_dwt_idx"),
            models.Index(fields=["availability_status"], name="vessel_avail_idx"),
            models.Index(fields=["draft"], name="vessel_draft_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.name} (IMO {self.imo})"


# ---------------------------------------------------------------------------
# Origin
# ---------------------------------------------------------------------------
class Origin(TimeStampedModel):
    """A sourcing origin (country/region a commodity is exported from)."""

    name = models.CharField(max_length=120, unique=True)
    country = models.CharField(max_length=80)
    # Optional representative load port for this origin.
    load_port = models.ForeignKey(
        Port,
        on_delete=models.SET_NULL,
        related_name="origins",
        blank=True,
        null=True,
    )

    class Meta:
        ordering = ["name"]
        indexes = [
            models.Index(fields=["country"], name="origin_country_idx"),
        ]

    def __str__(self) -> str:
        return self.name


# ---------------------------------------------------------------------------
# Route
# ---------------------------------------------------------------------------
class Route(TimeStampedModel):
    """A trade lane from an origin to a destination port."""

    origin = models.ForeignKey(
        Origin, on_delete=models.CASCADE, related_name="routes"
    )
    destination_port = models.ForeignKey(
        Port, on_delete=models.CASCADE, related_name="inbound_routes"
    )
    # Great-circle / sailing distance in nautical miles.
    distance_nm = models.DecimalField(
        "distance (nm)",
        max_digits=10,
        decimal_places=2,
        blank=True,
        null=True,
        validators=NON_NEGATIVE,
    )
    # Typical laden transit time in days.
    typical_transit_days = models.DecimalField(
        "typical transit (days)",
        max_digits=6,
        decimal_places=2,
        blank=True,
        null=True,
        validators=NON_NEGATIVE,
    )

    class Meta:
        ordering = ["origin__name", "destination_port__name"]
        constraints = [
            models.UniqueConstraint(
                fields=["origin", "destination_port"],
                name="uq_route_origin_destination",
            ),
        ]
        indexes = [
            models.Index(fields=["origin"], name="route_origin_idx"),
            models.Index(fields=["destination_port"], name="route_dest_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.origin.name} \u2192 {self.destination_port.name}"


# ---------------------------------------------------------------------------
# CargoRequirement
# ---------------------------------------------------------------------------
class CargoRequirement(TimeStampedModel):
    """A demand for delivered tonnage of a commodity into a destination port."""

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        OPEN = "open", "Open"
        PLANNED = "planned", "Planned"
        FIXED = "fixed", "Fixed"
        CLOSED = "closed", "Closed"

    reference = models.CharField(max_length=64, unique=True)
    commodity = models.ForeignKey(
        Commodity, on_delete=models.PROTECT, related_name="cargo_requirements"
    )
    destination_port = models.ForeignKey(
        Port, on_delete=models.PROTECT, related_name="cargo_requirements"
    )
    # Preferred origin (optional — may be decided by optimization).
    preferred_origin = models.ForeignKey(
        Origin,
        on_delete=models.SET_NULL,
        related_name="cargo_requirements",
        blank=True,
        null=True,
    )

    quantity_tonnes = models.DecimalField(
        "quantity (t)", max_digits=12, decimal_places=2, validators=POSITIVE
    )
    # Tolerance percentage on the quantity (e.g. +/- 10%).
    tolerance_pct = models.DecimalField(
        "tolerance (%)",
        max_digits=5,
        decimal_places=2,
        default=Decimal("0"),
        validators=[MinValueValidator(Decimal("0")), MaxValueValidator(Decimal("100"))],
    )

    # Laycan window (delivery window at destination).
    laycan_start = models.DateField()
    laycan_end = models.DateField()

    # Target budget per tonne (financial → Decimal).
    target_price_per_tonne = models.DecimalField(
        "target price/t",
        max_digits=12,
        decimal_places=2,
        blank=True,
        null=True,
        validators=NON_NEGATIVE,
    )
    currency = models.CharField(max_length=3, default="USD")

    status = models.CharField(
        max_length=8, choices=Status.choices, default=Status.DRAFT
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-laycan_start"]
        constraints = [
            models.CheckConstraint(
                check=models.Q(laycan_end__gte=models.F("laycan_start")),
                name="ck_cargo_laycan_order",
            ),
        ]
        indexes = [
            models.Index(fields=["status"], name="cargo_status_idx"),
            models.Index(fields=["destination_port"], name="cargo_dest_idx"),
            models.Index(fields=["laycan_start", "laycan_end"], name="cargo_laycan_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.reference} ({self.quantity_tonnes} t {self.commodity})"


# ---------------------------------------------------------------------------
# FreightObservation
# ---------------------------------------------------------------------------
class FreightObservation(TimeStampedModel):
    """A dated freight-rate observation for a route (the forecasting target).

    Rates are per tonne and stored as Decimal (financial value).
    """

    class RateType(models.TextChoices):
        SPOT = "spot", "Spot"
        INDEX = "index", "Index"
        FIXTURE = "fixture", "Reported fixture"
        ESTIMATE = "estimate", "Estimated / proxy"

    route = models.ForeignKey(
        Route, on_delete=models.CASCADE, related_name="freight_observations"
    )
    # Optional vessel class the rate applies to.
    vessel_type = models.CharField(
        max_length=14,
        choices=Vessel.VesselType.choices,
        blank=True,
    )
    observed_on = models.DateField(db_index=True)

    rate_per_tonne = models.DecimalField(
        "rate/t", max_digits=12, decimal_places=2, validators=NON_NEGATIVE
    )
    currency = models.CharField(max_length=3, default="USD")

    rate_type = models.CharField(
        max_length=8, choices=RateType.choices, default=RateType.SPOT
    )
    # Data provenance (e.g. "baltic", "proxy", "manual"). See docs/DATA_SOURCES.md.
    source = models.CharField(max_length=80, blank=True)
    # Flags estimated/non-authoritative data (NFR-DATA-4).
    is_estimated = models.BooleanField(default=False)

    class Meta:
        ordering = ["-observed_on"]
        constraints = [
            models.UniqueConstraint(
                fields=["route", "vessel_type", "observed_on", "rate_type", "source"],
                name="uq_freight_obs_natural",
            ),
        ]
        indexes = [
            models.Index(fields=["route", "observed_on"], name="freight_route_date_idx"),
            models.Index(fields=["rate_type"], name="freight_rate_type_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.route} @ {self.rate_per_tonne}/{self.currency} on {self.observed_on}"

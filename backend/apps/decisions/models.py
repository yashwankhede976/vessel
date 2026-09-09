"""
Chartering & procurement decision models for the Vessel platform.

These model the *outputs and options* of decision support: strategies, voyage
and contract plans, candidate vessels/ports, what-if scenarios, and the records
of optimization runs and their results.

Design notes:
- CharterStrategyType is the shared enum (SPOT / SHORT_TERM / MEDIUM_TERM /
  MULTI_VOYAGE) reused across models. CharterStrategy is a persisted entity.
- CostRiskMixin centralises the required cost breakdown and risk/confidence/
  savings fields so every plan/candidate/result stores them consistently.
- All monetary values use DecimalField (no float columns). Scores are 0..1.
- Every model has audit timestamps via catalog.TimeStampedModel.

No optimization algorithms are implemented here — this is data modelling only.
The domain/optimization layers (see docs/ARCHITECTURE.md §3, §6) populate these
records; nothing in this module solves or decides.
"""
from __future__ import annotations

from decimal import Decimal

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from apps.catalog.models import TimeStampedModel

NON_NEGATIVE = [MinValueValidator(Decimal("0"))]
SCORE = [MinValueValidator(Decimal("0")), MaxValueValidator(Decimal("1"))]


class CharterStrategyType(models.TextChoices):
    """Contract/chartering strategy options."""

    SPOT = "SPOT", "Spot"
    SHORT_TERM = "SHORT_TERM", "Short-term"
    MEDIUM_TERM = "MEDIUM_TERM", "Medium-term"
    MULTI_VOYAGE = "MULTI_VOYAGE", "Multi-voyage"


class CostRiskMixin(models.Model):
    """Shared cost breakdown, risk, confidence, and savings fields.

    All monetary values are Decimal and expressed in `currency`. Costs are
    totals for the plan/candidate/result unless noted otherwise.
    """

    currency = models.CharField(max_length=3, default="USD")

    # Cost breakdown (financial → Decimal).
    expected_cost = models.DecimalField(
        max_digits=16, decimal_places=2, null=True, blank=True, validators=NON_NEGATIVE
    )
    freight_cost = models.DecimalField(
        max_digits=16, decimal_places=2, null=True, blank=True, validators=NON_NEGATIVE
    )
    port_cost = models.DecimalField(
        max_digits=16, decimal_places=2, null=True, blank=True, validators=NON_NEGATIVE
    )
    bunker_cost = models.DecimalField(
        max_digits=16, decimal_places=2, null=True, blank=True, validators=NON_NEGATIVE
    )
    demurrage_estimate = models.DecimalField(
        max_digits=16, decimal_places=2, null=True, blank=True, validators=NON_NEGATIVE
    )

    # Derived value vs a baseline (may be negative if worse than baseline).
    expected_savings = models.DecimalField(
        max_digits=16, decimal_places=2, null=True, blank=True
    )

    # Normalized risk 0..1 and confidence 0..1.
    risk_score = models.DecimalField(
        max_digits=4, decimal_places=3, null=True, blank=True, validators=SCORE
    )
    confidence = models.DecimalField(
        max_digits=4, decimal_places=3, null=True, blank=True, validators=SCORE
    )

    class Meta:
        abstract = True


# ===========================================================================
# CharterStrategy
# ===========================================================================
class CharterStrategy(TimeStampedModel):
    """A named chartering strategy for meeting a cargo requirement.

    Represents the chosen/considered approach (e.g. cover a requirement via a
    multi-voyage arrangement) and its top-line economics.
    """

    cargo_requirement = models.ForeignKey(
        "catalog.CargoRequirement",
        on_delete=models.CASCADE,
        related_name="charter_strategies",
    )
    strategy_type = models.CharField(
        max_length=12, choices=CharterStrategyType.choices
    )
    name = models.CharField(max_length=120, blank=True)
    description = models.TextField(blank=True)
    is_recommended = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["cargo_requirement"], name="strategy_cargo_idx"),
            models.Index(fields=["strategy_type"], name="strategy_type_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.get_strategy_type_display()} for {self.cargo_requirement_id}"


# ===========================================================================
# VoyagePlan
# ===========================================================================
class VoyagePlan(TimeStampedModel, CostRiskMixin):
    """A planned single voyage (origin -> destination) with its economics."""

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PROPOSED = "proposed", "Proposed"
        SELECTED = "selected", "Selected"
        REJECTED = "rejected", "Rejected"

    strategy = models.ForeignKey(
        CharterStrategy,
        on_delete=models.CASCADE,
        related_name="voyage_plans",
        null=True,
        blank=True,
    )
    cargo_requirement = models.ForeignKey(
        "catalog.CargoRequirement",
        on_delete=models.CASCADE,
        related_name="voyage_plans",
    )
    route = models.ForeignKey(
        "catalog.Route", on_delete=models.PROTECT, related_name="voyage_plans"
    )
    vessel = models.ForeignKey(
        "catalog.Vessel",
        on_delete=models.SET_NULL,
        related_name="voyage_plans",
        null=True,
        blank=True,
    )

    quantity_tonnes = models.DecimalField(
        "quantity (t)", max_digits=12, decimal_places=2, validators=NON_NEGATIVE
    )
    # Planned laycan window for this voyage.
    laycan_start = models.DateField(null=True, blank=True)
    laycan_end = models.DateField(null=True, blank=True)

    status = models.CharField(
        max_length=8, choices=Status.choices, default=Status.DRAFT
    )

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(
                check=(
                    models.Q(laycan_start__isnull=True)
                    | models.Q(laycan_end__isnull=True)
                    | models.Q(laycan_end__gte=models.F("laycan_start"))
                ),
                name="ck_voyageplan_laycan_order",
            ),
        ]
        indexes = [
            models.Index(fields=["cargo_requirement"], name="voyage_cargo_idx"),
            models.Index(fields=["route"], name="voyage_route_idx"),
            models.Index(fields=["vessel"], name="voyage_vessel_idx"),
            models.Index(fields=["status"], name="voyage_status_idx"),
        ]

    def __str__(self) -> str:
        return f"VoyagePlan {self.pk} ({self.route_id})"


# ===========================================================================
# ContractPlan + ContractVoyage
# ===========================================================================
class ContractPlan(TimeStampedModel, CostRiskMixin):
    """A contract-level plan covering one or more voyages under a strategy."""

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PROPOSED = "proposed", "Proposed"
        SELECTED = "selected", "Selected"
        REJECTED = "rejected", "Rejected"

    strategy = models.ForeignKey(
        CharterStrategy,
        on_delete=models.CASCADE,
        related_name="contract_plans",
        null=True,
        blank=True,
    )
    cargo_requirement = models.ForeignKey(
        "catalog.CargoRequirement",
        on_delete=models.CASCADE,
        related_name="contract_plans",
    )
    strategy_type = models.CharField(
        max_length=12, choices=CharterStrategyType.choices
    )

    # Coverage period for the contract.
    period_start = models.DateField(null=True, blank=True)
    period_end = models.DateField(null=True, blank=True)
    total_quantity_tonnes = models.DecimalField(
        "total quantity (t)", max_digits=14, decimal_places=2, validators=NON_NEGATIVE
    )
    number_of_voyages = models.PositiveSmallIntegerField(default=1)

    status = models.CharField(
        max_length=8, choices=Status.choices, default=Status.DRAFT
    )

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(
                check=(
                    models.Q(period_start__isnull=True)
                    | models.Q(period_end__isnull=True)
                    | models.Q(period_end__gte=models.F("period_start"))
                ),
                name="ck_contractplan_period_order",
            ),
        ]
        indexes = [
            models.Index(fields=["cargo_requirement"], name="contract_cargo_idx"),
            models.Index(fields=["strategy_type"], name="contract_strategy_idx"),
            models.Index(fields=["status"], name="contract_status_idx"),
        ]

    def __str__(self) -> str:
        return f"ContractPlan {self.pk} ({self.strategy_type})"


class ContractVoyage(TimeStampedModel):
    """A voyage that belongs to a contract plan (through/ordering model)."""

    contract_plan = models.ForeignKey(
        ContractPlan, on_delete=models.CASCADE, related_name="contract_voyages"
    )
    voyage_plan = models.ForeignKey(
        VoyagePlan, on_delete=models.CASCADE, related_name="contract_voyages"
    )
    sequence = models.PositiveSmallIntegerField(
        default=1, help_text="Order of this voyage within the contract."
    )

    class Meta:
        ordering = ["contract_plan", "sequence"]
        constraints = [
            models.UniqueConstraint(
                fields=["contract_plan", "voyage_plan"],
                name="uq_contractvoyage_plan_voyage",
            ),
            models.UniqueConstraint(
                fields=["contract_plan", "sequence"],
                name="uq_contractvoyage_sequence",
            ),
        ]
        indexes = [
            models.Index(fields=["contract_plan"], name="cv_contract_idx"),
            models.Index(fields=["voyage_plan"], name="cv_voyage_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.contract_plan_id} #{self.sequence}"


# ===========================================================================
# Candidates
# ===========================================================================
class VesselCandidate(TimeStampedModel, CostRiskMixin):
    """A candidate vessel evaluated for a voyage/requirement, with economics."""

    cargo_requirement = models.ForeignKey(
        "catalog.CargoRequirement",
        on_delete=models.CASCADE,
        related_name="vessel_candidates",
    )
    vessel = models.ForeignKey(
        "catalog.Vessel", on_delete=models.CASCADE, related_name="candidacies"
    )
    voyage_plan = models.ForeignKey(
        VoyagePlan,
        on_delete=models.CASCADE,
        related_name="vessel_candidates",
        null=True,
        blank=True,
    )

    # Ranking score 0..1 (higher = more suitable) and rank position.
    suitability_score = models.DecimalField(
        max_digits=4, decimal_places=3, null=True, blank=True, validators=SCORE
    )
    rank = models.PositiveSmallIntegerField(null=True, blank=True)
    is_compatible = models.BooleanField(default=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["rank", "-suitability_score"]
        constraints = [
            models.UniqueConstraint(
                fields=["cargo_requirement", "vessel", "voyage_plan"],
                name="uq_vesselcandidate_natural",
            ),
        ]
        indexes = [
            models.Index(fields=["cargo_requirement"], name="vcand_cargo_idx"),
            models.Index(fields=["vessel"], name="vcand_vessel_idx"),
            models.Index(fields=["voyage_plan"], name="vcand_voyage_idx"),
        ]

    def __str__(self) -> str:
        return f"VesselCandidate {self.vessel_id} for {self.cargo_requirement_id}"


class PortCandidate(TimeStampedModel, CostRiskMixin):
    """A candidate destination port evaluated for a requirement, with economics."""

    cargo_requirement = models.ForeignKey(
        "catalog.CargoRequirement",
        on_delete=models.CASCADE,
        related_name="port_candidates",
    )
    port = models.ForeignKey(
        "catalog.Port", on_delete=models.CASCADE, related_name="candidacies"
    )
    # Whether this is the primary/originally-intended port.
    is_primary = models.BooleanField(default=False)

    suitability_score = models.DecimalField(
        max_digits=4, decimal_places=3, null=True, blank=True, validators=SCORE
    )
    rank = models.PositiveSmallIntegerField(null=True, blank=True)
    is_compatible = models.BooleanField(default=True)
    # Landed-cost delta vs the primary port (may be negative if cheaper).
    landed_cost_delta = models.DecimalField(
        max_digits=16, decimal_places=2, null=True, blank=True
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["rank", "-suitability_score"]
        constraints = [
            models.UniqueConstraint(
                fields=["cargo_requirement", "port"],
                name="uq_portcandidate_natural",
            ),
        ]
        indexes = [
            models.Index(fields=["cargo_requirement"], name="pcand_cargo_idx"),
            models.Index(fields=["port"], name="pcand_port_idx"),
        ]

    def __str__(self) -> str:
        return f"PortCandidate {self.port_id} for {self.cargo_requirement_id}"


# ===========================================================================
# Scenario + Optimization run/result
# ===========================================================================
class Scenario(TimeStampedModel):
    """A what-if scenario: a set of parameter overrides against a base case."""

    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    cargo_requirement = models.ForeignKey(
        "catalog.CargoRequirement",
        on_delete=models.CASCADE,
        related_name="scenarios",
        null=True,
        blank=True,
    )
    is_baseline = models.BooleanField(default=False)
    # Parameter overrides (e.g. bunker +10%, congestion worse). JSON, no logic here.
    parameters = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["cargo_requirement"], name="scenario_cargo_idx"),
            models.Index(fields=["is_baseline"], name="scenario_baseline_idx"),
        ]

    def __str__(self) -> str:
        return self.name


class OptimizationRun(TimeStampedModel):
    """A record of an optimization execution (metadata only; no solver here)."""

    class RunType(models.TextChoices):
        SOURCING = "sourcing", "Multi-origin sourcing"
        LAYCAN = "laycan", "Laycan optimization"
        CONTRACT = "contract", "Contract-type selection"
        IDLE_VESSEL = "idle_vessel", "Idle-vessel employment"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        RUNNING = "running", "Running"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"

    run_type = models.CharField(max_length=12, choices=RunType.choices)
    cargo_requirement = models.ForeignKey(
        "catalog.CargoRequirement",
        on_delete=models.CASCADE,
        related_name="optimization_runs",
        null=True,
        blank=True,
    )
    scenario = models.ForeignKey(
        Scenario,
        on_delete=models.SET_NULL,
        related_name="optimization_runs",
        null=True,
        blank=True,
    )

    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.PENDING
    )
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    # Solver/config provenance and inputs snapshot (audit).
    solver = models.CharField(max_length=80, blank=True)
    solver_version = models.CharField(max_length=40, blank=True)
    parameters = models.JSONField(default=dict, blank=True)
    error_message = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["run_type", "-created_at"], name="optrun_type_idx"),
            models.Index(fields=["cargo_requirement"], name="optrun_cargo_idx"),
            models.Index(fields=["scenario"], name="optrun_scenario_idx"),
            models.Index(fields=["status"], name="optrun_status_idx"),
        ]

    def __str__(self) -> str:
        return f"OptimizationRun {self.pk} ({self.run_type}, {self.status})"


class OptimizationResult(TimeStampedModel, CostRiskMixin):
    """A result produced by an optimization run, with economics and rationale."""

    run = models.ForeignKey(
        OptimizationRun, on_delete=models.CASCADE, related_name="results"
    )
    # Optional links to the concrete plan/strategy this result recommends.
    strategy = models.ForeignKey(
        CharterStrategy,
        on_delete=models.SET_NULL,
        related_name="optimization_results",
        null=True,
        blank=True,
    )
    contract_plan = models.ForeignKey(
        ContractPlan,
        on_delete=models.SET_NULL,
        related_name="optimization_results",
        null=True,
        blank=True,
    )

    rank = models.PositiveSmallIntegerField(default=1)
    is_optimal = models.BooleanField(default=False)
    # Objective value the solver reported (financial → Decimal).
    objective_value = models.DecimalField(
        max_digits=18, decimal_places=2, null=True, blank=True
    )
    # Solver rationale: binding constraints, chosen variables, explanation.
    detail = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["run", "rank"]
        constraints = [
            models.UniqueConstraint(
                fields=["run", "rank"], name="uq_optresult_run_rank"
            ),
        ]
        indexes = [
            models.Index(fields=["run", "rank"], name="optresult_run_rank_idx"),
            models.Index(fields=["is_optimal"], name="optresult_optimal_idx"),
        ]

    def __str__(self) -> str:
        return f"OptimizationResult {self.pk} (run {self.run_id}, rank {self.rank})"

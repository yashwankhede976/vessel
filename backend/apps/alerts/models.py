"""Alert and Notification models.

An Alert is a decision-relevant event detected by the alert-generation service
(freight moves, congestion, cyclone/marine warnings, vessel scarcity, ETA delay,
port incompatibility, unusual market pressure). A Notification is a delivery of
an alert through a channel (dashboard / database now; email/push later).

Both are audit records with explicit provenance: what triggered them, the value
vs the threshold, and a lifecycle status. No secrets are stored.
"""
from __future__ import annotations

from django.db import models

from apps.catalog.models import TimeStampedModel


class AlertType(models.TextChoices):
    FREIGHT_INCREASE = "freight_increase", "Freight increase"
    FREIGHT_DECREASE = "freight_decrease", "Freight decrease"
    FREIGHT_VOLATILITY = "freight_volatility", "Freight volatility"
    CONGESTION_INCREASE = "congestion_increase", "Congestion increase"
    CYCLONE_WARNING = "cyclone_warning", "Cyclone warning"
    MARINE_WARNING = "marine_warning", "Marine warning"
    VESSEL_SCARCITY = "vessel_scarcity", "Vessel scarcity"
    ETA_DELAY = "eta_delay", "ETA delay"
    PORT_INCOMPATIBILITY = "port_incompatibility", "Port incompatibility"
    UNUSUAL_MARKET_PRESSURE = "unusual_market_pressure", "Unusual market pressure"


class AlertSeverity(models.TextChoices):
    INFO = "info", "Info"
    LOW = "low", "Low"
    MEDIUM = "medium", "Medium"
    HIGH = "high", "High"
    CRITICAL = "critical", "Critical"


class AlertStatus(models.TextChoices):
    NEW = "new", "New"
    ACKNOWLEDGED = "acknowledged", "Acknowledged"
    RESOLVED = "resolved", "Resolved"


class Alert(TimeStampedModel):
    """A detected, decision-relevant condition with an explainable trigger."""

    alert_type = models.CharField(max_length=32, choices=AlertType.choices, db_index=True)
    severity = models.CharField(
        max_length=8, choices=AlertSeverity.choices, default=AlertSeverity.MEDIUM,
        db_index=True,
    )
    # When the condition was detected (distinct from created_at write time).
    timestamp = models.DateTimeField()

    # A free-text description of the entity the alert concerns (e.g.
    # "Australia -> Paradip (capesize)" or "Paradip"). Optional structured FKs
    # let the alert attach to concrete records when known.
    entity = models.CharField(max_length=200, blank=True)
    route = models.ForeignKey(
        "catalog.Route", on_delete=models.SET_NULL, related_name="alerts",
        null=True, blank=True,
    )
    port = models.ForeignKey(
        "catalog.Port", on_delete=models.SET_NULL, related_name="alerts",
        null=True, blank=True,
    )
    vessel = models.ForeignKey(
        "catalog.Vessel", on_delete=models.SET_NULL, related_name="alerts",
        null=True, blank=True,
    )

    # The measured value that fired the alert and the threshold it crossed.
    trigger_value = models.DecimalField(
        max_digits=18, decimal_places=4, null=True, blank=True
    )
    threshold = models.DecimalField(
        max_digits=18, decimal_places=4, null=True, blank=True
    )

    message = models.CharField(max_length=500)
    recommended_action = models.CharField(max_length=500, blank=True)

    status = models.CharField(
        max_length=12, choices=AlertStatus.choices, default=AlertStatus.NEW,
        db_index=True,
    )
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    # Dedup fingerprint: a stable key for "the same alert condition" so repeated
    # detection updates rather than duplicates an open alert.
    dedup_key = models.CharField(max_length=200, blank=True, db_index=True)

    # Explainability payload (drivers, inputs) — never secrets.
    context = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-timestamp"]
        indexes = [
            models.Index(fields=["alert_type", "-timestamp"], name="alert_type_ts_idx"),
            models.Index(fields=["status", "-timestamp"], name="alert_status_ts_idx"),
            models.Index(fields=["severity", "-timestamp"], name="alert_sev_ts_idx"),
            models.Index(fields=["dedup_key"], name="alert_dedup_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.alert_type} [{self.severity}] {self.status}: {self.message[:40]}"


class Notification(TimeStampedModel):
    """A delivery of an alert through a channel.

    Channels available now: dashboard, database. The Notifier architecture (see
    services/notifications.py) is pluggable so email/push channels can be added
    later without schema changes.
    """

    class Channel(models.TextChoices):
        DASHBOARD = "dashboard", "Dashboard"
        DATABASE = "database", "Database"
        EMAIL = "email", "Email"       # reserved for future use
        PUSH = "push", "Push"          # reserved for future use

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        SENT = "sent", "Sent"
        FAILED = "failed", "Failed"

    alert = models.ForeignKey(
        Alert, on_delete=models.CASCADE, related_name="notifications"
    )
    channel = models.CharField(max_length=12, choices=Channel.choices)
    status = models.CharField(
        max_length=8, choices=Status.choices, default=Status.PENDING
    )
    sent_at = models.DateTimeField(null=True, blank=True)
    detail = models.CharField(max_length=500, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["alert", "channel"], name="notif_alert_chan_idx"),
            models.Index(fields=["status", "-created_at"], name="notif_status_idx"),
        ]

    def __str__(self) -> str:
        return f"Notification[{self.channel}] alert={self.alert_id} {self.status}"

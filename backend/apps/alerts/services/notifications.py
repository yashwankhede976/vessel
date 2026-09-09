"""Notification foundation (pluggable, no paid services).

An alert, once created, is delivered through one or more Notifiers. Two channels
are implemented now:

    DashboardNotifier  — a no-op delivery that simply marks the alert available
                         to the dashboard (the dashboard reads Alert rows via the
                         API; this records that a dashboard notification "fired").
    DatabaseNotifier   — persists a Notification row (the durable in-app inbox).

The architecture is deliberately pluggable: adding email or push later means
writing another Notifier subclass and registering it in DEFAULT_NOTIFIERS (or
passing it to dispatch). No external/paid notification service is required.
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Iterable, Optional

from django.utils import timezone

from apps.alerts.models import Alert, Notification

logger = logging.getLogger("vessel.alerts")


class Notifier(ABC):
    """Delivers an alert through one channel. Must not raise on delivery
    failure — it records a failed Notification and returns it instead, so one
    channel failing never blocks the others."""

    channel: str = ""

    @abstractmethod
    def notify(self, alert: Alert) -> Notification:
        """Deliver the alert; return the Notification record."""


class DatabaseNotifier(Notifier):
    """Persist a Notification row (the durable in-app inbox)."""

    channel = Notification.Channel.DATABASE

    def notify(self, alert: Alert) -> Notification:
        return Notification.objects.create(
            alert=alert,
            channel=self.channel,
            status=Notification.Status.SENT,
            sent_at=timezone.now(),
            detail="Persisted to the in-app notification inbox.",
        )


class DashboardNotifier(Notifier):
    """Record that the alert is surfaced on the dashboard.

    The dashboard consumes Alert rows through the API; this notifier simply logs
    the delivery as a Notification so there is an audit trail per channel.
    """

    channel = Notification.Channel.DASHBOARD

    def notify(self, alert: Alert) -> Notification:
        return Notification.objects.create(
            alert=alert,
            channel=self.channel,
            status=Notification.Status.SENT,
            sent_at=timezone.now(),
            detail="Surfaced on the dashboard alert feed.",
        )


# Channels enabled by default. Email/push notifiers can be appended here later.
DEFAULT_NOTIFIERS: list[Notifier] = [DashboardNotifier(), DatabaseNotifier()]


def dispatch(
    alert: Alert, notifiers: Optional[Iterable[Notifier]] = None
) -> list[Notification]:
    """Deliver an alert through the given notifiers (default: dashboard + db).

    A failure in one channel is recorded as a failed Notification and does not
    prevent the others from running.
    """
    notifiers = list(notifiers) if notifiers is not None else DEFAULT_NOTIFIERS
    results: list[Notification] = []
    for notifier in notifiers:
        try:
            results.append(notifier.notify(alert))
        except Exception as exc:  # never let one channel break delivery
            logger.exception(
                "alert.notify failed channel=%s alert=%s", notifier.channel, alert.pk
            )
            results.append(
                Notification.objects.create(
                    alert=alert,
                    channel=notifier.channel or "unknown",
                    status=Notification.Status.FAILED,
                    detail=str(exc)[:500],
                )
            )
    return results

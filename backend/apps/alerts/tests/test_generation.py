"""Tests for the alert-generation service + notifications."""
from django.test import TestCase

from apps.alerts.models import Alert, AlertStatus, AlertType, Notification
from apps.alerts.services import generation as gen
from apps.alerts.services.notifications import (
    DatabaseNotifier,
    Notifier,
    dispatch,
)


class DetectorTests(TestCase):
    def test_freight_increase_fires_above_threshold(self):
        a = gen.detect_freight_move(entity="AUS->Paradip", current_rate=25, reference_rate=22)
        self.assertIsNotNone(a)
        self.assertEqual(a.alert_type, AlertType.FREIGHT_INCREASE)

    def test_freight_decrease_fires(self):
        a = gen.detect_freight_move(entity="AUS->Paradip", current_rate=20, reference_rate=22)
        self.assertEqual(a.alert_type, AlertType.FREIGHT_DECREASE)

    def test_freight_move_below_threshold_no_alert(self):
        a = gen.detect_freight_move(entity="lane", current_rate=22.1, reference_rate=22)
        self.assertIsNone(a)

    def test_volatility_alert(self):
        self.assertIsNotNone(gen.detect_freight_volatility(entity="lane", volatility=0.7))
        self.assertIsNone(gen.detect_freight_volatility(entity="lane", volatility=0.2))

    def test_congestion_alert_severity(self):
        a = gen.detect_congestion(entity="Paradip", congestion_score=80)
        self.assertEqual(a.severity, "critical")
        b = gen.detect_congestion(entity="Vizag", congestion_score=60)
        self.assertEqual(b.severity, "high")
        self.assertIsNone(gen.detect_congestion(entity="Kolkata", congestion_score=30))

    def test_marine_and_cyclone_warnings(self):
        m = gen.detect_marine_warning(entity="BoB", severity_level="high")
        self.assertEqual(m.alert_type, AlertType.MARINE_WARNING)
        c = gen.detect_marine_warning(entity="BoB", severity_level="severe", cyclone=True)
        self.assertEqual(c.alert_type, AlertType.CYCLONE_WARNING)
        self.assertIsNone(gen.detect_marine_warning(entity="BoB", severity_level="low"))

    def test_vessel_scarcity(self):
        self.assertIsNotNone(gen.detect_vessel_scarcity(entity="capesize", availability=0.1))
        self.assertIsNone(gen.detect_vessel_scarcity(entity="capesize", availability=0.8))

    def test_eta_delay(self):
        self.assertIsNotNone(gen.detect_eta_delay(entity="MV X", delay_probability=0.7))
        self.assertIsNone(gen.detect_eta_delay(entity="MV X", delay_probability=0.2))

    def test_port_incompatibility(self):
        a = gen.detect_port_incompatibility(entity="Paradip", reason="draft exceeds limit")
        self.assertEqual(a.alert_type, AlertType.PORT_INCOMPATIBILITY)

    def test_unusual_market_pressure_both_ends(self):
        tight = gen.detect_unusual_market_pressure(entity="mkt", market_pressure_index=80)
        self.assertEqual(tight.severity, "high")
        weak = gen.detect_unusual_market_pressure(entity="mkt", market_pressure_index=20)
        self.assertIsNotNone(weak)
        self.assertIsNone(gen.detect_unusual_market_pressure(entity="mkt", market_pressure_index=50))


class DedupTests(TestCase):
    def test_same_condition_updates_not_duplicates(self):
        gen.detect_congestion(entity="Paradip", congestion_score=80)
        gen.detect_congestion(entity="Paradip", congestion_score=85)
        self.assertEqual(Alert.objects.filter(alert_type=AlertType.CONGESTION_INCREASE).count(), 1)
        alert = Alert.objects.get(alert_type=AlertType.CONGESTION_INCREASE)
        self.assertEqual(alert.trigger_value, 85)

    def test_resolved_alert_does_not_block_new_one(self):
        a = gen.detect_congestion(entity="Paradip", congestion_score=80)
        a.status = AlertStatus.RESOLVED
        a.save()
        gen.detect_congestion(entity="Paradip", congestion_score=82)
        self.assertEqual(Alert.objects.filter(alert_type=AlertType.CONGESTION_INCREASE).count(), 2)


class NotificationTests(TestCase):
    def test_alert_creation_emits_notifications(self):
        a = gen.detect_congestion(entity="Paradip", congestion_score=80)
        # DEFAULT_NOTIFIERS = dashboard + database.
        self.assertEqual(a.notifications.count(), 2)
        channels = set(a.notifications.values_list("channel", flat=True))
        self.assertEqual(channels, {"dashboard", "database"})

    def test_database_notifier_persists(self):
        a = gen.raise_alert(
            alert_type=AlertType.ETA_DELAY, severity="medium",
            message="x", notify=False,
        )
        n = DatabaseNotifier().notify(a)
        self.assertEqual(n.status, Notification.Status.SENT)

    def test_dispatch_isolates_channel_failure(self):
        class BoomNotifier(Notifier):
            channel = "dashboard"

            def notify(self, alert):
                raise RuntimeError("channel down")

        a = gen.raise_alert(
            alert_type=AlertType.ETA_DELAY, severity="medium", message="x", notify=False
        )
        results = dispatch(a, notifiers=[BoomNotifier(), DatabaseNotifier()])
        statuses = {r.channel: r.status for r in results}
        self.assertEqual(statuses["dashboard"], Notification.Status.FAILED)
        self.assertEqual(statuses["database"], Notification.Status.SENT)

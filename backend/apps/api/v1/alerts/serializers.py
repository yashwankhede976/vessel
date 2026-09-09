"""Serializers for the alerts endpoints (v1)."""
from rest_framework import serializers

from apps.alerts.models import Alert, Notification


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ["id", "channel", "status", "sent_at", "detail", "created_at"]
        read_only_fields = fields


class AlertSerializer(serializers.ModelSerializer):
    notifications = NotificationSerializer(many=True, read_only=True)

    class Meta:
        model = Alert
        fields = [
            "id", "alert_type", "severity", "timestamp", "entity",
            "route", "port", "vessel", "trigger_value", "threshold",
            "message", "recommended_action", "status",
            "acknowledged_at", "resolved_at", "context", "notifications",
            "created_at", "updated_at",
        ]
        read_only_fields = fields

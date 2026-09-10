"""Serializers for the AI chat endpoint."""
from __future__ import annotations

from rest_framework import serializers

MAX_MESSAGE_LEN = 2000


class ChatRequestSerializer(serializers.Serializer):
    """Validated chat request. `context` is a free-form object with optional
    page context (origin, destination, commodity, cargo_quantity, ...)."""

    message = serializers.CharField(
        max_length=MAX_MESSAGE_LEN, trim_whitespace=True, allow_blank=False
    )
    conversation_id = serializers.CharField(
        max_length=64, required=False, allow_blank=True
    )
    context = serializers.DictField(required=False)

    def validate_message(self, value: str) -> str:
        if not value.strip():
            raise serializers.ValidationError("message cannot be empty.")
        return value

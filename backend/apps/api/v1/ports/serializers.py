"""Serializers for the ports domain (ports & berths).

These return clean, frontend-ready JSON and carry explicit validation for the
key berth dimensions (LOA, beam, draft) and handling rate. Validation is
declared here (in addition to model-level validators) so the API contract is
self-documenting and independently testable.

No vessel-compatibility logic lives here — these serializers only shape and
validate port/berth data.
"""
from __future__ import annotations

from decimal import Decimal

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.catalog.models import Berth, Commodity, Port

# Sanity upper bounds (metres / tonnes-per-day). These guard against obviously
# invalid data while staying well above any real-world vessel/berth value.
MAX_LOA_M = Decimal("500")
MAX_BEAM_M = Decimal("100")
MAX_DRAFT_M = Decimal("40")
MAX_HANDLING_RATE = Decimal("1000000")


class CommoditySlugField(serializers.SlugRelatedField):
    """Represent supported commodities by name (clean JSON, not opaque ids)."""


class BerthSerializer(serializers.ModelSerializer):
    """A berth with its physical/operational constraints."""

    port_id = serializers.PrimaryKeyRelatedField(source="port", read_only=True)
    port_name = serializers.CharField(source="port.name", read_only=True)
    supported_commodities = serializers.SlugRelatedField(
        many=True, slug_field="name", queryset=Commodity.objects.all(), required=False
    )

    class Meta:
        model = Berth
        fields = [
            "id",
            "port_id",
            "port_name",
            "berth_name",
            "max_loa",
            "max_beam",
            "max_draft",
            "handling_rate",
            "supported_commodities",
            "special_constraints",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    # --- Field validation for the key dimensions ---
    def validate_max_loa(self, value: Decimal) -> Decimal:
        return self._positive_within("max_loa", value, MAX_LOA_M)

    def validate_max_beam(self, value: Decimal) -> Decimal:
        return self._positive_within("max_beam", value, MAX_BEAM_M)

    def validate_max_draft(self, value: Decimal) -> Decimal:
        return self._positive_within("max_draft", value, MAX_DRAFT_M)

    def validate_handling_rate(self, value: Decimal) -> Decimal:
        # Handling rate may be zero (unknown) but not negative or absurd.
        if value < 0:
            raise serializers.ValidationError("Handling rate cannot be negative.")
        if value > MAX_HANDLING_RATE:
            raise serializers.ValidationError(
                f"Handling rate exceeds the maximum plausible value ({MAX_HANDLING_RATE})."
            )
        return value

    @staticmethod
    def _positive_within(field: str, value: Decimal, maximum: Decimal) -> Decimal:
        if value <= 0:
            raise serializers.ValidationError(f"{field} must be greater than 0.")
        if value > maximum:
            raise serializers.ValidationError(
                f"{field} exceeds the maximum plausible value ({maximum} m)."
            )
        return value


class PortSerializer(serializers.ModelSerializer):
    """List/summary representation of a port."""

    coast_display = serializers.CharField(source="get_coast_display", read_only=True)
    port_type_display = serializers.CharField(
        source="get_port_type_display", read_only=True
    )
    berth_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Port
        fields = [
            "id",
            "name",
            "country",
            "coast",
            "coast_display",
            "unlocode",
            "latitude",
            "longitude",
            "port_type",
            "port_type_display",
            "berth_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class PortDetailSerializer(PortSerializer):
    """Detail representation of a port, including its berths and source metadata."""

    berths = BerthSerializer(many=True, read_only=True)

    class Meta(PortSerializer.Meta):
        fields = PortSerializer.Meta.fields + ["metadata", "berths"]
        read_only_fields = fields


class PortConstraintsSerializer(serializers.ModelSerializer):
    """The physical/operational constraints of a port, derived from its berths.

    Reports the most permissive berth limits (max over berths) plus the union
    of supported commodities — a compact 'what can call here' summary. No
    vessel-compatibility decision is made; this only exposes the constraints.
    """

    max_loa = serializers.SerializerMethodField()
    max_beam = serializers.SerializerMethodField()
    max_draft = serializers.SerializerMethodField()
    max_handling_rate = serializers.SerializerMethodField()
    supported_commodities = serializers.SerializerMethodField()
    berth_count = serializers.IntegerField(source="berths.count", read_only=True)

    class Meta:
        model = Port
        fields = [
            "id",
            "name",
            "coast",
            "berth_count",
            "max_loa",
            "max_beam",
            "max_draft",
            "max_handling_rate",
            "supported_commodities",
        ]
        read_only_fields = fields

    def _agg(self, port: Port, field: str):
        values = [getattr(b, field) for b in port.berths.all() if getattr(b, field) is not None]
        return max(values) if values else None

    @extend_schema_field(OpenApiTypes.DECIMAL)
    def get_max_loa(self, port: Port):
        return self._agg(port, "max_loa")

    @extend_schema_field(OpenApiTypes.DECIMAL)
    def get_max_beam(self, port: Port):
        return self._agg(port, "max_beam")

    @extend_schema_field(OpenApiTypes.DECIMAL)
    def get_max_draft(self, port: Port):
        return self._agg(port, "max_draft")

    @extend_schema_field(OpenApiTypes.DECIMAL)
    def get_max_handling_rate(self, port: Port):
        return self._agg(port, "handling_rate")

    def get_supported_commodities(self, port: Port) -> list[str]:
        names: set[str] = set()
        for berth in port.berths.all():
            names.update(c.name for c in berth.supported_commodities.all())
        return sorted(names)

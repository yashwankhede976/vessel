"""Filters for the vessels domain.

Supports filtering by vessel type, DWT range, draft range, availability, and
current position (bounding box over each vessel's latest AIS position).

The current-position filter relies on annotations (`latest_lat`, `latest_lon`)
added by the viewset's queryset, so filtering happens in the database.
"""
from __future__ import annotations

import django_filters as filters

from apps.catalog.models import Vessel


class VesselFilter(filters.FilterSet):
    # Type.
    vessel_type = filters.ChoiceFilter(choices=Vessel.VesselType.choices)

    # DWT range (tonnes).
    dwt_min = filters.NumberFilter(field_name="dwt", lookup_expr="gte")
    dwt_max = filters.NumberFilter(field_name="dwt", lookup_expr="lte")

    # Draft range (metres).
    draft_min = filters.NumberFilter(field_name="draft", lookup_expr="gte")
    draft_max = filters.NumberFilter(field_name="draft", lookup_expr="lte")

    # Availability.
    availability_status = filters.ChoiceFilter(
        choices=Vessel.AvailabilityStatus.choices
    )
    open_before = filters.DateFilter(field_name="open_date", lookup_expr="lte")
    open_after = filters.DateFilter(field_name="open_date", lookup_expr="gte")

    # Current position bounding box (over the latest AIS position).
    min_lat = filters.NumberFilter(field_name="latest_lat", lookup_expr="gte")
    max_lat = filters.NumberFilter(field_name="latest_lat", lookup_expr="lte")
    min_lon = filters.NumberFilter(field_name="latest_lon", lookup_expr="gte")
    max_lon = filters.NumberFilter(field_name="latest_lon", lookup_expr="lte")

    class Meta:
        model = Vessel
        fields = [
            "vessel_type",
            "dwt_min",
            "dwt_max",
            "draft_min",
            "draft_max",
            "availability_status",
            "open_before",
            "open_after",
            "min_lat",
            "max_lat",
            "min_lon",
            "max_lon",
        ]

"""Filters for the ports domain."""
from __future__ import annotations

import django_filters as filters

from apps.catalog.models import Port


class PortFilter(filters.FilterSet):
    """Filter ports by coast, port type, country, and supported commodity.

    - ?coast=east_coast_india
    - ?commodity=<name>  -> ports having a berth that supports the commodity
    """

    coast = filters.ChoiceFilter(choices=Port.Coast.choices)
    port_type = filters.ChoiceFilter(choices=Port.PortType.choices)
    country = filters.CharFilter(field_name="country", lookup_expr="iexact")
    commodity = filters.CharFilter(method="filter_commodity", label="Supported commodity name")

    class Meta:
        model = Port
        fields = ["coast", "port_type", "country", "commodity"]

    def filter_commodity(self, queryset, name, value):
        return queryset.filter(
            berths__supported_commodities__name__iexact=value
        ).distinct()

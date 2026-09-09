"""Standard pagination for the Vessel API.

Emits a predictable structure that the response renderer folds into the
consistent envelope:

    {
      "success": true,
      "data": [ ... ],
      "pagination": {
        "count": 123,
        "page": 2,
        "page_size": 25,
        "num_pages": 5,
        "next": "…?page=3",
        "previous": "…?page=1"
      },
      "errors": null
    }

Clients may override the page size with ?page_size=N up to a hard cap.
"""
from collections import OrderedDict

from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response


class StandardPagination(PageNumberPagination):
    page_size = 25
    page_size_query_param = "page_size"
    max_page_size = 200
    page_query_param = "page"

    def get_paginated_response(self, data) -> Response:
        return Response(
            OrderedDict(
                [
                    ("results", data),
                    (
                        "pagination",
                        OrderedDict(
                            [
                                ("count", self.page.paginator.count),
                                ("page", self.page.number),
                                ("page_size", self.get_page_size(self.request)),
                                ("num_pages", self.page.paginator.num_pages),
                                ("next", self.get_next_link()),
                                ("previous", self.get_previous_link()),
                            ]
                        ),
                    ),
                ]
            )
        )

    def get_paginated_response_schema(self, schema):
        return {
            "type": "object",
            "properties": {
                "results": schema,
                "pagination": {
                    "type": "object",
                    "properties": {
                        "count": {"type": "integer"},
                        "page": {"type": "integer"},
                        "page_size": {"type": "integer"},
                        "num_pages": {"type": "integer"},
                        "next": {"type": "string", "nullable": True, "format": "uri"},
                        "previous": {"type": "string", "nullable": True, "format": "uri"},
                    },
                },
            },
        }

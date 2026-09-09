"""Custom DRF exception handling for the Vessel API.

Produces a consistent error envelope for every handled error:

    {
      "success": false,
      "data": null,
      "errors": [
        {"code": "invalid", "detail": "This field is required.", "field": "name"}
      ]
    }

Never leaks stack traces or secret values to clients (see
docs/DEVELOPMENT_WORKFLOW.md §14). Unhandled server errors are logged and
returned as a generic 500 without internals.
"""
from __future__ import annotations

import logging
from typing import Any

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

logger = logging.getLogger("vessel.api")


def _normalize_errors(data: Any) -> list[dict]:
    """Flatten DRF's error payloads into a list of {code, detail, field}."""
    errors: list[dict] = []

    if isinstance(data, dict):
        for field, detail in data.items():
            if isinstance(detail, (list, tuple)):
                for item in detail:
                    errors.append(_error_item(field, item))
            else:
                errors.append(_error_item(field, detail))
    elif isinstance(data, (list, tuple)):
        for item in data:
            errors.append(_error_item(None, item))
    else:
        errors.append(_error_item(None, data))

    return errors


def _error_item(field: str | None, detail: Any) -> dict:
    code = getattr(detail, "code", None) or "error"
    item = {"code": str(code), "detail": str(detail)}
    # "non_field_errors" and "detail" are not real field names.
    if field and field not in ("non_field_errors", "detail"):
        item["field"] = field
    return item


def exception_handler(exc: Exception, context: dict) -> Response | None:
    """DRF exception handler returning the consistent error envelope."""
    response = drf_exception_handler(exc, context)

    if response is None:
        # Unhandled exception -> log server-side, return a safe generic 500.
        logger.exception("Unhandled API exception", exc_info=exc)
        return Response(
            {
                "success": False,
                "data": None,
                "errors": [
                    {"code": "server_error", "detail": "An unexpected error occurred."}
                ],
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    response.data = {
        "success": False,
        "data": None,
        "errors": _normalize_errors(response.data),
    }
    return response

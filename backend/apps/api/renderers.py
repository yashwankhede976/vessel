"""Consistent-response renderer for the Vessel API.

Wraps successful responses in a stable envelope so every endpoint returns the
same shape:

    { "success": true, "data": <payload>, "errors": null }

For paginated responses (data carrying "results" + "pagination"), the results
become `data` and pagination is lifted to a top-level `pagination` key.

Error responses are already shaped by apps.api.exceptions.exception_handler and
are passed through unchanged.
"""
from rest_framework.renderers import JSONRenderer


class EnvelopeJSONRenderer(JSONRenderer):
    """JSON renderer that applies the consistent success envelope."""

    def render(self, data, accepted_media_type=None, renderer_context=None):
        renderer_context = renderer_context or {}
        response = renderer_context.get("response")
        status_code = getattr(response, "status_code", 200)

        payload = self._wrap(data, status_code)
        return super().render(payload, accepted_media_type, renderer_context)

    @staticmethod
    def _wrap(data, status_code):
        # Already-wrapped payloads (from the exception handler or explicit
        # envelopes) are passed through unchanged.
        if isinstance(data, dict) and "success" in data and "errors" in data:
            return data

        # Error status codes are handled by the exception handler; if we get
        # here with an error status and an unwrapped body, wrap defensively.
        if status_code and status_code >= 400:
            return {"success": False, "data": None, "errors": data}

        # Paginated payload -> lift results/pagination.
        if isinstance(data, dict) and "results" in data and "pagination" in data:
            return {
                "success": True,
                "data": data["results"],
                "pagination": data["pagination"],
                "errors": None,
            }

        return {"success": True, "data": data, "errors": None}

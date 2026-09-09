"""Fix-wait API view (v1)."""
from __future__ import annotations

from drf_spectacular.utils import extend_schema
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from rest_framework import status

from apps.decisions.services.fix_wait import (
    FixWaitError,
    FixWaitInput,
    decide_fix_wait,
)

from .serializers import FixWaitRequestSerializer


class FixWaitView(APIView):
    """Recommend FIX_NOW / WAIT / PARTIAL_FIX / MONITOR for a fixture decision.

    Every decision threshold is a documented constant (see the fix_wait engine);
    the response includes the numeric drivers and thresholds used.
    """

    authentication_classes: list = []
    permission_classes: list = []

    @extend_schema(
        summary="Fix / Wait timing decision",
        request=FixWaitRequestSerializer,
        responses=FixWaitRequestSerializer,
    )
    def post(self, request: Request) -> Response:
        payload = FixWaitRequestSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        try:
            result = decide_fix_wait(FixWaitInput(**payload.validated_data))
        except FixWaitError as exc:
            return Response(
                {"success": False, "data": None,
                 "errors": [{"code": "invalid_request", "detail": str(exc)}]},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(result.to_dict())

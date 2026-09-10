"""AI chatbot API (v1): POST /chat/.

Thin HTTP adapter over apps.decisions.services.chatbot. It validates input,
delegates to the grounded chatbot service (which reads OPENAI_API_KEY on the
backend and never exposes it), and returns a clean JSON envelope. The response
never contains the API key or the raw prompt.

Rate limited via the 'chat' scope (see settings DEFAULT_THROTTLE_RATES).
"""
from __future__ import annotations

from drf_spectacular.utils import OpenApiExample, extend_schema
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.decisions.services.chatbot import answer_chat, reset_conversation
from apps.decisions.services.decision_engine import DecisionError
from apps.decisions.services.landed_cost import LandedCostError

from .serializers import ChatRequestSerializer


def _error(detail: str, code: str = "invalid_request", http=status.HTTP_400_BAD_REQUEST) -> Response:
    return Response(
        {"success": False, "data": None, "errors": [{"code": code, "detail": detail}]},
        status=http,
    )


class ChatView(APIView):
    """Grounded AI chatbot. Answers from the platform's own decision engines;
    OpenAI (backend-only key) phrases the answer when configured, otherwise a
    deterministic grounded fallback is returned."""

    authentication_classes: list = []
    permission_classes: list = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "chat"

    @extend_schema(
        summary="AI chatbot (grounded in platform data)",
        request=ChatRequestSerializer,
        examples=[
            OpenApiExample(
                "Fix or wait",
                value={
                    "message": "Should I fix Australia to Paradip?",
                    "conversation_id": "",
                    "context": {"origin": "Australia", "destination": "Paradip"},
                },
                request_only=True,
            )
        ],
    )
    def post(self, request: Request) -> Response:
        payload = ChatRequestSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = payload.validated_data
        try:
            result = answer_chat(
                message=data["message"],
                conversation_id=data.get("conversation_id") or None,
                context=data.get("context") or {},
            )
        except (DecisionError, LandedCostError) as exc:
            return _error(str(exc))
        return Response(result.to_dict())

    @extend_schema(summary="Reset a chat conversation")
    def delete(self, request: Request) -> Response:
        conversation_id = request.query_params.get("conversation_id")
        if not conversation_id:
            return _error("conversation_id is required to reset.")
        reset_conversation(conversation_id)
        return Response({"conversation_id": conversation_id, "reset": True})

"""Contract-strategy API views (v1): spot-vs-contract + contract portfolio."""
from __future__ import annotations

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.decisions.services.contract_portfolio import (
    ContractPortfolioError,
    ContractPortfolioInput,
    build_portfolio,
)
from apps.decisions.services.spot_vs_contract import (
    SpotVsContractError,
    SpotVsContractInput,
    compare_strategies,
)

from .serializers import (
    ContractPortfolioRequestSerializer,
    SpotVsContractRequestSerializer,
)


def _error(detail: str) -> Response:
    return Response(
        {"success": False, "data": None,
         "errors": [{"code": "invalid_request", "detail": detail}]},
        status=status.HTTP_400_BAD_REQUEST,
    )


class SpotVsContractView(APIView):
    """Compare the four chartering strategies and recommend one."""

    authentication_classes: list = []
    permission_classes: list = []

    @extend_schema(
        summary="Spot vs contract comparison",
        request=SpotVsContractRequestSerializer,
        responses=SpotVsContractRequestSerializer,
    )
    def post(self, request: Request) -> Response:
        payload = SpotVsContractRequestSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        try:
            result = compare_strategies(SpotVsContractInput(**payload.validated_data))
        except SpotVsContractError as exc:
            return _error(str(exc))
        return Response(result.to_dict())


class ContractPortfolioView(APIView):
    """Recommend a diversified contract mix for a multi-month requirement."""

    authentication_classes: list = []
    permission_classes: list = []

    @extend_schema(
        summary="Contract portfolio recommendation",
        request=ContractPortfolioRequestSerializer,
        responses=ContractPortfolioRequestSerializer,
    )
    def post(self, request: Request) -> Response:
        payload = ContractPortfolioRequestSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        try:
            result = build_portfolio(ContractPortfolioInput(**payload.validated_data))
        except ContractPortfolioError as exc:
            return _error(str(exc))
        return Response(result.to_dict())

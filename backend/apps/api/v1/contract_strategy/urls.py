"""Contract-strategy domain API routes (v1)."""
from django.urls import path

from .views import ContractPortfolioView, SpotVsContractView

app_name = "contract_strategy"

urlpatterns = [
    path("compare/", SpotVsContractView.as_view(), name="compare"),
    path("portfolio/", ContractPortfolioView.as_view(), name="portfolio"),
]

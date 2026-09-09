"""System / observability API routes (v1)."""
from django.urls import path

from .views import DataFreshnessView, ExternalServicesView

app_name = "system"

urlpatterns = [
    path("data-freshness/", DataFreshnessView.as_view(), name="data_freshness"),
    path("external-services/", ExternalServicesView.as_view(), name="external_services"),
]

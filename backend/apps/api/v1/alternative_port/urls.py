"""Alternative-port domain API routes (v1)."""
from django.urls import path

from .views import AlternativePortView

app_name = "alternative_port"

urlpatterns = [
    path("", AlternativePortView.as_view(), name="compare"),
]

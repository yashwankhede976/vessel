"""ETA domain API routes (v1)."""
from django.urls import path

from .views import ETAView

app_name = "eta"

urlpatterns = [
    path("", ETAView.as_view(), name="predict"),
]

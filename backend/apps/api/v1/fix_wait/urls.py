"""Fix-wait domain API routes (v1)."""
from django.urls import path

from .views import FixWaitView

app_name = "fix_wait"

urlpatterns = [
    path("", FixWaitView.as_view(), name="decision"),
]

"""AI chatbot API routes (v1)."""
from django.urls import path

from .views import ChatView

app_name = "chat"

urlpatterns = [
    path("", ChatView.as_view(), name="chat"),
]

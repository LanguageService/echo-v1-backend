from django.urls import path
from .views import (
    DeveloperAppListCreateView,
    DeveloperAppDetailView,
    WebhookListCreateView,
    WebhookDetailView,
)

urlpatterns = [
    path("", DeveloperAppListCreateView.as_view(), name="api-keys-list-create"),
    path("<int:pk>/", DeveloperAppDetailView.as_view(), name="api-keys-detail"),
    path("webhooks/", WebhookListCreateView.as_view(), name="webhooks-list-create"),
    path("webhooks/<int:pk>/", WebhookDetailView.as_view(), name="webhooks-detail"),
]

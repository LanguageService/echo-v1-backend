from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status

from .models import DeveloperApp, WebhookEndpoint


def _serialize_app(app, include_secret=False):
    data = {
        "id": str(app.pk),
        "name": app.name,
        "client_id": app.client_id,
        "is_active": app.is_active,
        "created_at": app.created_at.isoformat(),
        "last_used": None,
    }
    if include_secret:
        data["client_secret"] = app.client_secret
    return data


def _serialize_webhook(webhook, include_secret=False):
    data = {
        "id": str(webhook.pk),
        "app_id": str(webhook.developer_app_id),
        "app_name": webhook.developer_app.name,
        "url": webhook.url,
        "is_active": webhook.is_active,
        "created_at": webhook.created_at.isoformat(),
    }
    if include_secret:
        data["secret"] = webhook.secret
    return data


class DeveloperAppListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        apps = DeveloperApp.objects.filter(user=request.user, is_active=True).order_by("-created_at")
        return Response([_serialize_app(app) for app in apps])

    def post(self, request):
        name = request.data.get("name", "").strip()
        if not name:
            return Response({"error": "name is required"}, status=status.HTTP_400_BAD_REQUEST)

        app = DeveloperApp.objects.create(user=request.user, name=name)
        return Response(_serialize_app(app, include_secret=True), status=status.HTTP_201_CREATED)


class DeveloperAppDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, pk):
        try:
            app = DeveloperApp.objects.get(pk=pk, user=request.user)
        except DeveloperApp.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)
        app.is_active = False
        app.save(update_fields=["is_active"])
        return Response(status=status.HTTP_204_NO_CONTENT)


class WebhookListCreateView(APIView):
    """
    GET  /api/v1/api-keys/webhooks/          — list all webhooks for the authenticated user
    POST /api/v1/api-keys/webhooks/          — create a webhook (body: {app_id, url})
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        webhooks = WebhookEndpoint.objects.filter(
            developer_app__user=request.user,
            is_active=True,
        ).select_related("developer_app").order_by("-created_at")
        return Response([_serialize_webhook(wh) for wh in webhooks])

    def post(self, request):
        url = request.data.get("url", "").strip()
        app_id = request.data.get("app_id")

        if not url:
            return Response({"error": "url is required"}, status=status.HTTP_400_BAD_REQUEST)
        if not app_id:
            return Response({"error": "app_id is required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            app = DeveloperApp.objects.get(pk=app_id, user=request.user, is_active=True)
        except DeveloperApp.DoesNotExist:
            return Response({"error": "API key not found"}, status=status.HTTP_404_NOT_FOUND)

        webhook = WebhookEndpoint.objects.create(developer_app=app, url=url)
        return Response(_serialize_webhook(webhook, include_secret=True), status=status.HTTP_201_CREATED)


class WebhookDetailView(APIView):
    """
    DELETE /api/v1/api-keys/webhooks/<pk>/  — remove a webhook
    """
    permission_classes = [IsAuthenticated]

    def delete(self, request, pk):
        try:
            webhook = WebhookEndpoint.objects.get(
                pk=pk, developer_app__user=request.user
            )
        except WebhookEndpoint.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)
        webhook.is_active = False
        webhook.save(update_fields=["is_active"])
        return Response(status=status.HTTP_204_NO_CONTENT)

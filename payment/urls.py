from django.urls import path, include
from rest_framework.routers import DefaultRouter

from . import views
from .views import KPayWebhookViewSet


app_name = "payment"

router = DefaultRouter()
router.register("", views.PaymentViewSet)
router.register(
    r"webhook/kpay",
    KPayWebhookViewSet,
    basename="kpay-webhook",
)

urlpatterns = [
    path("", include(router.urls)),
]

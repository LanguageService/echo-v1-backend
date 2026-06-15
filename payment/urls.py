from django.urls import path, include
from rest_framework.routers import DefaultRouter

from . import views
from .views import PaymentWebhookViewSet


app_name = "payment"

router = DefaultRouter()
router.register("", views.PaymentViewSet)
router.register(
    r"webhook/payment",
    PaymentWebhookViewSet,
    basename="payment-webhook",
)

urlpatterns = [
    path("", include(router.urls)),
]

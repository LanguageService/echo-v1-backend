from django.urls import path, include
from rest_framework.routers import DefaultRouter

from . import views

app_name = "payment"

router = DefaultRouter()
router.register("", views.PaymentViewSet)

urlpatterns = [
    path("", include(router.urls)),
]

from django.urls import path, include
from rest_framework.routers import DefaultRouter

from . import views


router = DefaultRouter()

router.register("transactions", views.TransactionViewSet)
router.register("global-config", views.GlobalConfigViewSet, basename="global-config")
router.register("", views.WalletViewSet)

urlpatterns = [
    path("", include(router.urls)),
]

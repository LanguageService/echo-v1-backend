from django.urls import path, include
from rest_framework.routers import DefaultRouter
from ..views import TextTranslationViewSet

router = DefaultRouter()
router.register(r"text", TextTranslationViewSet, basename="text translation")


urlpatterns = [
    path("", include(router.urls)),
]

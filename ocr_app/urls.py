from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'ocr', views.OcrViewSet, basename='ocr')
router.register(r'', views.HealthCheckViewSet, basename='health')

urlpatterns = [
    path('', include(router.urls)),
]

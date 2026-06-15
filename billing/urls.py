from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import PricingViewSet

router = DefaultRouter()
router.register(r'pricing', PricingViewSet, basename='pricing')

urlpatterns = [
    path('', include(router.urls)),
]

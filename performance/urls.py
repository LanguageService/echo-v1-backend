"""
URL patterns for performance-optimized API endpoints
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import PerformanceViewSet

# Create a router and register our viewsets with it.
router = DefaultRouter()
router.register(r'', PerformanceViewSet, basename='performance')

# The API URLs are now determined automatically by the router.
urlpatterns = [
    path('', include(router.urls)),
]

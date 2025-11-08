"""
Statistics URLs

URL configuration for statistics API endpoints.
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import StatsViewSet

app_name = 'stats_app'

# Create a router and register our viewset with it.
router = DefaultRouter()
router.register(r'', StatsViewSet, basename='stats')

# The API URLs are now determined automatically by the router.
urlpatterns = [
    path('', include(router.urls)),
]

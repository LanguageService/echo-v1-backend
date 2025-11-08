"""
Statistics URLs

URL configuration for statistics API endpoints.
"""

from django.urls import path
from .views import (
    stats_api_info, stats_health_check, 
    personal_stats_view, admin_stats_view
)

app_name = 'stats_app'

urlpatterns = [
    # API Info and Health
    path('', stats_api_info, name='stats_api_info'),
    path('health/', stats_health_check, name='stats_health_check'),
    
    # Statistics endpoints
    path('user/', personal_stats_view, name='personal_stats'),
    path('admin/', admin_stats_view, name='admin_stats'),
]
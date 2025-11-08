"""
Voice Translation URL Configuration

URL patterns for the Speak Africa voice translation API endpoints.
"""

from django.urls import path, include
from . import views

app_name = 'voice_translator'

urlpatterns = [
    # API Info
    path('', views.APIInfoView.as_view(), name='api_info'),
    
    # Health Check
    path('health/', views.HealthCheckAPIView.as_view(), name='health_check'),
    
    # Main Translation Endpoint
    path('translate/', views.VoiceTranslationAPIView.as_view(), name='voice_translate'),
    
    # Translation History
    path('translations/', views.TranslationHistoryAPIView.as_view(), name='translation_history'),
    path('translations/<uuid:translation_id>/', views.TranslationDetailAPIView.as_view(), name='translation_detail'),
    
    # User Settings
    path('settings/', views.UserSettingsAPIView.as_view(), name='user_settings'),
    
    # Language Support
    path('languages/', views.LanguageSupportAPIView.as_view(), name='supported_languages'),
    
    # Async Endpoints for improved performance
    path('translate/async/', views.AsyncVoiceTranslationAPIView.as_view(), name='async_voice_translate'),
    path('translations/async/', views.AsyncTranslationHistoryAPIView.as_view(), name='async_translation_history'),
    
    # Background Processing with Celery
    path('translate/background/', views.BackgroundVoiceTranslationAPIView.as_view(), name='background_voice_translate'),
    path('task/<str:task_id>/status/', views.TaskStatusAPIView.as_view(), name='task_status'),
]
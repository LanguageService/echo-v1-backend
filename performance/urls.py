"""
URL patterns for performance-optimized API endpoints
"""
from django.urls import path
from . import enhanced_api_views

urlpatterns = [
    # Enhanced processing endpoints
    path('ocr/enhanced/', enhanced_api_views.enhanced_ocr_process, name='enhanced_ocr_process'),
    path('voice/enhanced/', enhanced_api_views.enhanced_voice_process, name='enhanced_voice_process'),
    path('batch/ocr/', enhanced_api_views.batch_ocr_process, name='batch_ocr_process'),
    
    # Performance and monitoring
    path('stats/', enhanced_api_views.performance_stats, name='performance_stats'),
    path('cache/clear/', enhanced_api_views.clear_user_cache, name='clear_user_cache'),
    path('cache/warm/', enhanced_api_views.warm_cache, name='warm_cache'),
    
    # Testing and debugging
    path('test/language/', enhanced_api_views.language_detection_test, name='language_detection_test'),
]
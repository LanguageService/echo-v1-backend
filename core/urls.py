"""core URL Configuration"""
from django.urls import path, include
from django.contrib import admin
from django.conf import settings
from django.conf.urls.static import static
from django.http import JsonResponse
from django.views.generic import RedirectView
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView

def api_root(request):
    """Root API endpoint with system information"""
    return JsonResponse({
        'name': 'OCR & Voice Translation API System',
        'description': 'Comprehensive backend API system supporting image OCR translation and voice translation with African language specialization',
        'version': '1.0.0',
        # 'services': {
        #     'authentication': {
        #         'description': 'User authentication and management',
        #         'endpoint': '/auth/',
        #         'features': ['JWT authentication', 'Email verification', 'OTP password reset', 'User profiles']
        #     },
        #     'ocr_translation': {
        #         'description': 'Extract and translate text from images',
        #         'endpoint': '/api/image/',
        #         'features': ['Image text extraction', 'Language detection', 'Translation via Gemini AI']
        #     },
        #     'voice_translation': {
        #         'description': 'Speak Africa voice translation service',
        #         'endpoint': '/api/voice/',
        #         'features': ['Speech-to-text', 'Multi-language support', 'African language specialization', 'Translation history']
        #     },
        #     'statistics': {
        #         'description': 'User and system statistics tracking',
        #         'endpoint': '/statistics/',
        #         'features': ['Personal usage statistics', 'Admin system analytics', 'Processing metrics', 'Success/failure tracking']
        #     }
        # },
        # 'admin_panel': '/admin/',
        # 'api_documentation': {
        #     'swagger': '/api/schema/swagger-ui/',
        #     'redoc': '/api/schema/redoc/',
        #     'schema': '/api/schema/'
        # },
        'authentication': 'JWT Bearer Token Required',
        'supported_languages': 22,
        'african_languages_supported': 10
    })


SPECTACULAR_SETTINGS = {
    "TITLE": "ECHO API",
    "DESCRIPTION": "Your project description",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    # OTHER SETTINGS
}

urlpatterns = [

    path('', api_root, name='api_root'),
    path('admin/', admin.site.urls),
    
    # API Documentation
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/v1/doc/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/v1/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
    
    # Authentication
    path('auth/v1/', include('users.urls')),
    
    # API Services
    path('api/v1/image/', include('ocr_app.urls')),
    path('api/v1/voice/', include('voice_translator.urls')),
    
    # Statistics
    path('api/v1/statistics/', include('stats_app.urls')),
    
    # Performance Optimization APIs
    path('api/v1/performance/', include('performance.urls')),
]

# Serve media files during development
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

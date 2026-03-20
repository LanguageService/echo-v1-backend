from django.urls import path
from translation import views

urlpatterns = [
    path('health/', views.HealthCheckAPIView.as_view(), name='health_check'),
    path('settings/', views.UserSettingsAPIView.as_view(), name='user_settings'),
    path('languages/', views.LanguageSupportAPIView.as_view(), name='supported_languages'),
]

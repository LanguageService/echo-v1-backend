"""
User URLs

URL configuration for user authentication and profile management.
"""

from django.urls import path, include
from rest_framework_simplejwt.views import TokenVerifyView

from .views import (
    CustomRegisterView, CustomLoginView, CustomLogoutView, EmailVerificationView,
    ResendVerificationView, PasswordResetRequestView, PasswordResetConfirmView,
    ChangePasswordView, UserProfileView,
    auth_health_check, auth_api_info
)

app_name = 'users'

urlpatterns = [
    # API Info and Health
    path('', auth_api_info, name='auth_api_info'),
    path('health/', auth_health_check, name='auth_health_check'),
    
    # Authentication endpoints
    path('registration/', CustomRegisterView.as_view(), name='register'),
    path('login/', CustomLoginView.as_view(), name='login'),
    path('logout/', CustomLogoutView.as_view(), name='logout'),
    
    # Email verification
    path('verify-email/', EmailVerificationView.as_view(), name='verify_email'),
    path('resend-verification/', ResendVerificationView.as_view(), name='resend_verification'),
    
    # Password management
    path('password/change/', ChangePasswordView.as_view(), name='change_password'),
    path('password/reset/', PasswordResetRequestView.as_view(), name='password_reset_request'),
    path('password/reset/confirm/', PasswordResetConfirmView.as_view(), name='password_reset_confirm'),
    
    # JWT token management
    path('token/refresh/', get_refresh_view().as_view(), name='token_refresh'),
    path('token/verify/', TokenVerifyView.as_view(), name='token_verify'),
    
    # Profile management
    path('profile/', UserProfileView.as_view(), name='user_profile'),
    
    # User details endpoint only (no conflicting login)
    path('user/', UserDetailsView.as_view(), name='rest_user_details'),
]

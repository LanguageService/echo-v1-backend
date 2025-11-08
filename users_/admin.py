"""
User Admin

Django admin configuration for user management.
"""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth import get_user_model
from .models import EmailVerificationOTP, UserProfile

User = get_user_model()


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """Admin interface for User model"""
    
    list_display = [
        'email', 'first_name', 'last_name', 'is_active', 
        'email_verified', 'is_staff', 'date_joined', 'last_login'
    ]
    list_filter = [
        'is_active', 'email_verified', 'is_staff', 'is_superuser',
        'date_joined', 'last_login'
    ]
    search_fields = ['email', 'first_name', 'last_name']
    ordering = ['-date_joined']
    filter_horizontal = []
    
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal Info', {
            'fields': ('first_name', 'last_name', 'phone_number', 'profile_picture')
        }),
        ('Permissions', {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions'),
            'classes': ('collapse',)
        }),
        ('Account Status', {
            'fields': ('email_verified', 'login_attempts', 'last_failed_login', 'account_locked_until')
        }),
        ('Important Dates', {'fields': ('last_login', 'date_joined')}),
    )
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'password1', 'password2', 'first_name', 'last_name'),
        }),
    )
    
    readonly_fields = ['date_joined', 'last_login', 'last_modified']


@admin.register(EmailVerificationOTP)
class EmailVerificationOTPAdmin(admin.ModelAdmin):
    """Admin interface for EmailVerificationOTP model"""
    
    list_display = [
        'user', 'purpose', 'otp_code', 'is_used', 
        'date_created', 'expires_at', 'is_expired'
    ]
    list_filter = ['purpose', 'is_used', 'date_created', 'expires_at']
    search_fields = ['user__email', 'otp_code']
    ordering = ['-date_created']
    readonly_fields = ['date_created', 'expires_at', 'is_expired']
    
    def is_expired(self, obj):
        """Display if OTP is expired"""
        return obj.is_expired()
    is_expired.boolean = True
    is_expired.short_description = 'Expired'


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    """Admin interface for UserProfile model"""
    
    list_display = [
        'user', 'location', 'preferred_language', 'timezone',
        'api_calls_today', 'api_calls_this_month', 'last_api_call'
    ]
    list_filter = [
        'preferred_language', 'timezone', 'email_notifications', 
        'sms_notifications', 'date_created'
    ]
    search_fields = ['user__email', 'location']
    ordering = ['-date_created']
    readonly_fields = ['date_created', 'last_modified', 'last_api_call']
    
    fieldsets = (
        ('User Info', {'fields': ('user',)}),
        ('Profile', {
            'fields': ('bio', 'location', 'birth_date', 'website')
        }),
        ('Preferences', {
            'fields': ('preferred_language', 'timezone', 'email_notifications', 'sms_notifications')
        }),
        ('API Usage', {
            'fields': ('api_calls_today', 'api_calls_this_month', 'last_api_call'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('date_created', 'last_modified'),
            'classes': ('collapse',)
        }),
    )

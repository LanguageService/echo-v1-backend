"""
Voice Translation Admin Configuration

Django admin interface for managing voice translation models.
"""

from django.contrib import admin
from .models import (
    TextTranslation, SpeechTranslation, ImageTranslation, 
    UserSettings, AudioFile, LanguageSupport, CloudStorageConfig,
    LLMLog, SpeechTranslationProcessingTime
)

@admin.register(TextTranslation)
class TextTranslationAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'title', 'original_language', 'target_language', 
        'status', 'mode', 'is_sms', 'date_created'
    ]
    list_filter = ['status', 'mode', 'is_sms', 'original_language', 'target_language', 'date_created']
    search_fields = ['id', 'title', 'original_text', 'translated_text']
    readonly_fields = ['id', 'date_created', 'last_modified']
    ordering = ['-date_created']

@admin.register(SpeechTranslation)
class SpeechTranslationAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'title', 'speech_service', 'original_language', 'target_language', 
        'status', 'mode', 'date_created'
    ]
    list_filter = ['speech_service', 'status', 'mode', 'original_language', 'target_language', 'date_created']
    search_fields = ['id', 'title', 'original_text', 'translated_text']
    readonly_fields = ['id', 'date_created', 'last_modified']
    ordering = ['-date_created']

@admin.register(ImageTranslation)
class ImageTranslationAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'title', 'original_language', 'target_language', 
        'status', 'date_created'
    ]
    list_filter = ['status', 'original_language', 'target_language', 'date_created']
    search_fields = ['id', 'title', 'ocr_text', 'translated_text']
    readonly_fields = ['id', 'date_created', 'last_modified']
    ordering = ['-date_created']

@admin.register(LLMLog)
class LLMLogAdmin(admin.ModelAdmin):
    list_display = ['id', 'provider', 'model_name', 'function_performed', 'total_tokens', 'status', 'created_at']
    list_filter = ['provider', 'model_name', 'function_performed', 'status', 'created_at']
    search_fields = ['id', 'error_message']
    readonly_fields = ['created_at']


@admin.register(UserSettings)
class UserSettingsAdmin(admin.ModelAdmin):
    """Admin interface for UserSettings model"""
    
    list_display = [
        'user', 'model', 'voice', 'source_language', 
        'target_language', 'autoplay', 'super_fast_mode', 'date_created'
    ]
    list_filter = [
        'model', 'voice', 'source_language', 'target_language', 
        'autoplay', 'super_fast_mode'
    ]
    search_fields = ['user__email', 'user__first_name', 'user__last_name']
    readonly_fields = ['date_created', 'last_modified']
    ordering = ['-last_modified']


@admin.register(AudioFile)
class AudioFileAdmin(admin.ModelAdmin):
    """Admin interface for AudioFile model"""
    
    list_display = [
        'id', 'audio_type', 'language', 'duration', 
        'file_size', 'format', 'translation', 'date_created'
    ]
    list_filter = [
        'audio_type', 'language', 'format', 'date_created'
    ]
    search_fields = ['translation__original_text', 'translation__translated_text']
    readonly_fields = ['id', 'date_created']
    ordering = ['-date_created']


@admin.register(LanguageSupport)
class LanguageSupportAdmin(admin.ModelAdmin):
    """Admin interface for LanguageSupport model"""
    
    list_display = [
        'code', 'name', 'native_name', 'flag_emoji',
        'is_african_language',
        'speech_to_text_supported', 'text_to_speech_supported',
        'text_to_text_supported', 'speech_to_speech_translation_supported',
        'image_translation_supported', 'document_translation_supported'
    ]
    list_filter = [
        'is_african_language',
        'speech_to_text_supported', 'text_to_speech_supported',
        'text_to_text_supported', 'speech_to_speech_translation_supported',
        'image_translation_supported', 'document_translation_supported'
    ]
    search_fields = ['code', 'name', 'native_name']
    ordering = ['name']
    
    actions = ['enable_all_features', 'disable_tts']
    
    def enable_all_features(self, request, queryset):
        """Enable all features for selected languages"""
        queryset.update(
            speech_to_text_supported=True,
            text_to_speech_supported=True,
            text_to_text_supported=True,
            speech_to_speech_translation_supported=True,
            image_translation_supported=True,
            document_translation_supported=True
        )
        self.message_user(request, f'Enabled all features for {queryset.count()} languages.')
    enable_all_features.short_description = "Enable all features for selected languages"
    
    def disable_tts(self, request, queryset):
        """Disable text-to-speech for selected languages"""
        queryset.update(text_to_speech_supported=False)
        self.message_user(request, f'Disabled TTS for {queryset.count()} languages.')
    disable_tts.short_description = "Disable text-to-speech for selected languages"


@admin.register(SpeechTranslationProcessingTime)
class SpeechTranslationProcessingTimeAdmin(admin.ModelAdmin):
    list_display = ['id', 'translation', 'speech_to_text', 'text_to_text', 'text_to_speech', 'total']
    list_filter = ['translation__speech_service', 'date_created']
    readonly_fields = ['id', 'date_created', 'last_modified']


@admin.register(CloudStorageConfig)
class CloudStorageConfigAdmin(admin.ModelAdmin):
    """Admin interface for CloudStorageConfig model"""
    
    list_display = [
        'name', 'provider', 'bucket_name', 'region', 
        'credentials_status', 'is_active', 'date_created'
    ]
    list_filter = ['provider', 'is_active', 'date_created']
    search_fields = ['name', 'bucket_name']
    readonly_fields = ['expected_env_vars', 'credentials_status', 'date_created', 'last_modified']
    ordering = ['-is_active', 'name']
    
    fieldsets = (
        ('Basic Configuration', {
            'fields': ('name', 'provider', 'bucket_name', 'region', 'endpoint_url', 'is_active')
        }),
        ('Environment Variables', {
            'fields': ('credentials_env_prefix', 'expected_env_vars', 'credentials_status'),
            'description': 'Credentials are stored securely in environment variables. Configure them through your hosting platform secrets or environment settings.'
        }),
        ('Timestamps', {
            'fields': ('date_created', 'last_modified'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['activate_config', 'deactivate_config']
    
    def expected_env_vars(self, obj):
        """Show the expected environment variable names"""
        if obj.pk:  # Only for saved objects
            vars_list = obj.get_expected_env_vars()
            if vars_list:
                return ", ".join(vars_list)
        return "Save configuration to see expected environment variables"
    expected_env_vars.short_description = "Expected Environment Variables"
    
    def credentials_status(self, obj):
        """Check if required credentials are available in environment"""
        import os
        if not obj.pk:  # New object
            return "Not checked yet - save first"
        
        env_vars = obj.get_expected_env_vars()
        if not env_vars:
            return "No credentials required"
        
        missing = []
        for var in env_vars:
            if not config(var):
                missing.append(var)
        
        if not missing:
            return "✓ All credentials available"
        else:
            return f"✗ Missing: {', '.join(missing)}"
    credentials_status.short_description = "Credentials Status"
    
    def activate_config(self, request, queryset):
        """Activate selected configurations and deactivate others"""
        # First deactivate all configurations
        CloudStorageConfig.objects.update(is_active=False)
        # Then activate selected ones
        updated = queryset.update(is_active=True)
        self.message_user(request, f'Activated {updated} cloud storage configurations.')
    activate_config.short_description = "Activate selected configurations"
    
    def deactivate_config(self, request, queryset):
        """Deactivate selected configurations"""
        updated = queryset.update(is_active=False)
        self.message_user(request, f'Deactivated {updated} cloud storage configurations.')
    deactivate_config.short_description = "Deactivate selected configurations"


# Customize admin site header and title
admin.site.site_header = 'Speak Africa Voice Translation Admin'
admin.site.site_title = 'Voice Translation Admin'
admin.site.index_title = 'Voice Translation Administration'

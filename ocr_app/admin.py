from django.contrib import admin
from .models import OCRResult, TranslationFailureLog


@admin.register(OCRResult)
class OCRResultAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'detected_language', 'translation_provider', 'confidence_score', 'date_created']
    list_filter = ['detected_language', 'translation_provider', 'date_created']
    search_fields = ['user__email', 'original_text', 'translated_text']
    readonly_fields = ['date_created', 'last_modified']
    ordering = ['-date_created']


@admin.register(TranslationFailureLog)
class TranslationFailureLogAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'attempted_provider', 'error_type', 'fallback_used', 'date_created', 'resolved_at']
    list_filter = ['attempted_provider', 'error_type', 'fallback_used', 'date_created']
    search_fields = ['user__email', 'source_text', 'error_message']
    readonly_fields = ['date_created', 'resolved_at']
    ordering = ['-date_created']
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user', 'ocr_result')

from django.db import models
from django.utils import timezone
from django.contrib.auth import get_user_model
from core.constants import (
    EXTENDED_TRANSLATION_SERVICE_CHOICES, 
    ERROR_TYPE_CHOICES, 
)
from core.model import BaseModel


User = get_user_model()


class OCRResult(BaseModel):
    """Model to store OCR processing results"""
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='ocr_results', null=True, blank=True)
    image = models.ImageField(upload_to='ocr_images/')
    feature_type = models.CharField(max_length=50, default="IMAGE_TRANSLATION", null=True, blank=True)
    image_url = models.URLField(blank=True, null=True, help_text="Cloud storage URL for uploaded image")
    original_filename = models.CharField(max_length=255, blank=True, null=True, help_text="Original filename of uploaded image")
    image_format = models.CharField(max_length=10, blank=True, null=True, help_text="Image file format (jpg, png, etc.)")
    original_text = models.TextField(blank=True, null=True)
    detected_language = models.CharField(max_length=10, blank=True, null=True)
    translated_text = models.TextField(blank=True, null=True)
    confidence_score = models.FloatField(blank=True, null=True)
    processing_time = models.FloatField(blank=True, null=True, help_text="Total processing time in seconds")  # in seconds
    ocr_processing_time = models.FloatField(blank=True, null=True, help_text="Time for OCR step")
    language_detection_time = models.FloatField(blank=True, null=True, help_text="Time for language detection")
    translation_processing_time = models.FloatField(blank=True, null=True, help_text="Time for translation step")

    
    # Translation service tracking
    translation_provider = models.CharField(
        max_length=20,
        choices=EXTENDED_TRANSLATION_SERVICE_CHOICES,
        blank=True,
        null=True,
        help_text='Translation service that was used for this request'
    )
    
    # Error tracking
    error_message = models.TextField(blank=True, null=True)
    
    class Meta:
        ordering = ['-date_created']
    
    def __str__(self):
        return f"OCR Result {self.id} - {self.detected_language} - {self.created_at.strftime('%Y-%m-%d %H:%M')}"


class TranslationFailureLog(BaseModel):
    """Model to log failed translation requests with detailed error information"""
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='translation_failures', null=True, blank=True)
    ocr_result = models.ForeignKey(OCRResult, on_delete=models.CASCADE, related_name='translation_failures', null=True, blank=True)
    
    # Request details
    source_text = models.TextField(help_text='Original text that failed to translate')
    source_language = models.CharField(max_length=10, blank=True, null=True)
    target_language = models.CharField(max_length=10, default='en')
    
    # Service information
    attempted_provider = models.CharField(
        max_length=20,
        choices=EXTENDED_TRANSLATION_SERVICE_CHOICES,
        help_text='Translation service that failed'
    )
    
    # Error details
    error_message = models.TextField(help_text='Detailed error message from the provider')
    error_type = models.CharField(
        max_length=50,
        choices=ERROR_TYPE_CHOICES,
        default='unknown'
    )
    
    # Retry information
    retry_count = models.IntegerField(default=0, help_text='Number of retry attempts')
    fallback_used = models.BooleanField(default=False, help_text='Whether fallback service was used')
    fallback_provider = models.CharField(max_length=20, blank=True, null=True)
    
    # Timestamps
    resolved_at = models.DateTimeField(blank=True, null=True)
    
    class Meta:
        db_table = 'translation_failure_logs'
        ordering = ['-date_created']
        verbose_name = 'Translation Failure Log'
        verbose_name_plural = 'Translation Failure Logs'
    
    def __str__(self):
        return f"Translation Failure {self.id} - {self.attempted_provider} - {self.created_at.strftime('%Y-%m-%d %H:%M')}"
    
    def mark_resolved(self, fallback_provider=None):
        """Mark this failure as resolved with optional fallback provider"""
        self.resolved_at = timezone.now()
        self.fallback_used = True
        if fallback_provider:
            self.fallback_provider = fallback_provider
        self.save()

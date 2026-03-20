"""
Voice Translation Models

Models for handling voice translations, user settings, and audio files.
"""

from django.db import models
from django.contrib.auth import get_user_model
import uuid
from core.constants import  CLOUD_STORAGE_PROVIDERS
from core.model import BaseModel
from django.conf import settings
from .choices import TranslationStatus, TranslationMode, SpeechServiceType

User = get_user_model()


class SpeechTranslationProcessingTime(BaseModel):
    """Model for storing translation processing times"""
    translation = models.ForeignKey('SpeechTranslation', on_delete=models.CASCADE, related_name='processing_times')
    speech_to_text = models.FloatField(default=0.0, help_text="Speech-to-text processing time in seconds")  # seconds
    text_to_text = models.FloatField(default=0.0)  # seconds
    text_to_speech = models.FloatField(default=0.0)  # seconds
    total = models.FloatField(default=0.0)  # seconds



class BaseTranslation(BaseModel):
    """Abstract Base Class for all translation types"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='%(class)s_translations', null=True, blank=True)
    title = models.CharField(max_length=255, blank=True, null=True)
    
    # Language info
    original_language = models.CharField(max_length=10, default='auto')
    target_language = models.CharField(max_length=10, default='en')
    
    # Status and Metadata
    status = models.CharField(
        max_length=20, 
        choices=TranslationStatus.choices, 
        default=TranslationStatus.PENDING
    )
    mode = models.CharField(
        max_length=10, 
        choices=TranslationMode.choices, 
        default=TranslationMode.SHORT
    )
    session_id = models.CharField(max_length=100, blank=True, null=True)
    error_message = models.TextField(blank=True, null=True)
    total_processing_time = models.FloatField(default=0.0)
    
    class Meta:
        abstract = True
        ordering = ['-date_created']


class TextTranslation(BaseTranslation):
    """Model for text-to-text translations"""
    original_text = models.TextField()
    translated_text = models.TextField(blank=True, null=True)
    is_sms = models.BooleanField(default=False, help_text="Whether this is an SMS translation")
    
    # Document fields for Large text translations
    original_file_url = models.URLField(blank=True, null=True)
    translated_file_url = models.URLField(blank=True, null=True)
    
    
    def __str__(self):
        return f"Text: {self.original_language} -> {self.target_language} ({self.mode})"


class SpeechTranslation(BaseTranslation):
    """Model for speech-to-speech/text translations"""
    # Audio fields
    original_audio = models.FileField(upload_to='translation/speech/input/', null=True, blank=True)
    translated_audio = models.FileField(upload_to='translation/speech/output/', null=True, blank=True)
    original_audio_url = models.URLField(blank=True, null=True)
    translated_audio_url = models.URLField(blank=True, null=True)
    
    # Text results
    original_text = models.TextField(blank=True, null=True)
    translated_text = models.TextField(blank=True, null=True)
    
    # Keep transcript/translation as aliases or just remove? I'll remove for clean refactor
    # if the user has existing data, we would need a migration, but for now I'll replace.
    
    # Technical metadata
    audio_format = models.CharField(max_length=10, blank=True, null=True)
    duration = models.FloatField(default=0.0)
    confidence_score = models.FloatField(default=0.0)
    speech_service = models.CharField(
        max_length=10, 
        choices=SpeechServiceType.choices, 
        default=SpeechServiceType.STS
    )
    
    def __str__(self):
        return f"Speech: {self.original_language} -> {self.target_language} ({self.mode})"


class ImageTranslation(BaseTranslation):
    """Model for image-based translations (OCR)"""
    original_image = models.ImageField(upload_to='translations/images/original/')
    ocr_text = models.TextField(null=True, blank=True)
    translated_text = models.TextField(null=True, blank=True)
    
    class Meta(BaseTranslation.Meta):
        verbose_name_plural = "Image Translations"
    
    def __str__(self):
        return f"Image: {self.original_language} -> {self.target_language}"


class LLMLog(models.Model):
    """Log to track usage of LLM and AI services"""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True)
    provider = models.CharField(max_length=50) # e.g., 'Google'
    model_name = models.CharField(max_length=100) # e.g., 'gemini-2.0-flash'
    function_performed = models.CharField(max_length=50) # e.g., 'ASR', 'Translation', 'TTS', 'Image'
    input_tokens = models.IntegerField(default=0)
    output_tokens = models.IntegerField(default=0)
    total_tokens = models.IntegerField(default=0)
    latency = models.FloatField(default=0.0) # in seconds
    cost = models.DecimalField(max_digits=10, decimal_places=6, default=0.0)
    status = models.CharField(max_length=20, default='success')
    error_message = models.TextField(null=True, blank=True)
    
    # Relationships to translation models (nullable)
    text_translation = models.ForeignKey(TextTranslation, on_delete=models.SET_NULL, null=True, blank=True, related_name='llm_logs')
    speech_translation = models.ForeignKey(SpeechTranslation, on_delete=models.SET_NULL, null=True, blank=True, related_name='llm_logs')
    image_translation = models.ForeignKey(ImageTranslation, on_delete=models.SET_NULL, null=True, blank=True, related_name='llm_logs')
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = "LLM Usage Log"
        verbose_name_plural = "LLM Usage Logs"

    def __str__(self):
        return f"{self.function_performed} - {self.model_name} - {self.created_at}"


# Keep a legacy or common reference for AudioFile if needed, or remove it
# I'll update AudioFile to link to SpeechTranslation instead of Translation


class UserSettings(BaseModel):
    """Model for user preferences and settings"""
    
    AI_MODELS = [
        ('gemini-2.5-flash', 'Gemini 2.5 Flash'),
        ('gemini-2.5-pro', 'Gemini 2.5 Pro'),
    ]
    
    VOICES = [
        # English voices
        ('Zephyr', 'Zephyr (English - Neutral)'),
        ('Nova', 'Nova (English - Female)'),
        ('Orbit', 'Orbit (English - Male)'),
        ('Echo', 'Echo (English - Conversational)'),
        ('Breeze', 'Breeze (English - Calm)'),
        # More voices can be added here
        ('Aria', 'Aria (Multi-language - Female)'),
        ('Phoenix', 'Phoenix (Multi-language - Male)'),
        ('Luna', 'Luna (Multi-language - Neutral)'),
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='voice_settings', primary_key=True)
    model = models.CharField(max_length=50, choices=AI_MODELS, default='gemini-2.5-flash')
    voice = models.CharField(max_length=50, choices=VOICES, default='Zephyr')
    autoplay = models.BooleanField(default=False)
    auto_detect_language = models.BooleanField(default=True)
    super_fast_mode = models.BooleanField(default=False)
    source_language = models.CharField(max_length=10, default='auto')
    target_language = models.CharField(max_length=10, default='en')
    theme = models.CharField(max_length=20, default='african')
    audio_quality = models.CharField(max_length=20, default='high')
    
    
    def __str__(self):
        return f"Settings for {self.user.email}"


class AudioFile(BaseModel):
    """Model for managing audio file metadata"""
    
    AUDIO_TYPES = [
        ('original', 'Original Recording'),
        ('translated', 'Translated Audio'),
        ('tts', 'Text-to-Speech'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    file = models.FileField(upload_to='audio/')
    audio_type = models.CharField(max_length=20, choices=AUDIO_TYPES)
    language = models.CharField(max_length=10)
    duration = models.FloatField(default=0.0)  # seconds
    file_size = models.IntegerField(default=0)  # bytes
    format = models.CharField(max_length=10, default='wav')
    sample_rate = models.IntegerField(default=44100)
    translation = models.ForeignKey(SpeechTranslation, on_delete=models.CASCADE, related_name='audio_files')
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-date_created']
        
    def __str__(self):
        return f"{self.audio_type} - {self.language} ({self.duration}s)"


class CloudStorageConfig(BaseModel):
    """Model for cloud storage configuration metadata (credentials stored in environment variables)"""
    
    STORAGE_PROVIDERS = CLOUD_STORAGE_PROVIDERS
    
    name = models.CharField(max_length=100, unique=True, help_text="Configuration name")
    provider = models.CharField(max_length=10, choices=STORAGE_PROVIDERS, default='s3')
    bucket_name = models.CharField(max_length=255, help_text="Cloud storage bucket name")
    region = models.CharField(max_length=50, default='us-east-1', help_text="Storage region")
    endpoint_url = models.URLField(blank=True, null=True, help_text="Custom endpoint URL (optional)")
    is_active = models.BooleanField(default=True, help_text="Whether this config is currently active")
    credentials_env_prefix = models.CharField(
        max_length=50, 
        default='CLOUD_STORAGE',
        help_text="Environment variable prefix for credentials (e.g., 'CLOUD_STORAGE' looks for CLOUD_STORAGE_ACCESS_KEY)"
    )
   
    
    class Meta:
        ordering = ['-is_active', 'name']
        
    def __str__(self):
        return f"{self.name} ({self.provider})"
    
    def get_expected_env_vars(self):
        """Return the expected environment variable names for this configuration"""
        prefix = self.credentials_env_prefix
        vars_list = []
        
        if self.provider == 's3':
            vars_list = [f"{prefix}_ACCESS_KEY", f"{prefix}_SECRET_KEY", "S3_BUCKET_NAME"]
        elif self.provider == 'gcs':
            vars_list = [f"{prefix}_SERVICE_ACCOUNT_JSON", "GCS_BUCKET_NAME"]
        elif self.provider == 'cloudinary':
            vars_list = [f"{prefix}_CLOUD_NAME", f"{prefix}_API_KEY", f"{prefix}_API_SECRET"]
        
        return vars_list


class LanguageSupport(BaseModel):
    """Model for supported languages and their configurations"""
    
    code = models.CharField(max_length=10, primary_key=True)
    name = models.CharField(max_length=100)
    native_name = models.CharField(max_length=100)
    flag_emoji = models.CharField(max_length=10, default='🌍')
    speech_to_text_supported = models.BooleanField(default=True)
    text_to_speech_supported = models.BooleanField(default=True)
    text_to_text_supported = models.BooleanField(default=True)
    speech_to_speech_translation_supported = models.BooleanField(default=True)
    image_translation_supported = models.BooleanField(default=True)
    document_translation_supported = models.BooleanField(default=True)
    is_african_language = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['name']
        
    def __str__(self):
        return f"{self.name} ({self.code})"

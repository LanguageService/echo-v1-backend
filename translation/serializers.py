"""
Voice Translation Serializers

Serializers for REST API endpoints handling voice translation data.
"""

from rest_framework import serializers
from django.conf import settings
from .models import Translation, UserSettings, AudioFile, LanguageSupport


class LanguageSupportSerializer(serializers.ModelSerializer):
    """Serializer for language support information"""
    
    class Meta:
        model = LanguageSupport
        fields = [
            'code', 'name', 'native_name', 'flag_emoji',
            'speech_to_text_supported', 'text_to_speech_supported',
            'translation_supported', 'is_african_language'
        ]


class AudioFileSerializer(serializers.ModelSerializer):
    """Serializer for audio file metadata"""
    
    file_url = serializers.SerializerMethodField()
    
    class Meta:
        model = AudioFile
        fields = [
            'id', 'file_url', 'audio_type', 'language', 'duration',
            'file_size', 'format', 'sample_rate', 'created_at'
        ]
    
    def get_file_url(self, obj):
        if obj.file:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.file.url)
        return None


class TranslationSerializer(serializers.ModelSerializer):
    """Serializer for translation records"""
    
    audio_files = AudioFileSerializer(many=True, read_only=True)
    original_language_name = serializers.SerializerMethodField()
    target_language_name = serializers.SerializerMethodField()
    
    class Meta:
        model = Translation
        fields = [
            'id', 'original_text', 'translated_text',
            'original_language', 'target_language',
            'original_language_name', 'target_language_name', 'original_audio_url',
            'translated_audio_url', 'confidence_score',
            'total_processing_time', 'session_id', 'date_created', 'last_modified',
            'audio_files', 'feature_type'
        ]
        read_only_fields = ['id', 'created_at', 'last_modified']
    
    def get_original_language_name(self, obj):
        try:
            language = LanguageSupport.objects.get(code=obj.original_language)
            return language.name
        except LanguageSupport.DoesNotExist:
            return obj.original_language.upper()
    
    def get_target_language_name(self, obj):
        try:
            language = LanguageSupport.objects.get(code=obj.target_language)
            return language.name
        except LanguageSupport.DoesNotExist:
            return obj.target_language.upper()


class UserSettingsSerializer(serializers.ModelSerializer):
    """Serializer for user settings"""
    
    class Meta:
        model = UserSettings
        fields = [
            'model', 'voice', 'autoplay',
            'auto_detect_language', 'super_fast_mode',
            'source_language', 'target_language',
            'theme', 'audio_quality', 'date_created', 'last_modified'
        ]
        read_only_fields = ['date_created', 'last_modified']
    
    def create(self, validated_data):
        user = validated_data.pop('user', None)
        # Update existing settings or create new ones
        settings, created = UserSettings.objects.update_or_create(
            user=user,
            defaults=validated_data
        )
        return settings


class VoiceTranslationRequestSerializer(serializers.Serializer):
    """Serializer for voice translation request"""
    
    audio_file = serializers.FileField(
        required=True,
        help_text="Audio file to translate. Supported formats: WAV, MP3, MP4, WebM, OPUS (max 10MB)"
    )
    target_language = serializers.CharField(
        max_length=10, 
        default='en',
        help_text="Target language code (e.g., 'en' for English, 'es' for Spanish, 'sw' for Swahili)"
    )
    session_id = serializers.CharField(
        max_length=100, 
        required=False,
        help_text="Optional session ID to group related translations together"
    )
    source_language = serializers.CharField(
        max_length=10, 
        default='auto', 
        required=False,
        help_text="Source language code or 'auto' for automatic detection"
    )
    use_super_fast_mode = serializers.BooleanField(
        default=False, 
        required=False,
        help_text="Enable faster processing with potentially lower accuracy"
    )
    
    def validate_audio_file(self, value):
        """Validate audio file format and size"""
        # Check file size
        max_size = getattr(settings, 'MAX_AUDIO_FILE_SIZE', 10 * 1024 * 1024)
        if value.size > max_size:
            raise serializers.ValidationError(
                f'File too large. Maximum size is {max_size // (1024*1024)}MB. '
                f'Please compress your audio or use a shorter recording.'
            )
        
        # Check file format
        allowed_formats = getattr(settings, 'SUPPORTED_AUDIO_FORMATS', ['audio/wav', 'audio/mpeg', 'audio/mp4', 'audio/webm', 'audio/opus', 'audio/ogg'])
        if value.content_type not in allowed_formats:
            raise serializers.ValidationError(
                f'Unsupported audio format "{value.content_type}". '
                f'Please use one of: {", ".join(allowed_formats)}'
            )
        
        return value
    
    def validate_target_language(self, value):
        """Validate target language is supported"""
        try:
            language = LanguageSupport.objects.get(code=value)
            if not language.translation_supported:
                raise serializers.ValidationError(
                    f'Translation not supported for {language.name}. '
                    f'Check /api/voice/languages/ for supported languages.'
                )
        except LanguageSupport.DoesNotExist:
            raise serializers.ValidationError(
                f'Language code "{value}" not supported. '
                f'Use codes like "en", "es", "sw", etc. Check /api/voice/languages/ for all options.'
            )
        return value
    
    def validate_source_language(self, value):
        """Validate source language if specified"""
        if value and value != 'auto':
            try:
                language = LanguageSupport.objects.get(code=value)
                if not language.speech_to_text_supported:
                    raise serializers.ValidationError(
                        f'Speech-to-text not supported for {language.name}. '
                        f'Try "auto" for automatic detection or check /api/voice/languages/ for supported languages.'
                    )
            except LanguageSupport.DoesNotExist:
                raise serializers.ValidationError(
                    f'Language code "{value}" not supported. '
                    f'Use "auto" for detection or valid codes like "en", "es", "sw".'
                )
        return value


class VoiceTranslationResponseSerializer(serializers.Serializer):
    """Serializer for voice translation response"""
    
    success = serializers.BooleanField()
    translation_id = serializers.UUIDField(required=False)
    original_text = serializers.CharField(required=False)
    translated_text = serializers.CharField(required=False)
    original_language = serializers.CharField(required=False)
    target_language = serializers.CharField(required=False)
    confidence_score = serializers.FloatField(required=False)
    processing_time = serializers.FloatField(required=False)
    error = serializers.CharField(required=False)
    audio_available = serializers.BooleanField(required=False)
    original_audio_url = serializers.URLField(required=False, allow_null=True)
    translated_audio_url = serializers.URLField(required=False, allow_null=True)
    tts_note = serializers.CharField(required=False)
    steps = serializers.DictField(required=False)
    


class TranslationHistorySerializer(serializers.Serializer):
    """Serializer for translation history requests"""
    
    session_id = serializers.CharField(max_length=100, required=False)
    language_filter = serializers.CharField(max_length=10, required=False)
    date_from = serializers.DateTimeField(required=False)
    date_to = serializers.DateTimeField(required=False)
    limit = serializers.IntegerField(default=20, min_value=1, max_value=100)
    offset = serializers.IntegerField(default=0, min_value=0)


class TextTranslationRequestSerializer(serializers.Serializer):
    """Serializer for text-to-text translation request"""

    text = serializers.CharField(
        required=True,
        help_text="Text to translate."
    )
    target_language = serializers.CharField(
        max_length=10,
        help_text="Target language code (e.g., 'en' for English, 'es' for Spanish)."
    )
    source_language = serializers.CharField(
        max_length=10,
        default='auto',
        required=False,
        help_text="Source language code or 'auto' for automatic detection."
    )

    def validate_target_language(self, value):
        """Validate that the target language is supported for translation."""
        try:
            language = LanguageSupport.objects.get(code=value)
            if not language.translation_supported:
                raise serializers.ValidationError(
                    f'Translation is not supported for {language.name}.'
                )
        except LanguageSupport.DoesNotExist:
            raise serializers.ValidationError(
                f'Language code "{value}" is not supported.'
            )
        return value

    def validate_source_language(self, value):
        """Validate that the source language is supported if it's not 'auto'."""
        if value != 'auto':
            if not LanguageSupport.objects.filter(code=value).exists():
                raise serializers.ValidationError(
                    f'Language code "{value}" is not supported.'
                )
        return value


class TextTranslationResponseSerializer(serializers.ModelSerializer):
    """Serializer for the response of a text translation"""

    original_language_name = serializers.SerializerMethodField()
    target_language_name = serializers.SerializerMethodField()

    class Meta:
        model = Translation
        fields = (
            'id', 'original_text', 'translated_text', 'original_language',
            'target_language', 'original_language_name', 'target_language_name',
            'total_processing_time', 'date_created'
        )

    def get_original_language_name(self, obj):
        try:
            return LanguageSupport.objects.get(code=obj.original_language).name
        except LanguageSupport.DoesNotExist:
            return obj.original_language

    def get_target_language_name(self, obj):
        try:
            return LanguageSupport.objects.get(code=obj.target_language).name
        except LanguageSupport.DoesNotExist:
            return obj.target_language

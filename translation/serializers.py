from rest_framework import serializers
from .models import (
    TextTranslation, SpeechTranslation, ImageTranslation, 
    UserSettings, AudioFile, LanguageSupport
)

from .choices import SpeechServiceType

class LanguageSupportSerializer(serializers.ModelSerializer):
    class Meta:
        model = LanguageSupport
        fields = '__all__'


class UserSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserSettings
        fields = [
            'model', 'voice', 'autoplay', 'auto_detect_language',
            'super_fast_mode', 'source_language', 'target_language',
            'theme', 'audio_quality'
        ]
        read_only_fields = ['user']


class TextTranslationSerializer(serializers.ModelSerializer):
    class Meta:
        model = TextTranslation
        fields = [
            'id', 'title', 'mode', 'is_sms', 'original_language', 'target_language',
            'status', 'original_text', 'translated_text', 'original_file_url', 
            'translated_file_url', 'total_processing_time', 'date_created'
        ]
        read_only_fields = ['id', 'date_created', 'total_processing_time']

    def to_representation(self, instance):
        ret = super().to_representation(instance)
        # Filter fields based on mode for LIST/GET if needed, 
        # but keep text results as requested for consistency.
        if instance.mode == 'SHORT':
            ret.pop('original_file_url', None)
            ret.pop('translated_file_url', None)
        return ret

class SpeechTranslationSerializer(serializers.ModelSerializer):
    class Meta:
        model = SpeechTranslation
        fields = [
            'id', 'title', 'mode', 'speech_service', 'audio_format', 'duration',
            'original_audio_url', 'translated_audio_url', 'original_text', 
            'translated_text', 'status', 'original_language', 'target_language',
            'confidence_score', 'total_processing_time', 'date_created'
        ]
        read_only_fields = ['id', 'date_created', 'total_processing_time']

    def to_representation(self, instance):
        ret = super().to_representation(instance)
        # Ensure URLs are correctly populated from FileFields if URLFields are empty
        if not ret.get('original_audio_url') and instance.original_audio:
            try:
                ret['original_audio_url'] = instance.original_audio.url
            except ValueError:
                pass
        
        if not ret.get('translated_audio_url') and instance.translated_audio:
            try:
                ret['translated_audio_url'] = instance.translated_audio.url
            except ValueError:
                pass
                
        # The user wants original_text and translated_text to be present 
        # for STT and TTS regardless of mode.
        return ret

class ImageTranslationSerializer(serializers.ModelSerializer):
    class Meta:
        model = ImageTranslation
        fields = [
            'id', 'title', 'mode', 'original_image', 'original_image_url', 'ocr_text', 'translated_text',
            'status', 'original_language', 'target_language', 'total_processing_time', 
            'date_created'
        ]
        read_only_fields = ['id', 'date_created', 'total_processing_time']

# Patch Serializers (Only title allowed)
class TextTranslationTitleSerializer(serializers.ModelSerializer):
    class Meta:
        model = TextTranslation
        fields = ['title']

class SpeechTranslationTitleSerializer(serializers.ModelSerializer):
    class Meta:
        model = SpeechTranslation
        fields = ['title']

class ImageTranslationTitleSerializer(serializers.ModelSerializer):
    class Meta:
        model = ImageTranslation
        fields = ['title']

# Request Serializers
# Text Request Serializers
class TextShortRequestSerializer(serializers.Serializer):
    text = serializers.CharField(required=True)
    target_language = serializers.CharField(max_length=10, default='en')
    source_language = serializers.CharField(max_length=10, default='auto')
    is_sms = serializers.BooleanField(default=False)

class TextLargeRequestSerializer(serializers.Serializer):
    file = serializers.FileField(required=False, allow_null=True)
    original_file_url = serializers.URLField(required=False, allow_null=True)
    target_language = serializers.CharField(max_length=10, default='en')
    source_language = serializers.CharField(max_length=10, default='auto')
    title = serializers.CharField(max_length=255, required=False, allow_blank=True)

    def validate(self, data):
        if not data.get('file') and not data.get('original_file_url'):
            raise serializers.ValidationError("Either file or original_file_url is required for document translation")
        return data

# Speech Request Serializers
class SpeechShortRequestSerializer(serializers.Serializer):
    audio_file = serializers.FileField(required=False, allow_null=True)
    original_file_url = serializers.URLField(required=False, allow_null=True)
    target_language = serializers.CharField(max_length=10, default='en')
    source_language = serializers.CharField(max_length=10, default='auto')
    speech_service = serializers.ChoiceField(choices=SpeechServiceType.choices, default=SpeechServiceType.STS)

    def validate(self, data):
        if not data.get('audio_file') and not data.get('original_file_url'):
            raise serializers.ValidationError("Either audio_file or original_file_url is required")
        return data

class SpeechLargeRequestSerializer(serializers.Serializer):
    audio_file = serializers.FileField(required=False, allow_null=True)
    original_file_url = serializers.URLField(required=False, allow_null=True)
    target_language = serializers.CharField(max_length=10, default='en')
    source_language = serializers.CharField(max_length=10, default='auto')
    speech_service = serializers.ChoiceField(choices=SpeechServiceType.choices, default=SpeechServiceType.STS)
    title = serializers.CharField(max_length=255, required=False, allow_blank=True)

    def validate(self, data):
        if not data.get('audio_file') and not data.get('original_file_url'):
            raise serializers.ValidationError("Either audio_file or original_file_url is required")
        return data

class ImageTranslationRequestSerializer(serializers.Serializer):
    image = serializers.ImageField(required=True)
    target_language = serializers.CharField(max_length=10, default='en')
    source_language = serializers.CharField(max_length=10, default='auto')
class STTRequestSerializer(serializers.Serializer):
    audio_file = serializers.FileField(required=False, allow_null=True)
    source_language = serializers.CharField(max_length=10, default='auto')
    target_language = serializers.CharField(max_length=10, default='auto')
    session_id = serializers.CharField(required=False, allow_blank=True)
    original_file_url = serializers.URLField(required=False, allow_null=True)
    mode = serializers.ChoiceField(choices=['SHORT', 'LARGE'], default='SHORT')

    def validate(self, data):
        if not data.get('audio_file') and not data.get('original_file_url'):
            raise serializers.ValidationError("Either audio_file or original_file_url is required")
        return data

class TTSRequestSerializer(serializers.Serializer):
    text = serializers.CharField(required=True)
    source_language = serializers.CharField(max_length=10, default='en')
    target_language = serializers.CharField(max_length=10, default='en')
    voice = serializers.CharField(max_length=50, required=False, allow_null=True)
    session_id = serializers.CharField(required=False, allow_blank=True)
    mode = serializers.ChoiceField(choices=['SHORT', 'LARGE'], default='SHORT')


class UnifiedTranslationSerializer(serializers.Serializer):
    """Serializer that can handle any translation type"""
    def to_representation(self, instance):
        if isinstance(instance, TextTranslation):
            data = TextTranslationSerializer(instance, context=self.context).data
            data['type'] = 'text'
            return data
        elif isinstance(instance, SpeechTranslation):
            data = SpeechTranslationSerializer(instance, context=self.context).data
            data['type'] = 'speech'
            return data
        elif isinstance(instance, ImageTranslation):
            data = ImageTranslationSerializer(instance, context=self.context).data
            data['type'] = 'image'
            return data
        return {}

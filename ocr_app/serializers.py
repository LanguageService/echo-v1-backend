from rest_framework import serializers
from django.conf import settings
from .models import OCRResult


class OCRResultSerializer(serializers.ModelSerializer):
    """Serializer for OCR result data"""
    
    class Meta:
        model = OCRResult
        fields = [
            'id',
            'image',
            'image_url',
            'original_filename',
            'image_format',
            'original_text',
            'detected_language',
            'translated_text',
            'confidence_score',
            'processing_time',
            'date_created',
            'error_message'
        ]
        read_only_fields = [
            'id',
            'original_text',
            'detected_language',
            'translated_text',
            'confidence_score',
            'processing_time',
            'date_created',
            'error_message'
        ]


class ImageUploadSerializer(serializers.Serializer):
    """Serializer for image upload"""
    
    image = serializers.ImageField()
    
    def validate_image(self, value):
        """Validate image file"""
        
        # Check file size
        max_size = getattr(settings, 'MAX_IMAGE_FILE_SIZE', 10 * 1024 * 1024)
        if value.size > max_size:
            raise serializers.ValidationError(f"Image file too large. Maximum size is {max_size // (1024*1024)}MB.")
        
        # Check file format
        allowed_formats = getattr(settings, 'SUPPORTED_IMAGE_FORMATS', ['image/jpeg', 'image/png', 'image/jpg', 'image/bmp', 'image/tiff'])
        if value.content_type not in allowed_formats:
            format_names = [fmt.split('/')[1].upper() for fmt in allowed_formats]
            raise serializers.ValidationError(f"Unsupported image format '{value.content_type}'. Please use: {', '.join(format_names)}.")
        
        return value


class OCRProcessingResponseSerializer(serializers.Serializer):
    """Serializer for OCR processing response"""
    
    success = serializers.BooleanField()
    result_id = serializers.IntegerField(required=False)
    original_text = serializers.CharField(required=False)
    detected_language = serializers.CharField(required=False)
    language_name = serializers.CharField(required=False)
    translated_text = serializers.CharField(required=False)
    confidence_score = serializers.FloatField(required=False)
    processing_time = serializers.FloatField(required=False)
    word_count = serializers.IntegerField(required=False)
    error = serializers.CharField(required=False)

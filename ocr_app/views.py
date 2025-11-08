from rest_framework import status, permissions, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.conf import settings
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema, OpenApiExample, OpenApiResponse
import os
import tempfile
import logging

from .models import OCRResult
from .services import OCRTranslatorService
from .translation_services import TranslationProvider
from .translation_manager import translation_manager
from .serializers import (
    OCRResultSerializer,
    ImageUploadSerializer,
    OCRProcessingResponseSerializer
)
from utils.error_handler import ErrorHandler
from translation.cloud_storage import cloud_storage

logger = logging.getLogger(__name__)


@extend_schema(tags=['OCR Image Translation'])
class OcrViewSet(viewsets.ModelViewSet):
    """
    ViewSet for processing OCR images and managing results.
    """
    queryset = OCRResult.objects.all()
    serializer_class = OCRResultSerializer
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def get_queryset(self):
        """
        This view should return a list of all the OCR results
        for the currently authenticated user.
        """
        return OCRResult.objects.filter(user=self.request.user)

    @extend_schema(
        summary='Process Image through OCR Pipeline',
        description="""
         🖼️ **Extract text from images and translate it instantly!**
        
        Upload an image file and get the extracted text with automatic translation.
        """,
        request=ImageUploadSerializer,
        responses={
            201: OpenApiResponse(
                response=OCRProcessingResponseSerializer,
                description='Image processed successfully',
                examples=[
                    OpenApiExample(
                        'Successful Processing',
                        value={
                            'success': True,
                            'result_id': 1,
                            'original_text': 'Hello, how are you?',
                            'detected_language': 'en',
                            'language_name': 'English',
                            'translated_text': 'Hello, how are you?',
                            'confidence_score': 95.5,
                            'processing_time': 2.3,
                            'word_count': 4
                        }
                    )
                ]
            ),
            400: OpenApiResponse(description='Invalid image file'),
            401: OpenApiResponse(description='Authentication required'),
            500: OpenApiResponse(description='Internal server error')
        }
    )
    def create(self, request, *args, **kwargs):
        """
        🖼️ **Extract text from images and translate it instantly!**
        
        **AI-Powered OCR Pipeline:**
        1. **Google Gemini Vision AI**: Advanced text extraction from any image
        2. **Automatic Language Detection**: Identifies the language of extracted text
        3. **Instant Translation**: Translates to English using Gemini AI
        4. **Quality Metrics**: Confidence scores and processing analytics
        
        **📤 Upload Requirements:**
        - **Formats**: JPEG, PNG, BMP, TIFF (recommended: PNG for text clarity)
        - **Size**: Maximum 10MB per image
        - **Quality**: Higher resolution = better text extraction
        - **Text Size**: Minimum 12pt font for optimal results
        
        **💡 Pro Tips for Best Results:**
        - Use high-contrast images (dark text on light background)
        - Ensure text is straight and not rotated
        - Avoid blurry or low-resolution images
        - Screenshots of text work excellently
        - Handwritten text is supported but may have lower accuracy
        
        **🌍 Language Support:**
        - Detects 50+ languages automatically
        - Specialized support for African languages
        - Technical documents and multilingual content
        - Handwritten text in major languages
        
        **🚀 Integration Examples:**
        - Document scanning apps
        - Real-time translation of signs/menus
        - Digitizing printed materials
        - Accessibility tools for vision-impaired users
        """
        serializer = ImageUploadSerializer(data=request.data)
        if not serializer.is_valid():
            return ErrorHandler.handle_validation_error(
                serializer.errors,
                "Invalid image file"
            )

        image_file = serializer.validated_data['image']

        # Upload image to cloud storage before processing
        image_url = None
        original_filename = getattr(image_file, 'name', 'image_upload')
        image_format = original_filename.split('.')[-1].lower() if '.' in original_filename else 'jpg'
        
        # Import cloud storage service
        from translation.cloud_storage import cloud_storage

        # Note: We'll upload to cloud storage after OCR processing so we can use the detected language

        # Save the image to create OCR result record
        ocr_result = OCRResult.objects.create(
            user=request.user,
            image=image_file,
            original_filename=original_filename,
            image_format=image_format
        )

        # Get user's preferred translation service
        preferred_service = None
        if hasattr(request.user, 'profile') and request.user.profile.preferred_translation_service != 'auto':
            service_mapping = {
                'gemini': TranslationProvider.GEMINI,
                'openai': TranslationProvider.OPENAI,
                'anthropic': TranslationProvider.ANTHROPIC
            }
            preferred_service = service_mapping.get(request.user.profile.preferred_translation_service) if request.user.profile.preferred_translation_service else None

        # Process the image using OCR service with user's preferred translation service
        if preferred_service is not None:
            ocr_service = OCRTranslatorService(preferred_translation_service=preferred_service)
        else:
            ocr_service = OCRTranslatorService()
        processing_result = ocr_service.process_image(ocr_result.image.path, user=request.user, ocr_result_instance=ocr_result)

        # Upload image to cloud storage now that we know the detected language
        image_url = None
        if processing_result['success'] and cloud_storage.is_available():
            try:
                # Reset file position for upload
                image_file.seek(0)
                detected_language = processing_result['detected_language'] or 'unknown'
                image_url = cloud_storage.upload_image_input_file(
                    image_file, detected_language, str(request.user.id)
                )
                logger.info(f"Uploaded image to cloud storage: {image_url}")
            except Exception as e:
                logger.warning(f"Failed to upload image to cloud storage: {e}")

        # Update the database record
        ocr_result.original_text = processing_result['original_text']
        ocr_result.detected_language = processing_result['detected_language']
        ocr_result.translated_text = processing_result['translated_text']
        ocr_result.confidence_score = processing_result['confidence_score']
        ocr_result.processing_time = processing_result['processing_time']
        ocr_result.ocr_processing_time = processing_result.get('ocr_processing_time')
        ocr_result.language_detection_time = processing_result.get('language_detection_time')
        ocr_result.translation_processing_time = processing_result.get('translation_processing_time')
        ocr_result.translation_provider = processing_result.get('translation_provider', 'gemini_legacy')
        ocr_result.image_url = image_url

        if not processing_result['success']:
            ocr_result.error_message = processing_result['error_message']

        ocr_result.save()

        # Prepare response data
        response_data = {
            'success': processing_result['success'],
            'result_id': ocr_result.id,
            'original_text': processing_result['original_text'],
            'detected_language': processing_result['detected_language'],
            'language_name': processing_result['language_name'],
            'translated_text': processing_result['translated_text'],
            'confidence_score': processing_result['confidence_score'],
            'processing_time': processing_result['processing_time'],
            'word_count': processing_result['word_count'],
            'translation_provider': processing_result.get('translation_provider', 'gemini_legacy')
        }

        if not processing_result['success']:
            return ErrorHandler.format_error_response(
                "OCR processing failed",
                processing_result['error_message'],
                status.HTTP_200_OK
            )

        return ErrorHandler.success_response(
            response_data,
            "Image processed successfully",
            status_code=status.HTTP_201_CREATED
        )

    @extend_schema(
        summary='List OCR Results',
        description='Get paginated list of all OCR processing results for the authenticated user',
        responses={
            200: OpenApiResponse(
                description='List of OCR results',
                examples=[
                    OpenApiExample(
                        'OCR Results List',
                        value={
                            'count': 25,
                            'results': [
                                {
                                    'id': 1,
                                    'original_text': 'Sample extracted text',
                                    'detected_language': 'en',
                                    'translated_text': 'Sample extracted text',
                                    'confidence_score': 95.0,
                                    'processing_time': 1.5
                                }
                            ]
                        }
                    )
                ]
            ),
            401: OpenApiResponse(description='Authentication required')
        }
    )
    def list(self, request, *args, **kwargs):
        """
        List all OCR processing results for the authenticated user.
        """
        # Get query parameters
        limit = int(request.GET.get('limit', 10))
        offset = int(request.GET.get('offset', 0))
        
        # Validate parameters
        limit = min(limit, 100)  # Max 100 results
        offset = max(offset, 0)  # Min 0
        
        queryset = self.get_queryset()
        total_count = queryset.count()
        results = queryset[offset:offset + limit]
        
        serializer = self.get_serializer(results, many=True)
        
        return ErrorHandler.success_response({
            'count': total_count,
            'results': serializer.data
        }, "Results retrieved successfully")
        
    @extend_schema(
        summary='Get OCR Result by ID',
        description='Retrieve a specific OCR processing result by its ID',
        responses={
            200: OCRResultSerializer,
            404: OpenApiResponse(description='Result not found'),
            401: OpenApiResponse(description='Authentication required')
        }
    )
    def retrieve(self, request, *args, **kwargs):
        """
        Retrieve a specific OCR result.
        """
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return ErrorHandler.success_response(serializer.data, "Result retrieved successfully")

    @extend_schema(
        summary='Delete OCR Result',
        description='Delete a specific OCR processing result and its associated image file',
        responses={
            204: OpenApiResponse(description='Result deleted successfully'),
            404: OpenApiResponse(description='Result not found'),
            401: OpenApiResponse(description='Authentication required')
        }
    )
    def destroy(self, request, *args, **kwargs):
        """
        Delete an OCR result.
        """
        instance = self.get_object()
        # Delete the image file if it exists
        if instance.image and default_storage.exists(instance.image.name):
            default_storage.delete(instance.image.name)
        self.perform_destroy(instance)
        return ErrorHandler.success_response(
            {},
            "Result deleted successfully",
            status_code=status.HTTP_204_NO_CONTENT
        )

    @extend_schema(
        summary='Get Translation Services Status',
        description='Get the status and availability of all translation service providers',
        responses={
            200: OpenApiResponse(description='Translation services status information'),
            401: OpenApiResponse(description='Authentication required')
        }
    )
    @action(detail=False, methods=['get'], url_path='translation-services')
    def translation_services_status(self, request):
        """
        Get status and availability of translation service providers.
        """
        status_info = translation_manager.get_service_status()
        available_services = translation_manager.get_available_services()
        supported_languages = translation_manager.get_all_supported_languages()
        
        # Get user's current preference
        user_preference = 'auto'
        if hasattr(request.user, 'profile') and request.user.profile.preferred_translation_service:
            user_preference = request.user.profile.preferred_translation_service
        
        response_data = {
            'success': True,
            'available_services': [service.value for service in available_services],
            'service_status': status_info,
            'supported_languages': supported_languages,
            'user_preference': user_preference,
            'total_services': len(status_info),
            'active_services': len(available_services)
        }
        
        return ErrorHandler.success_response(
            response_data,
            "Translation services status retrieved successfully"
        )
        

@extend_schema(tags=['OCR Health Check'])
class HealthCheckViewSet(viewsets.ViewSet):
    permission_classes = [permissions.AllowAny]

    @action(detail=False, methods=['get'], url_path='health')
    def health_check(self, request):
        """
        Health check endpoint
        """
        return Response({
            'status': 'healthy',
            'service': 'OCR Translator API',
            'version': '1.0.0'
        }, status=status.HTTP_200_OK)

    @action(detail=False, methods=['get'], url_path='info')
    def api_info(self, request):
        """
        API information endpoint
        """
        return Response({
            'name': 'OCR Translator API',
            'description': 'Extract text from images, detect language, and translate to English',
            'version': '1.0.0',
            'endpoints': {
                'process': 'POST /api/ocr/ - Process image through OCR pipeline',
                'results': 'GET /api/ocr/ - List all results',
                'result': 'GET /api/ocr/{id}/ - Get specific result',
                'delete': 'DELETE /api/ocr/{id}/ - Delete result',
                'health': 'GET /api/health/ - Health check'
            },
            'supported_formats': [fmt.split('/')[1].upper() for fmt in getattr(settings, 'SUPPORTED_IMAGE_FORMATS', ['image/jpeg', 'image/png', 'image/bmp', 'image/tiff'])],
            'max_file_size': f"{getattr(settings, 'MAX_IMAGE_FILE_SIZE', 10 * 1024 * 1024) // (1024*1024)}MB"
        }, status=status.HTTP_200_OK)

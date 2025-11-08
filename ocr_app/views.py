from rest_framework import status, permissions
from rest_framework.decorators import api_view, parser_classes, permission_classes
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.conf import settings
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
from voice_translator.cloud_storage import cloud_storage

logger = logging.getLogger(__name__)


@extend_schema(
    tags=['OCR Image Translation'],
    summary='Process Image through OCR Pipeline',
    description="""
    🖼️ **Extract text from images and translate it instantly!**
    
    Upload an image file and get the extracted text with automatic translation.
    """,
    request=ImageUploadSerializer,
    responses={
        200: OpenApiResponse(
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
@api_view(['POST'])
@parser_classes([MultiPartParser, FormParser])
@permission_classes([permissions.IsAuthenticated])
def process_image(request):
    """
    🖼️ **Extract text from images and translate it instantly!**
    
    **AI-Powered OCR Pipeline:**
    1. **Google Gemini Vision AI**: Advanced text extraction from any image
    2. **Automatic Language Detection**: Identifies the language of extracted text
    3. **Instant Translation**: Translates to English using Gemini AI
    4. **Quality Metrics**: Confidence scores and processing analytics
    
    POST /api/process/
    Content-Type: multipart/form-data
    
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
    
    **📊 Response Format:**
    {
        "success": true,
        "result_id": 1,
        "original_text": "extracted text",
        "detected_language": "es",
        "language_name": "Spanish", 
        "translated_text": "translated text",
        "confidence_score": 85.5,
        "processing_time": 2.34,
        "word_count": 10
    }
    
    **🚀 Integration Examples:**
    - Document scanning apps
    - Real-time translation of signs/menus
    - Digitizing printed materials
    - Accessibility tools for vision-impaired users
    """
    try:
        # Validate input
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
        from voice_translator.cloud_storage import cloud_storage
        
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
            "Image processed successfully"
        )
        
    except Exception as e:
        return ErrorHandler.handle_generic_error(e, "image processing")


@extend_schema(
    tags=['OCR Image Translation'],
    summary='Get OCR Result by ID',
    description='Retrieve a specific OCR processing result by its ID',
    responses={
        200: OCRResultSerializer,
        404: OpenApiResponse(description='Result not found'),
        401: OpenApiResponse(description='Authentication required')
    }
)
@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
@extend_schema(
    tags=['OCR Image Translation'])
def get_result(request, result_id):
    """
    Get OCR processing result by ID
    
    GET /api/results/{result_id}/
    
    Returns:
    {
        "id": 1,
        "image": "/media/ocr_images/image.jpg",
        "original_text": "extracted text",
        "detected_language": "es",
        "translated_text": "translated text",
        "confidence_score": 85.5,
        "processing_time": 2.34,
        "created_at": "2025-08-26T20:00:00Z",
        "error_message": null
    }
    """
    try:
        ocr_result = OCRResult.objects.get(id=result_id, user=request.user)
        serializer = OCRResultSerializer(ocr_result)
        return ErrorHandler.success_response(serializer.data, "Result retrieved successfully")
        
    except OCRResult.DoesNotExist:
        return ErrorHandler.handle_not_found_error("OCR result")


@extend_schema(
    tags=['OCR Image Translation'],
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
@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
@extend_schema(
    tags=['OCR Image Translation'])
def list_results(request):
    """
    List all OCR processing results
    
    GET /api/results/
    
    Query parameters:
    - limit: Number of results to return (default: 10)
    - offset: Number of results to skip (default: 0)
    
    Returns:
    {
        "count": 25,
        "results": [
            {
                "id": 1,
                "image": "/media/ocr_images/image.jpg",
                "original_text": "extracted text",
                "detected_language": "es",
                "translated_text": "translated text",
                "confidence_score": 85.5,
                "processing_time": 2.34,
                "created_at": "2025-08-26T20:00:00Z",
                "error_message": null
            }
        ]
    }
    """
    try:
        # Get query parameters
        limit = int(request.GET.get('limit', 10))
        offset = int(request.GET.get('offset', 0))
        
        # Validate parameters
        limit = min(limit, 100)  # Max 100 results
        offset = max(offset, 0)  # Min 0
        
        # Get results for authenticated user
        results = OCRResult.objects.filter(user=request.user, user__isnull=False)[offset:offset + limit]
        total_count = OCRResult.objects.filter(user=request.user, user__isnull=False).count()
        
        serializer = OCRResultSerializer(results, many=True)
        
        return ErrorHandler.success_response({
            'count': total_count,
            'results': serializer.data
        }, "Results retrieved successfully")
        
    except ValueError:
        return ErrorHandler.format_error_response(
            "Invalid parameters",
            "Limit and offset must be valid integers"
        )


@extend_schema(
    tags=['OCR Image Translation'],
    summary='Delete OCR Result',
    description='Delete a specific OCR processing result and its associated image file',
    responses={
        204: OpenApiResponse(description='Result deleted successfully'),
        404: OpenApiResponse(description='Result not found'),
        401: OpenApiResponse(description='Authentication required')
    }
)
@api_view(['DELETE'])
@permission_classes([permissions.IsAuthenticated])
@extend_schema(
    tags=['OCR Image Translation'])
def delete_result(request, result_id):
    """
    Delete OCR processing result by ID
    
    DELETE /api/results/{result_id}/
    
    Returns:
    {
        "success": true,
        "message": "Result deleted successfully"
    }
    """
    try:
        ocr_result = OCRResult.objects.get(id=result_id, user=request.user)
        
        # Delete the image file if it exists
        if ocr_result.image and default_storage.exists(ocr_result.image.name):
            default_storage.delete(ocr_result.image.name)
        
        ocr_result.delete()
        
        return ErrorHandler.success_response(
            {},
            "Result deleted successfully"
        )
        
    except OCRResult.DoesNotExist:
        return ErrorHandler.handle_not_found_error("OCR result")
    except Exception as e:
        return ErrorHandler.handle_generic_error(e, "result deletion")


@api_view(['GET'])
@permission_classes([permissions.AllowAny])
@extend_schema(
    tags=['Health Check'])
def health_check(request):
    """
    Health check endpoint
    
    GET /api/health/
    
    Returns:
    {
        "status": "healthy",
        "service": "OCR Translator API",
        "version": "1.0.0"
    }
    """
    return Response({
        'status': 'healthy',
        'service': 'OCR Translator API',
        'version': '1.0.0'
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([permissions.AllowAny])
@extend_schema(
    tags=['API Info'])
def api_info(request):
    """
    API information endpoint
    
    GET /api/
    
    Returns:
    {
        "name": "OCR Translator API",
        "description": "Extract text from images, detect language, and translate to English",
        "version": "1.0.0",
        "endpoints": {
            "process": "POST /api/process/ - Process image through OCR pipeline",
            "results": "GET /api/results/ - List all results",
            "result": "GET /api/results/{id}/ - Get specific result",
            "delete": "DELETE /api/results/{id}/ - Delete result",
            "health": "GET /api/health/ - Health check"
        }
    }
    """
    return Response({
        'name': 'OCR Translator API',
        'description': 'Extract text from images, detect language, and translate to English',
        'version': '1.0.0',
        'endpoints': {
            'process': 'POST /api/process/ - Process image through OCR pipeline',
            'results': 'GET /api/results/ - List all results',
            'result': 'GET /api/results/{id}/ - Get specific result',
            'delete': 'DELETE /api/results/{id}/ - Delete result',
            'health': 'GET /api/health/ - Health check'
        },
        'supported_formats': [fmt.split('/')[1].upper() for fmt in getattr(settings, 'SUPPORTED_IMAGE_FORMATS', ['image/jpeg', 'image/png', 'image/bmp', 'image/tiff'])],
        'max_file_size': f"{getattr(settings, 'MAX_IMAGE_FILE_SIZE', 10 * 1024 * 1024) // (1024*1024)}MB"
    }, status=status.HTTP_200_OK)


@extend_schema(
    tags=['OCR Image Translation'],
    summary='Get Translation Services Status',
    description='Get the status and availability of all translation service providers',
    responses={
        200: OpenApiResponse(description='Translation services status information'),
        401: OpenApiResponse(description='Authentication required')
    }
)
@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def translation_services_status(request):
    """
    Get status and availability of translation service providers
    
    GET /api/translation-services/
    
    Returns information about available translation services, their status,
    and supported languages.
    """
    try:
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
        
    except Exception as e:
        return ErrorHandler.handle_generic_error(e, "translation services status")

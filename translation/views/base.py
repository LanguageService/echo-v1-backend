"""
Text Translation API Views

REST API endpoints for the Speak Africa voice translation application.
"""

import logging

from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView
from django.conf import settings
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiExample, OpenApiResponse
from drf_spectacular.types import OpenApiTypes

from ..models import Translation, UserSettings, LanguageSupport
from ..serializers import (
     UserSettingsSerializer, LanguageSupportSerializer,

)

logger = logging.getLogger(__name__)



@extend_schema(tags=["Users Settings"])
class UserSettingsAPIView(APIView):
    """Endpoint for user settings management"""
    
    permission_classes = [IsAuthenticated]
    
    def get(self, request, *args, **kwargs):
        """Get user settings"""
        try:
            try:
                settings = UserSettings.objects.get(user=request.user)
                serializer = UserSettingsSerializer(settings)
                return Response(serializer.data, status=status.HTTP_200_OK)
            except UserSettings.DoesNotExist:
                # Return default settings
                default_settings = {
                    'model': 'gemini-2.5-flash',
                    'voice': 'Zephyr',
                    'autoplay': False,
                    'auto_detect_language': True,
                    'super_fast_mode': False,
                    'source_language': 'auto',
                    'target_language': 'en',
                    'theme': 'african',
                    'audio_quality': 'high'
                }
                return Response(default_settings, status=status.HTTP_200_OK)
                
        except Exception as e:
            logger.error(f"Error retrieving settings: {str(e)}")
            return Response({
                'error': f'Failed to retrieve settings: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @extend_schema(
        tags=['Voice Translation Settings'],
        summary='Update User Settings',
        description='Update voice translation settings for the authenticated user',
        request=UserSettingsSerializer,
        responses={
            200: UserSettingsSerializer,
            400: OpenApiResponse(description='Invalid settings data'),
            401: OpenApiResponse(description='Authentication required'),
            500: OpenApiResponse(description='Internal server error')
        },
        examples=[
            OpenApiExample(
                'Update Settings',
                value={
                    'model': 'gemini-2.5-flash',
                    'voice': 'Zephyr',
                    'autoplay': True,
                    'auto_detect_language': True,
                    'super_fast_mode': False,
                    'source_language': 'en',
                    'target_language': 'sw',
                    'theme': 'african',
                    'audio_quality': 'high'
                }
            )
        ]
    )
    def post(self, request, *args, **kwargs):
        """Update user settings"""
        try:
            serializer = UserSettingsSerializer(data=request.data)
            if not serializer.is_valid():
                return Response({
                    'error': 'Invalid settings data',
                    'details': serializer.errors
                }, status=status.HTTP_400_BAD_REQUEST)
            
            settings = serializer.save(user=request.user)
            return Response(serializer.data, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error updating settings: {str(e)}")
            return Response({
                'error': f'Failed to update settings: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@extend_schema(tags=["Language Support Settings"])
class LanguageSupportAPIView(APIView):
    """Endpoint for supported languages information"""
    
    permission_classes = [AllowAny]
    
    @extend_schema(
        parameters=[
            OpenApiParameter(name='african_only', description='Filter for African languages.', type=OpenApiTypes.BOOL),
            OpenApiParameter(name='stt_supported', description='Filter for languages that support Speech-to-Text.', type=OpenApiTypes.BOOL),
            OpenApiParameter(name='tts_supported', description='Filter for languages that support Text-to-Speech.', type=OpenApiTypes.BOOL),
            OpenApiParameter(name='translation_supported', description='Filter for languages that support translation.', type=OpenApiTypes.BOOL),
            OpenApiParameter(name='text_to_text_supported', description='Filter for languages that support text-to-text translation.', type=OpenApiTypes.BOOL),
        ],
        responses={
            200: OpenApiResponse(
                description='A list of supported languages.',
                response=LanguageSupportSerializer(many=True)
            )
        }
    )
    def get(self, request, *args, **kwargs):
        """Get list of supported languages"""
        try:
            # Filter parameters
            african_only = request.query_params.get('african_only', '').lower() == 'true'
            stt_supported = request.query_params.get('stt_supported', '').lower() == 'true'
            tts_supported = request.query_params.get('tts_supported', '').lower() == 'true'
            translation_supported = request.query_params.get('translation_supported', '').lower() == 'true'
            text_to_text_supported = request.query_params.get('text_to_text_supported', '').lower() == 'true'
            
            # Build queryset
            queryset = LanguageSupport.objects.all()
            
            if african_only:
                queryset = queryset.filter(is_african_language=True)
            if stt_supported:
                queryset = queryset.filter(speech_to_text_supported=True)
            if tts_supported:
                queryset = queryset.filter(text_to_speech_supported=True)
            if translation_supported:
                queryset = queryset.filter(translation_supported=True)
            if text_to_text_supported:
                queryset = queryset.filter(text_to_text_supported=True)
            
            serializer = LanguageSupportSerializer(queryset, many=True)
            
            return Response({
                'count': queryset.count(),
                'languages': serializer.data
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error retrieving supported languages: {str(e)}")
            return Response({
                'error': f'Failed to retrieve languages: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@extend_schema(tags=["Health Check"])
class HealthCheckAPIView(APIView):
    """Health check endpoint for the voice translation service"""
    
    permission_classes = [AllowAny]
    
    def get(self, request, *args, **kwargs):
        """Health check endpoint"""
        try:
            # Check database connectivity
            translation_count = Translation.objects.count()
            settings_count = UserSettings.objects.count()
            language_count = LanguageSupport.objects.count()
            
            return Response({
                'status': 'healthy',
                'service': 'Speak Africa Voice Translation API',
                'version': '1.0.0',
                'statistics': {
                    'total_translations': translation_count,
                    'user_sessions': settings_count,
                    'supported_languages': language_count
                }
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Health check failed: {str(e)}")
            return Response({
                'status': 'unhealthy',
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@extend_schema(tags=["API Info"])
class APIInfoView(APIView):
    """API information and documentation endpoint"""
    
    permission_classes = [AllowAny]
    
    def get(self, request, *args, **kwargs):
        """API information endpoint"""
        return Response({
            'name': 'Speak Africa Voice Translation API',
            'description': 'Comprehensive voice translation API supporting bidirectional translation between English and African languages',
            'version': '1.0.0',
            'features': [
                'Speech-to-text transcription',
                'Text translation with Gemini AI',
                'Text-to-speech synthesis',
                'Multi-language support',
                'African language specialization',
                'Translation history',
                'User preferences'
            ],
            'endpoints': {
                'translate': 'POST /api/voice/translate - Process voice translation',
                'translations': 'GET /api/voice/translations - Get translation history',
                'translation_detail': 'GET/DELETE /api/voice/translations/{id} - Manage specific translation',
                'settings': 'GET/POST /api/voice/settings - Manage user settings',
                'languages': 'GET /api/voice/languages - Get supported languages',
                'health': 'GET /api/voice/health - Health check',
                'info': 'GET /api/voice/ - API information'
            },
            'supported_languages': {
                'african_languages': ['Kinyarwanda', 'Swahili', 'Amharic', 'Yoruba', 'Hausa', 'Igbo', 'Zulu', 'Xhosa', 'Afrikaans', 'Somali'],
                'world_languages': ['English', 'Spanish', 'French', 'German', 'Chinese', 'Japanese', 'Korean', 'Arabic', 'Hindi', 'Portuguese', 'Russian', 'Italian']
            },
            'audio_formats': [fmt.split('/')[1].upper() for fmt in getattr(settings, 'SUPPORTED_AUDIO_FORMATS', ['audio/wav', 'audio/mpeg', 'audio/mp4', 'audio/webm', 'audio/opus', 'audio/ogg'])],
            'max_file_size': f"{getattr(settings, 'MAX_AUDIO_FILE_SIZE', 10 * 1024 * 1024) // (1024*1024)}MB"
        }, status=status.HTTP_200_OK)



class TaskStatusAPIView(APIView):
    """API endpoint for checking background task status"""
    
    permission_classes = [IsAuthenticated]
    
    @extend_schema(
        tags=['Voice Translation (Background)'],
        summary='Check Background Task Status',
        description='Check the status and results of a background voice translation task'
    )
    def get(self, request, task_id, *args, **kwargs):
        """
        Check status of background translation task
        """
        try:
            from celery.result import AsyncResult
            
            # Get task result
            task_result = AsyncResult(task_id)
            
            if task_result.state == 'PENDING':
                response = {
                    'task_id': task_id,
                    'status': 'pending',
                    'message': 'Task is waiting to be processed'
                }
            elif task_result.state == 'PROGRESS':
                response = {
                    'task_id': task_id,
                    'status': 'processing',
                    'message': 'Task is currently being processed',
                    'progress': task_result.info
                }
            elif task_result.state == 'SUCCESS':
                response = {
                    'task_id': task_id,
                    'status': 'completed',
                    'message': 'Task completed successfully',
                    'result': task_result.result
                }
            else:  # FAILURE
                response = {
                    'task_id': task_id,
                    'status': 'failed',
                    'message': 'Task failed',
                    'error': str(task_result.info)
                }
            
            return Response(response, status=status.HTTP_200_OK)
                
        except Exception as e:
            logger.error(f"Error checking task status: {str(e)}")
            return Response({
                'task_id': task_id,
                'status': 'error',
                'error': f'Failed to check task status: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

"""
Voice Translation API Views

REST API endpoints for the Speak Africa voice translation application.
"""

import logging
import uuid
import time
from django.http import JsonResponse, Http404
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.db import models
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from django.conf import settings
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiExample, OpenApiResponse
from drf_spectacular.types import OpenApiTypes

from .models import Translation, UserSettings, LanguageSupport
from .serializers import (
    TranslationSerializer, UserSettingsSerializer, LanguageSupportSerializer,
    VoiceTranslationRequestSerializer, VoiceTranslationResponseSerializer,
    TranslationHistorySerializer
)
from .services import VoiceTranslationService, AsyncVoiceTranslationService
from utils.error_handler import ErrorHandler

logger = logging.getLogger(__name__)



class VoiceTranslationAPIView(APIView):
    """Main endpoint for voice translation processing"""
    
    permission_classes = [IsAuthenticated]
    
    @extend_schema(
        tags=['Voice Translation'],
        summary='Process Voice Translation',
        description='''
        Process voice translation from audio file to text and translate to target language.
        
        **How to use:**
        1. Upload an audio file (WAV, MP3, MP4, WebM, OPUS formats supported)
        2. Specify target language code (e.g., 'en' for English, 'es' for Spanish)
        3. **Optional**: Provide session_id to group related translations (useful for conversations)
        4. **Optional**: Specify source_language (default: auto-detect)
        
        **About Session ID:**
        - Session ID is optional - each user's translations are automatically linked to their account
        - Use session_id to group related translations (e.g., parts of a conversation)
        - If not provided, a unique session will be created automatically
        
        **Supported Languages:**
        - English (en), Spanish (es), French (fr), German (de), Italian (it)
        - African Languages: Swahili (sw), Kinyarwanda (rw), Yoruba (yo), Hausa (ha)
        - And many more - check /api/voice/languages/ for full list
        
        **File Requirements:**
        - Max size: 10MB
        - Formats: WAV, MP3, MP4, WebM, OPUS
        - Duration: Recommended under 5 minutes for best results
        ''',
        request=VoiceTranslationRequestSerializer,
        responses={
            200: OpenApiResponse(
                response=VoiceTranslationResponseSerializer,
                description='Translation processed successfully',
                examples=[
                    OpenApiExample(
                        'Successful Translation',
                        value={
                            'success': True,
                            'translation_id': 'a1b2c3d4-e5f6-7890-abcd-ef1234567890',
                            'original_text': 'Hello, how are you?',
                            'translated_text': 'Hola, ¿cómo estás?',
                            'original_language': 'en',
                            'target_language': 'es',
                            'confidence_score': 0.95,
                            'processing_time': 2.3,
                            'audio_available': True,
                            'steps': {
                                'speech_to_text': 'completed',
                                'translation': 'completed', 
                                'text_to_speech': 'completed'
                            }
                        }
                    )
                ]
            ),
            400: OpenApiResponse(
                description='Invalid request data',
                examples=[
                    OpenApiExample(
                        'Validation Error',
                        value={
                            'success': False,
                            'error': 'Invalid request data',
                            'details': {
                                'audio_file': ['This field is required.'],
                                'target_language': ['Language "xyz" not supported']
                            }
                        }
                    )
                ]
            ),
            401: OpenApiResponse(description='Authentication required'),
            500: OpenApiResponse(
                description='Internal server error',
                examples=[
                    OpenApiExample(
                        'Server Error',
                        value={
                            'success': False,
                            'error': 'Internal server error: Unable to process audio file'
                        }
                    )
                ]
            )
        },
        examples=[
            OpenApiExample(
                'Basic Translation Request',
                description='Simple audio translation from any language to English',
                value={
                    'target_language': 'en',
                    'source_language': 'auto'
                }
            ),
            OpenApiExample(
                'African Language Translation',
                description='Translate to Swahili with session tracking',
                value={
                    'target_language': 'sw',
                    'source_language': 'en',
                    'session_id': 'my-session-123',
                    'use_super_fast_mode': True
                }
            )
        ]
    )
    def post(self, request, *args, **kwargs):
        """
        Process voice translation request
        
        Accepts audio file and returns transcription + translation
        """
        try:
            # Validate request data
            serializer = VoiceTranslationRequestSerializer(data=request.data)
            if not serializer.is_valid():
                return Response({
                    'success': False,
                    'error': 'Invalid request data',
                    'details': serializer.errors
                }, status=status.HTTP_400_BAD_REQUEST)
            
            validated_data = serializer.validated_data
            
            # Get or create session ID
            session_id = validated_data.get('session_id') or str(uuid.uuid4())
            
            # Initialize translation service
            translation_service = VoiceTranslationService()
            
            # Process the voice translation
            result = translation_service.process_voice_translation(
                user=request.user,
                audio_file=validated_data['audio_file'],
                session_id=session_id,
                target_language=validated_data['target_language']
            )
            
            # Prepare response
            response_serializer = VoiceTranslationResponseSerializer(data=result)
            if response_serializer.is_valid():
                return Response(response_serializer.data, status=status.HTTP_200_OK)
            else:
                return Response(result, status=status.HTTP_200_OK)
                
        except Exception as e:
            logger.error(f"Error in voice translation API: {str(e)}")
            return Response({
                'success': False,
                'error': f'Internal server error: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@extend_schema(tags=["Voice Translation History"])
class TranslationHistoryAPIView(APIView):
    """Endpoint for retrieving translation history"""
    
    permission_classes = [IsAuthenticated]
    
    def get(self, request, *args, **kwargs):
        """Get translation history with optional filtering"""
        try:
            # Validate query parameters
            query_serializer = TranslationHistorySerializer(data=request.query_params)
            if not query_serializer.is_valid():
                return Response({
                    'error': 'Invalid query parameters',
                    'details': query_serializer.errors
                }, status=status.HTTP_400_BAD_REQUEST)
            
            params = query_serializer.validated_data
            
            # Build queryset for authenticated user
            queryset = Translation.objects.filter(user=request.user, user__isnull=False)
            
            # Apply filters
            if params.get('session_id'):
                queryset = queryset.filter(session_id=params['session_id'])
            
            if params.get('language_filter'):
                lang_filter = params['language_filter']
                queryset = queryset.filter(
                    models.Q(original_language=lang_filter) | 
                    models.Q(target_language=lang_filter)
                )
            
            if params.get('date_from'):
                queryset = queryset.filter(created_at__gte=params['date_from'])
            
            if params.get('date_to'):
                queryset = queryset.filter(created_at__lte=params['date_to'])
            
            # Apply pagination
            offset = params.get('offset', 0)
            limit = params.get('limit', 20)
            
            total_count = queryset.count()
            translations = queryset[offset:offset + limit]
            
            # Serialize results
            serializer = TranslationSerializer(translations, many=True, context={'request': request})
            
            return Response({
                'count': total_count,
                'offset': offset,
                'limit': limit,
                'results': serializer.data
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error retrieving translation history: {str(e)}")
            return Response({
                'error': f'Failed to retrieve history: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@extend_schema(tags=["Voice Translation History"])
class TranslationDetailAPIView(APIView):
    """Endpoint for individual translation details"""
    
    permission_classes = [IsAuthenticated]
    
    def get(self, request, translation_id, *args, **kwargs):
        """Get specific translation by ID"""
        try:
            translation = get_object_or_404(Translation, id=translation_id, user=request.user)
            serializer = TranslationSerializer(translation, context={'request': request})
            return Response(serializer.data, status=status.HTTP_200_OK)
            
        except Http404:
            return Response({
                'error': 'Translation not found'
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Error retrieving translation {translation_id}: {str(e)}")
            return Response({
                'error': f'Failed to retrieve translation: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def delete(self, request, translation_id, *args, **kwargs):
        """Delete specific translation by ID"""
        try:
            translation = get_object_or_404(Translation, id=translation_id, user=request.user)
            translation.delete()
            
            return Response({
                'success': True,
                'message': 'Translation deleted successfully'
            }, status=status.HTTP_200_OK)
            
        except Http404:
            return Response({
                'error': 'Translation not found'
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Error deleting translation {translation_id}: {str(e)}")
            return Response({
                'error': f'Failed to delete translation: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


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
    
    def get(self, request, *args, **kwargs):
        """Get list of supported languages"""
        try:
            # Filter parameters
            african_only = request.query_params.get('african_only', '').lower() == 'true'
            stt_supported = request.query_params.get('stt_supported', '').lower() == 'true'
            tts_supported = request.query_params.get('tts_supported', '').lower() == 'true'
            translation_supported = request.query_params.get('translation_supported', '').lower() == 'true'
            
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



# Async API Views for improved performance
@extend_schema(tags=["Voice Translation"])
class AsyncVoiceTranslationAPIView(APIView):
    """Async version of voice translation endpoint for improved performance"""
    
    permission_classes = [IsAuthenticated]
    
    @extend_schema(
        tags=['Voice Translation (Async)'],
        summary='Process Voice Translation (Async)',
        description='''
        Process voice translation from audio file to text and translate to target language using async processing.
        
        **Performance Benefits:**
        - Concurrent processing of translation steps
        - Non-blocking I/O operations
        - Better resource utilization
        - Faster response times for multiple requests
        
        **How to use:**
        1. Upload an audio file (WAV, MP3, MP4, WebM, OPUS formats supported)
        2. Specify target language code (e.g., 'en' for English, 'es' for Spanish)
        3. **Optional**: Provide session_id to group related translations (useful for conversations)
        4. **Optional**: Specify source_language (default: auto-detect)
        
        **About Session ID:**
        - Session ID is optional - each user's translations are automatically linked to their account
        - Use session_id to group related translations (e.g., parts of a conversation)
        - If not provided, a unique session will be created automatically
        
        **Supported Languages:**
        - English (en), Spanish (es), French (fr), German (de), Italian (it)
        - African Languages: Swahili (sw), Kinyarwanda (rw), Yoruba (yo), Hausa (ha)
        - And many more - check /api/voice/languages/ for full list
        
        **File Requirements:**
        - Max size: 10MB
        - Formats: WAV, MP3, MP4, WebM, OPUS
        - Duration: Recommended under 5 minutes for best results
        ''',
        request=VoiceTranslationRequestSerializer,
        responses={
            200: OpenApiResponse(
                response=VoiceTranslationResponseSerializer,
                description='Translation processed successfully (async)',
                examples=[
                    OpenApiExample(
                        'Successful Async Translation',
                        value={
                            'success': True,
                            'translation_id': 'a1b2c3d4-e5f6-7890-abcd-ef1234567890',
                            'original_text': 'Hello, how are you?',
                            'translated_text': 'Hola, ¿cómo estás?',
                            'original_language': 'en',
                            'target_language': 'es',
                            'confidence_score': 0.95,
                            'processing_time': 1.8,
                            'audio_available': True,
                            'steps': {
                                'speech_to_text': 'completed',
                                'translation': 'completed', 
                                'text_to_speech': 'completed'
                            },
                            'async_note': 'Processed with concurrent async operations'
                        }
                    )
                ]
            ),
            400: OpenApiResponse(description='Invalid request data'),
            401: OpenApiResponse(description='Authentication required'),
            500: OpenApiResponse(description='Internal server error')
        }
    )
    async def post(self, request, *args, **kwargs):
        """
        Process voice translation request asynchronously
        
        Uses async services for improved performance and concurrency
        """
        try:
            # Validate request data
            serializer = VoiceTranslationRequestSerializer(data=request.data)
            if not serializer.is_valid():
                return Response({
                    'success': False,
                    'error': 'Invalid request data',
                    'details': serializer.errors
                }, status=status.HTTP_400_BAD_REQUEST)
            
            validated_data = serializer.validated_data
            
            # Get or create session ID
            session_id = validated_data.get('session_id') or str(uuid.uuid4())
            
            # Initialize async translation service
            async_translation_service = AsyncVoiceTranslationService()
            
            # Process the voice translation asynchronously
            result = await async_translation_service.process_voice_translation(
                user=request.user,
                audio_file=validated_data['audio_file'],
                session_id=session_id,
                target_language=validated_data['target_language']
            )
            
            # Add async processing note
            result['async_note'] = 'Processed with concurrent async operations'
            
            # Prepare response
            response_serializer = VoiceTranslationResponseSerializer(data=result)
            if response_serializer.is_valid():
                return Response(response_serializer.data, status=status.HTTP_200_OK)
            else:
                return Response(result, status=status.HTTP_200_OK)
                
        except Exception as e:
            logger.error(f"Error in async voice translation API: {str(e)}")
            return Response({
                'success': False,
                'error': f'Internal server error: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@extend_schema(tags=["Voice Translation History"])
class AsyncTranslationHistoryAPIView(APIView):
    """Async endpoint for retrieving translation history"""
    
    permission_classes = [IsAuthenticated]
    
    @extend_schema(
        tags=['Voice Translation (Async)'],
        summary='Get Translation History (Async)',
        description='Get translation history with optional filtering using async database operations'
    )
    async def get(self, request, *args, **kwargs):
        """Get translation history with optional filtering (async)"""
        try:
            # Validate query parameters
            query_serializer = TranslationHistorySerializer(data=request.query_params)
            if not query_serializer.is_valid():
                return Response({
                    'error': 'Invalid query parameters',
                    'details': query_serializer.errors
                }, status=status.HTTP_400_BAD_REQUEST)
            
            params = query_serializer.validated_data
            
            # Build queryset for authenticated user using async
            from asgiref.sync import sync_to_async
            from django.db.models import Q
            
            # Start with base queryset
            queryset = Translation.objects.filter(user=request.user, user__isnull=False)
            
            # Apply filters
            if params.get('session_id'):
                queryset = queryset.filter(session_id=params['session_id'])
            
            if params.get('language_filter'):
                lang_filter = params['language_filter']
                queryset = queryset.filter(
                    Q(original_language=lang_filter) | 
                    Q(target_language=lang_filter)
                )
            
            if params.get('date_from'):
                queryset = queryset.filter(created_at__gte=params['date_from'])
            
            if params.get('date_to'):
                queryset = queryset.filter(created_at__lte=params['date_to'])
            
            # Apply pagination
            offset = params.get('offset', 0)
            limit = params.get('limit', 20)
            
            # Execute queries asynchronously
            total_count = await sync_to_async(queryset.count)()
            translations_list = await sync_to_async(list)(queryset[offset:offset + limit])
            
            # Serialize results
            serializer = TranslationSerializer(translations_list, many=True, context={'request': request})
            
            return Response({
                'count': total_count,
                'offset': offset,
                'limit': limit,
                'results': serializer.data,
                'async_note': 'Retrieved using async database operations'
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error retrieving async translation history: {str(e)}")
            return Response({
                'error': f'Failed to retrieve history: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@extend_schema(tags=["Voice Translation"])
class BackgroundVoiceTranslationAPIView(APIView):
    """API endpoint for dispatching voice translation to background tasks"""
    
    permission_classes = [IsAuthenticated]
    
    @extend_schema(
        tags=['Voice Translation (Background)'],
        summary='Dispatch Voice Translation to Background',
        description='''
        Dispatch voice translation processing to a background Celery task for long-running operations.
        
        **Use Case:**
        - Large audio files (>2 minutes)
        - Multiple concurrent requests
        - When immediate response is not required
        - Batch processing scenarios
        
        **Benefits:**
        - Non-blocking API response
        - Better resource management
        - Scalable processing
        - Automatic retry on failure
        
        **Process:**
        1. Upload audio file and get immediate task ID
        2. Poll task status using returned task_id
        3. Retrieve results when task completes
        ''',
        request=VoiceTranslationRequestSerializer,
        responses={
            202: OpenApiResponse(
                description='Task dispatched successfully',
                examples=[
                    OpenApiExample(
                        'Task Dispatched',
                        value={
                            'success': True,
                            'task_id': 'a1b2c3d4-e5f6-7890-abcd-ef1234567890',
                            'status': 'dispatched',
                            'message': 'Voice translation task dispatched to background',
                            'estimated_completion': '2-5 minutes',
                            'check_status_url': '/api/voice/task/a1b2c3d4-e5f6-7890-abcd-ef1234567890/status/'
                        }
                    )
                ]
            ),
            400: OpenApiResponse(description='Invalid request data'),
            401: OpenApiResponse(description='Authentication required'),
            500: OpenApiResponse(description='Internal server error')
        }
    )
    def post(self, request, *args, **kwargs):
        """
        Dispatch voice translation to background task
        """
        try:
            # Validate request data
            serializer = VoiceTranslationRequestSerializer(data=request.data)
            if not serializer.is_valid():
                return Response({
                    'success': False,
                    'error': 'Invalid request data',
                    'details': serializer.errors
                }, status=status.HTTP_400_BAD_REQUEST)
            
            validated_data = serializer.validated_data
            
            # Save uploaded file temporarily
            audio_file = validated_data['audio_file']
            import tempfile
            import os
            
            # Create temporary file
            temp_dir = tempfile.mkdtemp()
            temp_file_path = os.path.join(temp_dir, f"audio_{request.user.id}_{int(time.time())}.wav")
            
            with open(temp_file_path, 'wb') as temp_file:
                for chunk in audio_file.chunks():
                    temp_file.write(chunk)
            
            # Get or create session ID
            session_id = validated_data.get('session_id') or str(uuid.uuid4())
            
            # Dispatch Celery task
            from .tasks import async_voice_translation_task
            
            task = async_voice_translation_task.delay(
                user_id=request.user.id,
                audio_file_path=temp_file_path,
                session_id=session_id,
                target_language=validated_data['target_language']
            )
            
            return Response({
                'success': True,
                'task_id': str(task.id),
                'status': 'dispatched',
                'message': 'Voice translation task dispatched to background',
                'estimated_completion': '2-5 minutes',
                'check_status_url': f'/api/voice/task/{task.id}/status/',
                'session_id': session_id,
                'target_language': validated_data['target_language']
            }, status=status.HTTP_202_ACCEPTED)
                
        except Exception as e:
            logger.error(f"Error dispatching background task: {str(e)}")
            return Response({
                'success': False,
                'error': f'Failed to dispatch task: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


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

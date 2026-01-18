"""
Voice Translation API Views

REST API endpoints for the Speak Africa voice translation application.
"""

import logging
import uuid
import time
from django.shortcuts import get_object_or_404
from django.http import JsonResponse, Http404
from django.shortcuts import get_object_or_404

from django.db import models
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView

from drf_spectacular.utils import extend_schema, OpenApiExample, OpenApiResponse

from ..serializers import (
    TranslationSerializer,
    VoiceTranslationRequestSerializer, VoiceTranslationResponseSerializer, TranslationHistorySerializer,
)
from ..services import VoiceTranslationService, AsyncVoiceTranslationService
from ..models import Translation


logger = logging.getLogger(__name__)


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
            from ..tasks import async_voice_translation_task
            
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


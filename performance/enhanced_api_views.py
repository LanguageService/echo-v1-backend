"""
Enhanced API views with performance optimizations
"""
from ocr_app.services import OCRTranslatorService
import time
import json
from typing import Dict, Any, Optional
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.views import View
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

from .cache_service import cache_service
from .language_detector import language_detector
from .image_optimizer import image_optimizer
from .async_processor import async_processor
from .connection_pool import service_manager
from .celery_tasks import process_ocr_background, process_voice_background
import logging

logger = logging.getLogger(__name__)


@csrf_exempt
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def enhanced_ocr_process(request):
    """Enhanced OCR processing with real-time updates and caching"""
    try:
        # Extract parameters
        image_file = request.FILES.get('image')
        target_language = request.data.get('target_language', 'en')
        processing_mode = request.data.get('mode', 'async')  # 'sync', 'async', 'background'
        user_id = request.user.id
        
        if not image_file:
            return Response({
                'error': 'No image file provided'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Save uploaded image
        image_path = _save_uploaded_file(image_file, user_id)
        
        # Get image info for optimization decisions
        image_info = image_optimizer.get_image_info(image_path)
        
        if processing_mode == 'sync':
            # Synchronous processing with caching
            result = _process_ocr_sync(image_path, user_id, target_language)
            
            return Response({
                'status': 'completed',
                'result': result,
                'image_info': image_info,
                'processing_mode': 'synchronous'
            })
            
        elif processing_mode == 'background':
            # Background processing with Celery
            task = process_ocr_background.delay(image_path, user_id, target_language)
            
            return Response({
                'status': 'processing',
                'task_id': task.id,
                'message': 'Processing started in background. Connect to WebSocket for updates.',
                'websocket_url': f'/ws/ocr/',
                'image_info': image_info,
                'processing_mode': 'background'
            })
            
        else:  # async mode (default)
            # Async processing with real-time updates
            asyncio.create_task(_process_ocr_async(image_path, user_id, target_language))
            
            return Response({
                'status': 'processing',
                'message': 'Processing started. Connect to WebSocket for real-time updates.',
                'websocket_url': f'/ws/ocr/',
                'image_info': image_info,
                'processing_mode': 'async',
                'estimated_time': image_optimizer.estimate_processing_time(image_path)
            })
            
    except Exception as e:
        return Response({
            'error': f'Processing failed: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@csrf_exempt
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def enhanced_voice_process(request):
    """Enhanced voice processing with real-time updates"""
    try:
        audio_file = request.FILES.get('audio')
        target_language = request.data.get('target_language', 'en')
        processing_mode = request.data.get('mode', 'async')
        user_id = request.user.id
        
        if not audio_file:
            return Response({
                'error': 'No audio file provided'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Save uploaded audio
        audio_path = _save_uploaded_file(audio_file, user_id, file_type='audio')
        
        if processing_mode == 'background':
            task = process_voice_background.delay(audio_path, user_id, target_language)
            
            return Response({
                'status': 'processing',
                'task_id': task.id,
                'message': 'Voice processing started in background.',
                'websocket_url': f'/ws/voice/',
                'processing_mode': 'background'
            })
        else:
            asyncio.create_task(_process_voice_async(audio_path, user_id, target_language))
            
            return Response({
                'status': 'processing',
                'message': 'Voice processing started.',
                'websocket_url': f'/ws/voice/',
                'processing_mode': 'async'
            })
            
    except Exception as e:
        return Response({
            'error': f'Voice processing failed: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@csrf_exempt
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def batch_ocr_process(request):
    """Process multiple images in batch"""
    try:
        images = request.FILES.getlist('images')
        target_language = request.data.get('target_language', 'en')
        user_id = request.user.id
        
        if not images:
            return Response({
                'error': 'No images provided'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if len(images) > 10:  # Limit batch size
            return Response({
                'error': 'Maximum 10 images allowed per batch'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Save all images
        image_paths = []
        for i, image_file in enumerate(images):
            image_path = _save_uploaded_file(image_file, user_id, suffix=f'_batch_{i}')
            image_paths.append(image_path)
        
        # Start batch processing
        from .celery_tasks import batch_process_images
        task = batch_process_images.delay(image_paths, user_id, target_language)
        
        return Response({
            'status': 'processing',
            'task_id': task.id,
            'total_images': len(images),
            'message': 'Batch processing started.',
            'websocket_url': f'/ws/processing/',
            'processing_mode': 'batch'
        })
        
    except Exception as e:
        return Response({
            'error': f'Batch processing failed: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


from asgiref.sync import async_to_sync

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def performance_stats(request):
    """Get performance statistics and cache info"""
    try:
        user_id = request.user.id
        
        # Get cache statistics
        cache_stats = cache_service.get_cache_stats()
        
        # Get service health
        service_health = async_to_sync(service_manager.health_check)()
        
        # Get connection pool stats
        connection_stats = async_to_sync(service_manager.get_service_stats)()
        
        return Response({
            'user_id': user_id,
            'cache_statistics': cache_stats,
            'service_health': service_health,
            'connection_statistics': connection_stats,
            'supported_languages': language_detector.get_supported_languages(),
            'optimization_features': {
                'smart_caching': True,
                'image_optimization': True,
                'parallel_processing': True,
                'real_time_updates': True,
                'background_tasks': True,
                'connection_pooling': True,
                'service_fallback': True
            }
        })
        
    except Exception as e:
        return Response({
            'error': f'Failed to get performance stats: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def clear_user_cache(request):
    """Clear cache for current user"""
    try:
        user_id = request.user.id
        cache_service.clear_user_cache(user_id)
        
        return Response({
            'status': 'success',
            'message': f'Cache cleared for user {user_id}'
        })
        
    except Exception as e:
        return Response({
            'error': f'Failed to clear cache: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def warm_cache(request):
    """Pre-warm cache with common translations"""
    try:
        user_id = request.user.id
        common_translations = request.data.get('translations', [])
        
        if not common_translations:
            return Response({
                'error': 'No translations provided for cache warming'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        from .celery_tasks import warm_user_cache
        task = warm_user_cache.delay(user_id, common_translations)
        
        return Response({
            'status': 'processing',
            'task_id': task.id,
            'message': 'Cache warming started',
            'translations_count': len(common_translations)
        })
        
    except Exception as e:
        return Response({
            'error': f'Cache warming failed: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def language_detection_test(request):
    """Test language detection capabilities"""
    try:
        text = request.GET.get('text', '')
        
        if not text:
            return Response({
                'error': 'No text provided'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Quick pattern detection
        quick_result = language_detector.quick_detect(text)
        
        # Text complexity analysis
        complexity = language_detector.analyze_text_complexity(text)
        
        return Response({
            'text': text,
            'quick_detection': quick_result,
            'text_analysis': complexity,
            'supported_languages': language_detector.get_supported_languages()
        })
        
    except Exception as e:
        return Response({
            'error': f'Language detection test failed: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# Helper functions
def _save_uploaded_file(file, user_id: int, file_type: str = 'image', suffix: str = '') -> str:
    """Save uploaded file and return path"""
    import os
    from django.conf import settings
    
    # Create user directory
    user_dir = os.path.join(settings.MEDIA_ROOT, f'user_{user_id}', file_type)
    os.makedirs(user_dir, exist_ok=True)
    
    # Generate filename with timestamp
    timestamp = int(time.time())
    filename = f"{timestamp}{suffix}_{file.name}"
    file_path = os.path.join(user_dir, filename)
    
    # Save file
    with open(file_path, 'wb+') as destination:
        for chunk in file.chunks():
            destination.write(chunk)
    
    return file_path


def _process_ocr_sync(image_path: str, user_id: int, target_language: str) -> Dict[str, Any]:
    """Synchronous OCR processing with caching"""
    start_time = time.time()
    
    # Check cache first
    image_hash = cache_service.get_image_hash(image_path)
    cached_result = cache_service.get_cached_ocr_result(image_hash)
    
    if cached_result:
        result = cached_result.copy()
        result['processing_time'] = time.time() - start_time
        result['cached'] = True
        return result
    
    # Image optimization
    optimized_path = image_optimizer.optimize_for_ocr(image_path)
    
    # Initialize the OCR service
    ocr_service = OCRTranslatorService()
    
    # Process the image to get the OCR result
    ocr_result = ocr_service.process_image(optimized_path)
    
    result = {
        'success': ocr_result.get('success', False),
        'original_text': ocr_result.get('original_text', ''),
        'detected_language': ocr_result.get('detected_language', 'unknown'),
        'language_name': ocr_result.get('language_name', 'Unknown'),
        'translated_text': ocr_result.get('translated_text', ''),
        'target_language': target_language,
        'confidence': ocr_result.get('confidence_score', 0.0),
        'processing_time': time.time() - start_time,
        'cached': False,
        'optimization_applied': optimized_path != image_path
    }
    
    # Cache the result
    if result['success']:
        cache_service.cache_ocr_result(image_hash, result)
    
    return result


from functools import partial

async def _process_ocr_async(image_path: str, user_id: int, target_language: str):
    """Async OCR processing with real-time updates"""
    try:
        loop = asyncio.get_running_loop()
        
        # Run the synchronous OCR processing in a separate thread
        result = await loop.run_in_executor(
            None,  # Use the default executor
            partial(_process_ocr_sync, image_path, user_id, target_language)
        )
        
        # Send result via WebSocket (optional, can be added later)
        channel_layer = get_channel_layer()
        if channel_layer:
            await channel_layer.group_send(
                f"ocr_{user_id}",
                {
                    'type': 'processing_update',
                    'data': {
                        'type': 'complete',
                        'result': result
                    }
                }
            )
        
        return result
    except Exception as e:
        # Send error via WebSocket
        channel_layer = get_channel_layer()
        if channel_layer:
            await channel_layer.group_send(
                f"ocr_{user_id}",
                {
                    'type': 'processing_update',
                    'data': {
                        'type': 'error',
                        'message': f'Async processing failed: {str(e)}'
                    }
                }
            )


async def _process_voice_async(audio_path: str, user_id: int, target_language: str):
    """Async voice processing with real-time updates"""
    try:
        result = await async_processor.process_voice_parallel(
            audio_path, user_id, target_language
        )
        return result
    except Exception as e:
        channel_layer = get_channel_layer()
        if channel_layer:
            await channel_layer.group_send(
                f"voice_{user_id}",
                {
                    'type': 'processing_update',
                    'data': {
                        'type': 'error',
                        'message': f'Voice processing failed: {str(e)}'
                    }
                }
            )
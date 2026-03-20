"""
Celery background tasks for heavy processing
"""
import os
import time
import logging
from typing import Dict, Any, Optional
from celery import shared_task
from django.conf import settings
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

logger = logging.getLogger(__name__)
channel_layer = get_channel_layer()


def send_websocket_update(user_id: int, processing_type: str, data: Dict[str, Any]):
    """Send real-time updates via WebSocket"""
    if not channel_layer:
        return
    
    group_name = f"{processing_type}_{user_id}"
    
    try:
        async_to_sync(channel_layer.group_send)(
            group_name,
            {
                'type': 'processing_update',
                'data': data
            }
        )
    except Exception as e:
        logger.error(f"Failed to send WebSocket update: {str(e)}")


@shared_task(bind=True)
def process_ocr_background(self, image_path: str, user_id: int, 
                          target_language: str = 'en') -> Dict[str, Any]:
    """Process OCR in background with progress updates"""
    task_id = self.request.id
    start_time = time.time()
    
    try:
        # Send initial status
        send_websocket_update(user_id, 'ocr', {
            'type': 'task_started',
            'task_id': task_id,
            'progress': 0,
            'message': 'Starting background OCR processing...'
        })
        
        # Import here to avoid circular imports
        from .cache_service import cache_service
        from .image_optimizer import image_optimizer
        from .async_processor import async_processor
        
        # Step 1: Check cache
        image_hash = cache_service.get_image_hash(image_path)
        cached_result = cache_service.get_cached_ocr_result(image_hash)
        
        if cached_result:
            send_websocket_update(user_id, 'ocr', {
                'type': 'progress',
                'task_id': task_id,
                'progress': 90,
                'message': 'Found cached result!'
            })
            
            result = cached_result.copy()
            result['task_id'] = task_id
            result['processing_time'] = time.time() - start_time
            result['cached'] = True
            
            send_websocket_update(user_id, 'ocr', {
                'type': 'task_complete',
                'task_id': task_id,
                'progress': 100,
                'result': result
            })
            
            return result
        
        # Step 2: Image optimization
        send_websocket_update(user_id, 'ocr', {
            'type': 'progress',
            'task_id': task_id,
            'progress': 20,
            'message': 'Optimizing image...'
        })
        
        optimized_path = image_optimizer.optimize_for_ocr(image_path)
        
        # Step 3: OCR processing
        send_websocket_update(user_id, 'ocr', {
            'type': 'progress',
            'task_id': task_id,
            'progress': 50,
            'message': 'Extracting text...'
        })
        
        # Here you would integrate with your actual OCR service
        ocr_result = _mock_ocr_processing(optimized_path)
        
        if not ocr_result.get('text'):
            raise ValueError("No text detected in image")
        
        # Step 4: Language detection
        send_websocket_update(user_id, 'ocr', {
            'type': 'progress',
            'task_id': task_id,
            'progress': 70,
            'message': 'Detecting language...'
        })
        
        from .language_detector import language_detector
        detected_lang = language_detector.quick_detect(ocr_result['text'])
        if not detected_lang:
            detected_lang = {'language': 'en', 'confidence': 0.5}
        
        # Step 5: Translation
        send_websocket_update(user_id, 'ocr', {
            'type': 'progress',
            'task_id': task_id,
            'progress': 90,
            'message': 'Translating text...'
        })
        
        translation_result = _mock_translation(
            ocr_result['text'], 
            detected_lang['language'], 
            target_language
        )
        
        # Final result
        final_result = {
            'task_id': task_id,
            'original_text': ocr_result['text'],
            'detected_language': detected_lang['language'],
            'translated_text': translation_result['translation'],
            'target_language': target_language,
            'confidence': ocr_result.get('confidence', 0.9),
            'processing_time': time.time() - start_time,
            'cached': False,
            'optimization_applied': optimized_path != image_path,
            'service_used': translation_result.get('service_used', 'gemini')
        }
        
        # Cache the result
        cache_service.cache_ocr_result(image_hash, final_result)
        
        send_websocket_update(user_id, 'ocr', {
            'type': 'task_complete',
            'task_id': task_id,
            'progress': 100,
            'result': final_result
        })
        
        return final_result
        
    except Exception as e:
        logger.error(f"Background OCR processing failed: {str(e)}")
        
        error_data = {
            'type': 'task_error',
            'task_id': task_id,
            'error': str(e),
            'processing_time': time.time() - start_time
        }
        
        send_websocket_update(user_id, 'ocr', error_data)
        
        # Re-raise to mark task as failed
        raise


@shared_task(bind=True)
def process_voice_background(self, audio_path: str, user_id: int,
                           target_language: str = 'en') -> Dict[str, Any]:
    """Process voice translation in background"""
    task_id = self.request.id
    start_time = time.time()
    
    try:
        send_websocket_update(user_id, 'voice', {
            'type': 'task_started',
            'task_id': task_id,
            'progress': 0,
            'message': 'Starting background voice processing...'
        })
        
        from .cache_service import cache_service
        
        # Check transcription cache
        audio_hash = cache_service.get_image_hash(audio_path)
        cached_transcription = cache_service.get_cached_voice_transcription(audio_hash)
        
        if cached_transcription:
            transcription = cached_transcription['transcription']
            source_language = cached_transcription['language']
            
            send_websocket_update(user_id, 'voice', {
                'type': 'progress',
                'task_id': task_id,
                'progress': 40,
                'message': 'Using cached transcription...'
            })
        else:
            send_websocket_update(user_id, 'voice', {
                'type': 'progress',
                'task_id': task_id,
                'progress': 30,
                'message': 'Converting speech to text...'
            })
            
            transcription_result = _mock_voice_transcription(audio_path)
            transcription = transcription_result['text']
            source_language = transcription_result['language']
            
            cache_service.cache_voice_transcription(audio_hash, transcription, source_language)
        
        # Translation
        send_websocket_update(user_id, 'voice', {
            'type': 'progress',
            'task_id': task_id,
            'progress': 70,
            'message': 'Translating text...'
        })
        
        translation_result = _mock_translation(transcription, source_language, target_language)
        
        # Text-to-speech
        send_websocket_update(user_id, 'voice', {
            'type': 'progress',
            'task_id': task_id,
            'progress': 90,
            'message': 'Generating audio...'
        })
        
        audio_result = _mock_text_to_speech(translation_result['translation'], target_language)
        
        final_result = {
            'task_id': task_id,
            'original_text': transcription,
            'source_language': source_language,
            'translated_text': translation_result['translation'],
            'target_language': target_language,
            'audio_url': audio_result.get('audio_url'),
            'processing_time': time.time() - start_time,
            'cached_transcription': cached_transcription is not None,
            'service_used': translation_result.get('service_used', 'gemini')
        }
        
        send_websocket_update(user_id, 'voice', {
            'type': 'task_complete',
            'task_id': task_id,
            'progress': 100,
            'result': final_result
        })
        
        return final_result
        
    except Exception as e:
        logger.error(f"Background voice processing failed: {str(e)}")
        
        send_websocket_update(user_id, 'voice', {
            'type': 'task_error',
            'task_id': task_id,
            'error': str(e),
            'processing_time': time.time() - start_time
        })
        
        raise


@shared_task
def batch_process_images(image_paths: list, user_id: int, target_language: str = 'en'):
    """Process multiple images in batch"""
    results = {}
    total_images = len(image_paths)
    
    for i, image_path in enumerate(image_paths):
        try:
            progress = int((i / total_images) * 100)
            
            send_websocket_update(user_id, 'batch', {
                'type': 'batch_progress',
                'progress': progress,
                'current_image': i + 1,
                'total_images': total_images,
                'processing': image_path
            })
            
            # Process single image
            result = process_ocr_background.delay(image_path, user_id, target_language)
            results[image_path] = result.get()  # Wait for completion
            
        except Exception as e:
            logger.error(f"Batch processing failed for {image_path}: {str(e)}")
            results[image_path] = {'error': str(e)}
    
    send_websocket_update(user_id, 'batch', {
        'type': 'batch_complete',
        'progress': 100,
        'results': results,
        'total_processed': len(results)
    })
    
    return results


@shared_task
def cleanup_old_cache():
    """Periodic task to cleanup old cache entries"""
    try:
        from .cache_service import cache_service
        
        # This would implement cache cleanup logic
        # For now, just log the operation
        logger.info("Cache cleanup task executed")
        
        return {'status': 'completed', 'timestamp': time.time()}
        
    except Exception as e:
        logger.error(f"Cache cleanup failed: {str(e)}")
        raise


@shared_task
def warm_user_cache(user_id: int, common_translations: list):
    """Pre-warm cache for frequently used translations"""
    try:
        from .cache_service import cache_service
        
        cache_service.warm_cache(user_id, common_translations)
        
        logger.info(f"Cache warmed for user {user_id}")
        return {'status': 'completed', 'user_id': user_id}
        
    except Exception as e:
        logger.error(f"Cache warming failed for user {user_id}: {str(e)}")
        raise


# Mock functions (replace with actual implementations)
def _mock_ocr_processing(image_path: str) -> Dict[str, Any]:
    """Mock OCR processing"""
    time.sleep(1.0)  # Simulate processing time
    return {
        'text': f'Sample extracted text from {os.path.basename(image_path)}',
        'confidence': 0.95
    }


def _mock_voice_transcription(audio_path: str) -> Dict[str, Any]:
    """Mock voice transcription"""
    time.sleep(1.5)
    return {
        'text': f'Sample transcribed text from {os.path.basename(audio_path)}',
        'language': 'en'
    }


def _mock_translation(text: str, source_lang: str, target_lang: str) -> Dict[str, Any]:
    """Mock translation"""
    time.sleep(0.5)
    return {
        'translation': f'[{target_lang}] Translated: {text}',
        'service_used': 'gemini'
    }


def _mock_text_to_speech(text: str, language: str) -> Dict[str, Any]:
    """Mock TTS"""
    time.sleep(0.8)
    return {
        'audio_url': f'/media/generated_audio_{int(time.time())}.mp3'
    }



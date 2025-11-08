"""
Celery tasks for voice translation background processing

This module contains Celery tasks for handling voice translation operations
in the background, improving API responsiveness and handling concurrent requests.
"""

import logging
import time
from typing import Dict, Any
from celery import shared_task
from django.contrib.auth import get_user_model
from .services import AsyncVoiceTranslationService
from .models import Translation, UserSettings

logger = logging.getLogger(__name__)
User = get_user_model()


@shared_task(bind=True, autoretry_for=(Exception,), retry_kwargs={'max_retries': 3, 'countdown': 60})
def async_voice_translation_task(self, user_id: int, audio_file_path: str, 
                                session_id: str = None, target_language: str = 'en') -> Dict[str, Any]:
    """
    Background Celery task for voice translation processing
    
    Args:
        self: Celery task instance
        user_id: User ID for authentication
        audio_file_path: Path to the audio file
        session_id: Session ID for grouping translations
        target_language: Target language for translation
        
    Returns:
        Dictionary with translation results
    """
    try:
        logger.info(f"Starting background voice translation task for user {user_id}")
        
        # Get user
        user = User.objects.get(id=user_id)
        
        # Initialize async service
        async_service = AsyncVoiceTranslationService()
        
        # Process translation (Note: This is running in sync context within Celery)
        # For true async processing in Celery, we'd need async-compatible broker
        import asyncio
        
        async def run_translation():
            with open(audio_file_path, 'rb') as audio_file:
                result = await async_service.process_voice_translation(
                    user=user,
                    audio_file=audio_file,
                    session_id=session_id,
                    target_language=target_language
                )
            return result
        
        # Run async function in sync context
        result = asyncio.run(run_translation())
        
        # Mark task as successful
        result['task_id'] = str(self.request.id)
        result['processed_in_background'] = True
        
        logger.info(f"Background voice translation completed for user {user_id}")
        return result
        
    except Exception as e:
        logger.error(f"Error in background voice translation task: {str(e)}")
        # Celery will automatically retry based on autoretry_for configuration
        raise


@shared_task(bind=True)
def batch_translation_task(self, translation_requests: list) -> Dict[str, Any]:
    """
    Process multiple translation requests in parallel using Celery
    
    Args:
        self: Celery task instance
        translation_requests: List of translation request dictionaries
        
    Returns:
        Dictionary with batch processing results
    """
    try:
        logger.info(f"Starting batch translation task with {len(translation_requests)} requests")
        
        results = []
        errors = []
        
        for req in translation_requests:
            try:
                # Dispatch individual translation task
                task_result = async_voice_translation_task.delay(
                    user_id=req['user_id'],
                    audio_file_path=req['audio_file_path'],
                    session_id=req.get('session_id'),
                    target_language=req.get('target_language', 'en')
                )
                
                results.append({
                    'request_id': req.get('request_id'),
                    'task_id': task_result.id,
                    'status': 'dispatched'
                })
                
            except Exception as e:
                errors.append({
                    'request_id': req.get('request_id'),
                    'error': str(e)
                })
        
        return {
            'batch_id': str(self.request.id),
            'total_requests': len(translation_requests),
            'successful_dispatches': len(results),
            'errors': len(errors),
            'results': results,
            'error_details': errors
        }
        
    except Exception as e:
        logger.error(f"Error in batch translation task: {str(e)}")
        raise


@shared_task(bind=True)
def cleanup_old_translations_task(self, days_old: int = 30) -> Dict[str, Any]:
    """
    Background task to clean up old translation records
    
    Args:
        self: Celery task instance
        days_old: Number of days after which translations should be cleaned up
        
    Returns:
        Dictionary with cleanup results
    """
    try:
        logger.info(f"Starting cleanup of translations older than {days_old} days")
        
        from django.utils import timezone
        from datetime import timedelta
        
        cutoff_date = timezone.now() - timedelta(days=days_old)
        
        # Get count before deletion
        old_translations = Translation.objects.filter(created_at__lt=cutoff_date)
        count_before = old_translations.count()
        
        # Delete old translations
        deleted_count = old_translations.delete()[0]
        
        logger.info(f"Cleanup completed: {deleted_count} translations deleted")
        
        return {
            'task_id': str(self.request.id),
            'cutoff_date': cutoff_date.isoformat(),
            'translations_found': count_before,
            'translations_deleted': deleted_count,
            'success': True
        }
        
    except Exception as e:
        logger.error(f"Error in cleanup task: {str(e)}")
        raise


@shared_task(bind=True)
def translation_analytics_task(self) -> Dict[str, Any]:
    """
    Background task to generate translation analytics and statistics
    
    Args:
        self: Celery task instance
        
    Returns:
        Dictionary with analytics results
    """
    try:
        logger.info("Starting translation analytics generation")
        
        from django.db.models import Count, Avg, Q
        from django.utils import timezone
        from datetime import timedelta
        
        # Get analytics for the last 30 days
        thirty_days_ago = timezone.now() - timedelta(days=30)
        
        # Total translations
        total_translations = Translation.objects.count()
        recent_translations = Translation.objects.filter(created_at__gte=thirty_days_ago).count()
        
        # Language statistics
        language_stats = Translation.objects.values('original_language', 'target_language').annotate(
            count=Count('id')
        ).order_by('-count')[:10]
        
        # User statistics
        user_stats = Translation.objects.values('user').annotate(
            translation_count=Count('id'),
            avg_confidence=Avg('confidence_score')
        ).order_by('-translation_count')[:10]
        
        # Performance statistics
        avg_processing_time = Translation.objects.aggregate(
            avg_time=Avg('processing_time')
        )['avg_time'] or 0
        
        # Success rate
        successful_translations = Translation.objects.filter(
            translated_text__isnull=False
        ).exclude(translated_text='').count()
        
        success_rate = (successful_translations / total_translations * 100) if total_translations > 0 else 0
        
        analytics = {
            'task_id': str(self.request.id),
            'generated_at': timezone.now().isoformat(),
            'period': '30_days',
            'totals': {
                'all_time_translations': total_translations,
                'recent_translations': recent_translations,
                'success_rate_percent': round(success_rate, 2),
                'avg_processing_time_seconds': round(avg_processing_time, 2)
            },
            'language_stats': list(language_stats),
            'top_users': list(user_stats),
            'success': True
        }
        
        logger.info("Translation analytics generation completed")
        return analytics
        
    except Exception as e:
        logger.error(f"Error in analytics task: {str(e)}")
        raise
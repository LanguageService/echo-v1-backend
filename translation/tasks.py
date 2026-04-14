"""
Celery tasks for voice translation background processing

This module contains Celery tasks for handling voice translation operations
in the background, improving API responsiveness and handling concurrent requests.
"""

import logging
import time
from typing import Dict, Any, Optional
from celery import shared_task
from django.contrib.auth import get_user_model
from .services import AsyncVoiceTranslationService
from .models import UserSettings

logger = logging.getLogger(__name__)
User = get_user_model()


@shared_task(bind=True, autoretry_for=(Exception,), retry_kwargs={'max_retries': 3, 'countdown': 60})
def async_voice_translation_task(self, translation_id: str) -> Dict[str, Any]:
    """
    Background Celery task for voice translation processing using the orchestrator
    """
    try:
        from .orchestrator import TranslationOrchestrator
        from .models import SpeechTranslation
        
        translation_record = SpeechTranslation.objects.get(id=translation_id)
        orchestrator = TranslationOrchestrator()
        
        result = orchestrator.translate_speech(
            user=translation_record.user,
            audio_file=None,
            target_lang=translation_record.target_language,
            source_lang=translation_record.original_language,
            mode=translation_record.mode,
            session_id=translation_record.session_id,
            original_file_url=translation_record.original_audio_url,
            translation_id=translation_id
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Error in background voice translation task: {str(e)}")
        if translation_id:
            from .models import SpeechTranslation
            from .choices import TranslationStatus
            SpeechTranslation.objects.filter(id=translation_id).update(
                status=TranslationStatus.FAILED,
                error_message=str(e)
            )
        raise



@shared_task(bind=True, autoretry_for=(Exception,), retry_kwargs={'max_retries': 2, 'countdown': 300})
def async_ebook_translation_task(self, translation_id: str, local_file_path: str = None) -> Dict[str, Any]:
    """
    Background Celery task for ebook/document translation
    """
    try:
        logger.info(f"Starting background ebook translation task for record {translation_id}")
        
        from .services import DocumentTranslationService
        from .models import TextTranslation
        from core.mail import send_email
        
        service = DocumentTranslationService()
        result = service.process_document_translation(translation_id, local_file_path)
        
        if result['success']:
            # Send completion email
            translation_record = TextTranslation.objects.get(id=translation_id)
            if translation_record.user and translation_record.user.email:
                subject = "Your Document Translation is Ready!"
                body = f"""
                Hello {translation_record.user.first_name or 'there'},
                
                Your document has been successfully translated to {translation_record.target_language}.
                
                You can download it now from your dashboard:
                {translation_record.translated_file_url}
                
                Thank you for using Echo!
                """
                send_email(
                    recipient=translation_record.user.email,
                    subject=subject,
                    body_text=body,
                    enqueue=True
                )
        
        return result
        
    except Exception as e:
        logger.error(f"Error in background ebook translation task: {str(e)}")
        raise


@shared_task(bind=True)
def batch_translation_task(self, translation_requests: list) -> Dict[str, Any]:
    """
    Process multiple translation requests in parallel using Celery
    """
    try:
        logger.info(f"Starting batch translation task with {len(translation_requests)} requests")
        
        results = []
        errors = []
        
        for req in translation_requests:
            try:
                # Dispatch individual voice translation task
                task_result = async_voice_translation_task.delay(
                    translation_id=req['translation_id']
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
    Background task to clean up old translation records across all types
    """
    try:
        logger.info(f"Starting cleanup of translations older than {days_old} days")
        
        from django.utils import timezone
        from datetime import timedelta
        from .models import TextTranslation, SpeechTranslation, ImageTranslation
        
        cutoff_date = timezone.now() - timedelta(days=days_old)
        
        total_deleted = 0
        deleted_details = {}
        
        for model in [TextTranslation, SpeechTranslation, ImageTranslation]:
            old_records = model.objects.filter(date_created__lt=cutoff_date)
            count = old_records.count()
            deleted_count = old_records.delete()[0]
            total_deleted += deleted_count
            deleted_details[model.__name__] = deleted_count
        
        logger.info(f"Cleanup completed: {total_deleted} translations deleted. Details: {deleted_details}")
        
        return {
            'task_id': str(self.request.id),
            'cutoff_date': cutoff_date.isoformat(),
            'total_deleted': total_deleted,
            'details': deleted_details,
            'success': True
        }
        
    except Exception as e:
        logger.error(f"Error in cleanup task: {str(e)}")
        raise


@shared_task(bind=True)
def translation_analytics_task(self) -> Dict[str, Any]:
    """
    Background task to generate translation analytics and statistics across all types
    """
    try:
        logger.info("Starting translation analytics generation")
        
        from django.db.models import Count, Avg, Q
        from django.utils import timezone
        from datetime import timedelta
        from .models import TextTranslation, SpeechTranslation, ImageTranslation
        
        thirty_days_ago = timezone.now() - timedelta(days=30)
        
        total_count = 0
        recent_count = 0
        type_counts = {}
        
        for model in [TextTranslation, SpeechTranslation, ImageTranslation]:
            name = model.__name__
            all_q = model.objects.all()
            total_count += all_q.count()
            recent = all_q.filter(date_created__gte=thirty_days_ago).count()
            recent_count += recent
            type_counts[name] = all_q.count()
        
        # Performance statistics from SpeechTranslation (most relevant for processing times)
        avg_processing_time = SpeechTranslation.objects.aggregate(
            avg_time=Avg('total_processing_time')
        )['avg_time'] or 0
        
        analytics = {
            'task_id': str(self.request.id),
            'generated_at': timezone.now().isoformat(),
            'period': '30_days',
            'totals': {
                'all_time_translations': total_count,
                'recent_translations': recent_count,
                'avg_speech_processing_time_seconds': round(avg_processing_time, 2)
            },
            'type_distribution': type_counts,
            'success': True
        }
        
        logger.info("Translation analytics generation completed")
        return analytics
        
    except Exception as e:
        logger.error(f"Error in analytics task: {str(e)}")
        raise

@shared_task(bind=True, autoretry_for=(Exception,), retry_kwargs={'max_retries': 3, 'countdown': 60})
def async_stt_task(self, user_id: int, audio_file_path: Optional[str], 
                   translation_id: str, source_language: str = 'auto', 
                   target_language: Optional[str] = None,
                   mode: str = 'LARGE', session_id: Optional[str] = None,
                   original_file_url: Optional[str] = None) -> Dict[str, Any]:
    """Background task for Large Speech-to-Text"""
    try:
        from .orchestrator import TranslationOrchestrator
        from .models import SpeechTranslation
        
        user = User.objects.get(id=user_id)
        orchestrator = TranslationOrchestrator()
        
        # In Large mode, the record is already created by the view
        # But we need to pass a special handle or let orchestrator handle it
        # Let's modify orchestrator if needed, but for now we can just call it
        
        result = orchestrator.speech_to_text(
            user=user,
            audio_file=audio_file_path,
            source_language=source_language,
            target_language=target_language,
            mode=mode,
            session_id=session_id,
            original_file_url=original_file_url,
            translation_id=translation_id
        )
        
        return result
    except Exception as e:
        logger.error(f"Error in async_stt_task: {str(e)}")
        if translation_id:
            from .models import SpeechTranslation
            from .choices import TranslationStatus
            SpeechTranslation.objects.filter(id=translation_id).update(
                status=TranslationStatus.FAILED,
                error_message=str(e)
            )
        raise

@shared_task(bind=True, autoretry_for=(Exception,), retry_kwargs={'max_retries': 3, 'countdown': 60})
def async_tts_task(self, user_id: int, text: str, source_language: str, 
                   translation_id: str, target_language: Optional[str] = None,
                   voice: Optional[str] = None,
                   mode: str = 'LARGE', session_id: Optional[str] = None) -> Dict[str, Any]:
    """Background task for Large Text-to-Speech"""
    try:
        from .orchestrator import TranslationOrchestrator
        from .models import SpeechTranslation
        
        user = User.objects.get(id=user_id)
        orchestrator = TranslationOrchestrator()
        
        result = orchestrator.text_to_speech(
            user=user,
            text=text,
            source_language=source_language,
            target_language=target_language,
            voice=voice,
            mode=mode,
            session_id=session_id,
            translation_id=translation_id
        )
        
        return result
    except Exception as e:
        logger.error(f"Error in async_tts_task: {str(e)}")
        if translation_id:
            from .models import SpeechTranslation
            from .choices import TranslationStatus
            SpeechTranslation.objects.filter(id=translation_id).update(
                status=TranslationStatus.FAILED,
                error_message=str(e)
            )
        raise

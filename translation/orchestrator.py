import logging
import os
import time
from typing import Dict, Any, Optional, BinaryIO
from django.core.files.base import ContentFile
from .providers.factory import ProviderFactory
from .models import TextTranslation, SpeechTranslation, ImageTranslation
from .choices import TranslationStatus, TranslationMode, SpeechServiceType
from .cloud_storage import cloud_storage

logger = logging.getLogger(__name__)

class TranslationOrchestrator:
    """Orchestrates translation workflows using decoupled providers"""
    
    def __init__(self):
        self.asr = ProviderFactory.get_asr_provider()
        self.translator = ProviderFactory.get_translation_provider()
        self.tts = ProviderFactory.get_tts_provider()

    def _save_audio(self, translation_record: SpeechTranslation, audio_data: bytes,
                    filename: str, user_id: str, language: str) -> None:
        """Save synthesised audio. Try cloud first, fallback to local."""
        
        # Step 1 – try cloud upload first (to avoid read-only file system errors)
        try:
            if cloud_storage.is_available():
                remote_url = cloud_storage.upload_voice_output_file(
                    file_content=audio_data,
                    language=language,
                    user_id=str(user_id)
                )
                if remote_url:
                    translation_record.translated_audio_url = remote_url
                    translation_record.translated_audio.name = None
                    translation_record.save(update_fields=['translated_audio', 'translated_audio_url'])
                    return
                else:
                    logger.warning("Cloud upload returned no URL – falling back to local.")
        except Exception as exc:
            logger.error(f"Cloud upload failed: {exc}")

        # Step 2 – fallback to local storage
        try:
            translation_record.translated_audio.save(filename, ContentFile(audio_data), save=True)
            logger.info(f"Audio saved locally to {translation_record.translated_audio.name}")
        except Exception as e:
            logger.error(f"Failed to save audio locally: {str(e)}")

    def _save_input_audio(self, translation_record: SpeechTranslation, audio_file: Any,
                          filename: str, user_id: str, language: str) -> None:
        """Save input audio file. Try cloud first, fallback to local."""
        
        # Step 1 - try cloud upload first
        try:
            if cloud_storage.is_available():
                if hasattr(audio_file, 'seek'):
                    audio_file.seek(0)

                remote_url = cloud_storage.upload_voice_input_file(
                    file=audio_file,
                    language=language,
                    user_id=str(user_id)
                )
                if remote_url:
                    translation_record.original_audio_url = remote_url
                    translation_record.original_audio.name = None
                    translation_record.save(update_fields=['original_audio', 'original_audio_url'])
                    return
        except Exception as exc:
            logger.error(f"Input audio cloud upload failed: {exc}")

        # Step 2 - fallback to local storage
        try:
            translation_record.original_audio.save(filename, audio_file, save=True)
        except Exception as e:
            logger.error(f"Failed to save input audio locally: {str(e)}")

    def _save_input_image(self, translation_record: ImageTranslation, image_file: Any,
                          filename: str, user_id: str, language: str) -> None:
        """Save input image file. Try cloud first, fallback to local."""
        
        # Step 1 - try cloud upload
        try:
            if cloud_storage.is_available():
                if hasattr(image_file, 'seek'):
                    image_file.seek(0)

                remote_url = cloud_storage.upload_image_input_file(
                    file=image_file,
                    language=language,
                    user_id=str(user_id)
                )
                if remote_url:
                    translation_record.original_image_url = remote_url
                    translation_record.original_image.name = None
                    translation_record.save(update_fields=['original_image', 'original_image_url'])
                    return
        except Exception as exc:
            logger.error(f"Input image cloud upload failed: {exc}")

        # Step 2 - fallback to local storage
        try:
            translation_record.original_image.save(filename, image_file, save=True)
        except Exception as e:
            logger.error(f"Failed to save input image locally: {str(e)}")


    def _log_usage(self, user, result: Dict[str, Any], function_performed: str, 
                   translation_record: Optional[Any] = None) -> None:
        """Log LLM usage metadata"""
        try:
            from .models import LLMLog, TextTranslation, SpeechTranslation, ImageTranslation
            
            usage = result.get('usage')
            input_tokens = 0
            output_tokens = 0
            total_tokens = 0
            
            if usage:
                input_tokens = usage.get('prompt_tokens') or 0
                output_tokens = usage.get('candidates_tokens') or 0
                total_tokens = usage.get('total_tokens') or 0
            
            # For TTS, we might track character count if tokens aren't available
            if function_performed == 'TTS' and not total_tokens:
                input_tokens = result.get('char_count', 0)
            
            # Create log entry
            log_entry = LLMLog.objects.create(
                user=user if user and not user.is_anonymous else None,
                provider=result.get('provider', 'Google'),
                model_name=result.get('model', 'gemini-2.0-flash'),
                function_performed=function_performed,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=total_tokens,
                latency=result.get('processing_time', 0.0),
                status='success' if result.get('success') else 'failure',
                error_message=result.get('error')
            )
            
            # Link to translation record
            if translation_record:
                if isinstance(translation_record, TextTranslation):
                    log_entry.text_translation = translation_record
                elif isinstance(translation_record, SpeechTranslation):
                    log_entry.speech_translation = translation_record
                elif isinstance(translation_record, ImageTranslation):
                    log_entry.image_translation = translation_record
                log_entry.save()
        except Exception as e:
            logger.error(f"Failed to log LLM usage: {str(e)}")

    def _generate_default_title(self, text: Optional[str] = None, file_obj: Optional[Any] = None, 
                               url: Optional[str] = None, prefix: str = "Translation") -> str:
        """Generate a default title from content"""
        if text:
            # First 50 chars or first line
            clean_text = text.strip()
            if clean_text:
                title = clean_text[:50].split('\n')[0]
                return title + ("..." if len(clean_text) > 50 else "")
        
        if file_obj and hasattr(file_obj, 'name'):
            return f"{prefix}: {file_obj.name}"
        
        if url:
            # Extract filename from URL
            from urllib.parse import urlparse
            import os
            try:
                path = urlparse(url).path
                filename = os.path.basename(path)
                if filename:
                    return f"{prefix}: {filename}"
            except Exception:
                pass
        
        return f"{prefix} {int(time.time())}"

    def translate_text(self, user, text: Optional[str], target_lang: str, source_lang: str = 'auto', 
                      is_sms: bool = False, mode: str = 'SHORT', session_id: Optional[str] = None,
                      original_file_url: Optional[str] = None, title: Optional[str] = None) -> Dict[str, Any]:
        """Orchestrate text-to-text translation"""
        start_time = time.time()
        
        # Generate default title if not provided
        if not title:
            title = self._generate_default_title(text=text, url=original_file_url, prefix="Text")
            
        # Create record
        translation_record = TextTranslation.objects.create(
            user=user,
            title=title,
            original_text=text,
            original_language=source_lang,
            target_language=target_lang,
            is_sms=is_sms,
            mode=mode,
            session_id=session_id,
            original_file_url=original_file_url,
            status=TranslationStatus.PROCESSING
        )
        
        try:
            # Handle empty text with valid URL
            if not text and original_file_url:
                import requests
                # Download and extract logic ...
                response = requests.get(original_file_url, timeout=120)
                response.raise_for_status()
                text = response.text
                translation_record.original_text = text[:1000] + "..." if len(text) > 1000 else text
                translation_record.save()

            # Execute translation
            result = self.translator.translate(text, source_lang, target_lang)
            
            # Log usage
            self._log_usage(user, result, 'Translation', translation_record)
            
            if result['success']:
                translation_record.translated_text = result['translated_text']
                translation_record.status = TranslationStatus.COMPLETED
            else:
                translation_record.status = TranslationStatus.FAILED
                translation_record.error_message = result.get('error', 'Translation failed')
            
            translation_record.total_processing_time = time.time() - start_time
            translation_record.save()
            
            return {
                'success': result['success'],
                'translation_id': str(translation_record.id),
                'original_text': translation_record.original_text,
                'translated_text': translation_record.translated_text,
                'error': translation_record.error_message
            }
            
        except Exception as e:
            logger.error(f"Orchestrator error in text translation: {str(e)}")
            translation_record.status = TranslationStatus.FAILED
            translation_record.error_message = str(e)
            translation_record.save()
            return {'success': False, 'error': str(e)}

    def translate_speech(self, user, audio_file: Any, target_lang: str, source_lang: str = 'auto', 
                         mode: str = 'SHORT', session_id: Optional[str] = None, 
                         original_file_url: Optional[str] = None,
                         translation_id: Optional[str] = None, title: Optional[str] = None) -> Dict[str, Any]:
        """Orchestrate speech-to-speech translation"""
        start_time = time.time()
        
        if translation_id:
            translation_record = SpeechTranslation.objects.get(id=translation_id)
            if translation_record.status != TranslationStatus.PROCESSING:
                translation_record.status = TranslationStatus.PROCESSING
                translation_record.save()
        else:
            # Generate default title if not provided
            if not title:
                title = self._generate_default_title(file_obj=audio_file, url=original_file_url, prefix="Speech")
                
            # Create record
            translation_record = SpeechTranslation.objects.create(
                user=user,
                title=title,
                original_language=source_lang,
                target_language=target_lang,
                mode=mode,
                session_id=session_id,
                original_audio_url=original_file_url,
                status=TranslationStatus.PROCESSING,
                speech_service=SpeechServiceType.STS
            )
        
        # Save original audio (locally + cloud upload + local cleanup)
        if audio_file and not isinstance(audio_file, (str, bytes)) and hasattr(audio_file, 'name'):
            self._save_input_audio(
                translation_record=translation_record,
                audio_file=audio_file,
                filename=f"input_{translation_record.id}.wav",
                user_id=translation_record.user_id,
                language=translation_record.original_language
            )
        
        try:
            # 1. ASR - Convert speech to text
            asr_result = self.asr.transcribe(audio_file or original_file_url, source_lang)
            self._log_usage(user, asr_result, 'ASR', translation_record)
            
            if not asr_result['success']:
                raise Exception(f"ASR failed: {asr_result.get('error')}")
            
            translation_record.original_text = asr_result['text']
            translation_record.original_language = asr_result.get('language', source_lang)
            translation_record.confidence_score = asr_result.get('confidence', 0.0)
            
            # 2. Translation
            trans_result = self.translator.translate(asr_result['text'], translation_record.original_language, target_lang)
            self._log_usage(user, trans_result, 'Translation', translation_record)
            
            if not trans_result['success']:
                raise Exception(f"Translation failed: {trans_result.get('error')}")
            
            translation_record.translated_text = trans_result['translated_text']
            
            # 3. TTS - Synthesize (If mode is SHORT or explicitly requested)
            if mode == 'SHORT':
                tts_result = self.tts.synthesize(translation_record.translated_text, target_lang)
                self._log_usage(user, tts_result, 'TTS', translation_record)
                
                if tts_result['success'] and tts_result['audio_data']:
                    # Save translated audio (locally + cloud upload + local cleanup)
                    self._save_audio(
                        translation_record=translation_record,
                        audio_data=tts_result['audio_data'],
                        filename=f"output_{translation_record.id}.wav",
                        user_id=translation_record.user_id,
                        language=translation_record.target_language
                    )
            
            translation_record.status = TranslationStatus.COMPLETED
            translation_record.total_processing_time = time.time() - start_time
            translation_record.save()
            
            # Prefer the cloud URL when available, fall back to local FileField URLs
            translated_audio_url = (
                translation_record.translated_audio_url
                or (translation_record.translated_audio.url if translation_record.translated_audio else None)
            )
            original_audio_url = (
                translation_record.original_audio_url
                or (translation_record.original_audio.url if translation_record.original_audio else None)
            )
            
            return {
                'success': True,
                'translation_id': str(translation_record.id),
                'original_text': translation_record.original_text,
                'translated_text': translation_record.translated_text,
                'original_audio_url': original_audio_url,
                'translated_audio_url': translated_audio_url
            }
            
        except Exception as e:
            logger.error(f"Orchestrator error in speech translation: {str(e)}")
            translation_record.status = TranslationStatus.FAILED
            translation_record.error_message = str(e)
            translation_record.save()
            return {'success': False, 'error': str(e)}
            
    def speech_to_text(self, user, audio_file: Any, source_language: str = 'auto', 
                       target_language: Optional[str] = None,
                       mode: str = 'SHORT', session_id: Optional[str] = None,
                       original_file_url: Optional[str] = None,
                       translation_id: Optional[str] = None, title: Optional[str] = None) -> Dict[str, Any]:
        """Standalone Speech-to-Text (ASR) with optional translation"""
        # Maintain backward compatibility if language was passed positionally
        # (Though we prefer keyword arguments now)
        target_lang = target_language or source_language
        start_time = time.time()
        
        if translation_id:
            translation_record = SpeechTranslation.objects.get(id=translation_id)
            if translation_record.status != TranslationStatus.PROCESSING:
                translation_record.status = TranslationStatus.PROCESSING
                translation_record.save()
        else:
            # Generate default title if not provided
            if not title:
                title = self._generate_default_title(file_obj=audio_file, url=original_file_url, prefix="STT")
                
            # Create record
            translation_record = SpeechTranslation.objects.create(
                user=user,
                title=title,
                original_language=source_language,
                target_language=target_lang,
                mode=mode,
                session_id=session_id,
                original_audio_url=original_file_url,
                status=TranslationStatus.PROCESSING,
                speech_service=SpeechServiceType.STT
            )
        
        # Save audio file if provided (locally + cloud upload + local cleanup)
        if audio_file and not isinstance(audio_file, (str, bytes)) and hasattr(audio_file, 'name'):
            self._save_input_audio(
                translation_record=translation_record,
                audio_file=audio_file,
                filename=f"stt_input_{translation_record.id}.wav",
                user_id=translation_record.user_id,
                language=translation_record.original_language
            )
            
        try:
            # Execute ASR
            asr_result = self.asr.transcribe(audio_file or original_file_url, source_language)
            self._log_usage(user, asr_result, 'ASR', translation_record)
            
            if not asr_result['success']:
                raise Exception(f"ASR failed: {asr_result.get('error')}")
            
            transcription = asr_result['text']
            detected_source_lang = asr_result.get('language', source_language)
            
            # Update record with transcription
            translation_record.original_text = transcription
            translation_record.original_language = detected_source_lang
            translation_record.confidence_score = asr_result.get('confidence', 0.0)
            
            # Optional: Perform translation if target differs from source
            final_text = ''
            if target_lang != detected_source_lang and target_lang != 'auto':
                trans_result = self.translator.translate(transcription, detected_source_lang, target_lang)
                self._log_usage(user, trans_result, 'Translation', translation_record)
                if trans_result['success']:
                    final_text = trans_result['translated_text']
            
            translation_record.translated_text = final_text
            translation_record.status = TranslationStatus.COMPLETED
            translation_record.total_processing_time = time.time() - start_time
            translation_record.save()
            
            # Prefer the cloud URL when available, fall back to local FileField URL
            original_audio_url = (
                translation_record.original_audio_url
                or (translation_record.original_audio.url if translation_record.original_audio else None)
            )
            
            return {
                'success': True,
                'translation_id': str(translation_record.id),
                'original_text': transcription,
                'translated_text': final_text,
                'original_audio_url': original_audio_url,
                'language': translation_record.original_language,
                'confidence': translation_record.confidence_score
            }
            
        except Exception as e:
            logger.error(f"Orchestrator error in STT: {str(e)}")
            translation_record.status = TranslationStatus.FAILED
            translation_record.error_message = str(e)
            translation_record.save()
            return {'success': False, 'error': str(e)}

    def text_to_speech(self, user, text: str, source_language: str = 'en', 
                       target_language: Optional[str] = None, voice: Optional[str] = None,
                       mode: str = 'SHORT', session_id: Optional[str] = None,
                       translation_id: Optional[str] = None, title: Optional[str] = None) -> Dict[str, Any]:
        """Standalone Text-to-Speech (TTS) with optional translation"""
        target_lang = target_language or source_language
        start_time = time.time()
        
        if translation_id:
            translation_record = SpeechTranslation.objects.get(id=translation_id)
            if translation_record.status != TranslationStatus.PROCESSING:
                translation_record.status = TranslationStatus.PROCESSING
                translation_record.save()
        else:
            # Generate default title if not provided
            if not title:
                title = self._generate_default_title(text=text, prefix="TTS")
                
            # Create record
            translation_record = SpeechTranslation.objects.create(
                user=user,
                title=title,
                original_language=source_language,
                target_language=target_lang,
                original_text=text,
                mode=mode,
                session_id=session_id,
                status=TranslationStatus.PROCESSING,
                speech_service=SpeechServiceType.TTS
            )
        
        try:
            # 1. Optional: Translate text if target language differs
            text_to_synthesize = text
            if target_lang != source_language and source_language != 'auto':
                trans_result = self.translator.translate(text, source_language, target_lang)
                self._log_usage(user, trans_result, 'Translation', translation_record)
                if trans_result['success']:
                    text_to_synthesize = trans_result['translated_text']
            
            translation_record.translated_text = text_to_synthesize
            
            # 2. Execute TTS with target language
            tts_result = self.tts.synthesize(text_to_synthesize, target_lang, voice)
            self._log_usage(user, tts_result, 'TTS', translation_record)
            
            if not tts_result['success'] or not tts_result['audio_data']:
                raise Exception(f"TTS failed: {tts_result.get('error')}")
            
            # Save translated audio (locally + cloud upload + local cleanup)
            self._save_audio(
                translation_record=translation_record,
                audio_data=tts_result['audio_data'],
                filename=f"tts_output_{translation_record.id}.wav",
                user_id=translation_record.user_id,
                language=translation_record.target_language
            )
            
            translation_record.status = TranslationStatus.COMPLETED
            translation_record.total_processing_time = time.time() - start_time
            translation_record.save()
            
            # Prefer the cloud URL when available, fall back to local FileField URL
            translated_audio_url = (
                translation_record.translated_audio_url
                or (translation_record.translated_audio.url if translation_record.translated_audio else None)
            )
            return {
                'success': True,
                'translation_id': str(translation_record.id),
                'translated_audio_url': translated_audio_url,
                'original_text': translation_record.original_text,
                'translated_text': translation_record.translated_text
            }
            
        except Exception as e:
            logger.error(f"Orchestrator error in TTS: {str(e)}")
            translation_record.status = TranslationStatus.FAILED
            translation_record.error_message = str(e)
            translation_record.save()
            return {'success': False, 'error': str(e)}

    def translate_image(self, user, image_file, target_lang: str, source_lang: str = 'auto', 
                        title: Optional[str] = None) -> Dict[str, Any]:
        """Orchestrate image-based OCR translation using Gemini Vision"""
        start_time = time.time()
        
        # Generate default title if not provided
        if not title:
            title = self._generate_default_title(file_obj=image_file, prefix="Image")
            
        # Create record
        translation_record = ImageTranslation.objects.create(
            user=user,
            title=title,
            original_language=source_lang,
            target_language=target_lang,
            status=TranslationStatus.PROCESSING
        )
        # Save original image (locally + cloud upload + local cleanup)
        self._save_input_image(
            translation_record=translation_record,
            image_file=image_file,
            filename=f"input_{translation_record.id}.png",
            user_id=translation_record.user_id,
            language=translation_record.original_language
        )
        
        try:
            # Gemini can do OCR and Translation in one go if prompted correctly
            # Reset file pointer
            image_file.seek(0)
            image_data = image_file.read()
            
            prompt = f"""Perform OCR on this image. Extract all text and then translate it to {target_lang}. 
            Format the output as follows:
            OCR: [Original extracted text]
            TRANSLATION: [Translated text]"""
            
            from google import genai
            from google.genai import types
            from django.conf import settings
            
            # Using the same client as providers for consistency
            client = genai.Client(api_key=settings.GEMINI_API_KEY)
            
            # Note: We're doing a manual call here for Image, 
            # ideally this should also be a provider but let's log it manually
            start_ai = time.time()
            response = client.models.generate_content(
                model="gemini-2.0-flash", 
                contents=[
                    types.Part.from_bytes(data=image_data, mime_type="image/png"),
                    prompt
                ]
            )
            ai_latency = time.time() - start_ai
            
            # Log manual call
            usage = None
            if hasattr(response, 'usage_metadata'):
                usage = {
                    'prompt_tokens': response.usage_metadata.prompt_token_count,
                    'candidates_tokens': response.usage_metadata.candidates_token_count,
                    'total_tokens': response.usage_metadata.total_token_count
                }
            
            self._log_usage(user, {
                'success': True,
                'usage': usage,
                'processing_time': ai_latency,
                'model': 'gemini-2.0-flash',
                'provider': 'Google'
            }, 'Image', translation_record)
            
            # Parse response
            full_text = response.text if response.text else ""
            ocr_text = ""
            translated_text = ""
            
            if "OCR:" in full_text and "TRANSLATION:" in full_text:
                parts = full_text.split("TRANSLATION:")
                ocr_text = parts[0].replace("OCR:", "").strip()
                translated_text = parts[1].strip()
            else:
                translated_text = full_text
            
            translation_record.ocr_text = ocr_text
            translation_record.translated_text = translated_text
            translation_record.status = TranslationStatus.COMPLETED
            translation_record.total_processing_time = time.time() - start_time
            translation_record.save()
            
            # Prefer the cloud URL when available, fall back to local FileField URL
            image_url = (
                translation_record.original_image_url
                or (translation_record.original_image.url if translation_record.original_image else None)
            )
            
            return {
                'success': True,
                'translation_id': str(translation_record.id),
                'ocr_text': ocr_text,
                'translated_text': translated_text,
                'image_url': image_url
            }
            
        except Exception as e:
            logger.error(f"Orchestrator error in image translation: {str(e)}")
            translation_record.status = TranslationStatus.FAILED
            translation_record.error_message = str(e)
            translation_record.save()
            return {'success': False, 'error': str(e)}

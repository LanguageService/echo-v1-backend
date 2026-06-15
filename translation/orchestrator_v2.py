import logging
import time
import io
from typing import Dict, Any, Optional
import numpy as np
import soundfile as sf
from django.core.files.base import ContentFile

from .models import TextTranslation, SpeechTranslation
from .choices import TranslationStatus, TranslationMode, SpeechServiceType
from .providers.v2_pipelines import pipeline_manager
from .orchestrator import TranslationOrchestrator  # to reuse some helper methods like _save_audio

logger = logging.getLogger(__name__)

class TranslationOrchestratorV2(TranslationOrchestrator):
    """
    Orchestrates translation workflows using local V2 custom models pipelines
    specifically for English <-> Kinyarwanda.
    """

    def __init__(self):
        # We don't initialize standard providers, we rely on pipeline_manager
        pass

    def _read_audio(self, audio_file) -> tuple[np.ndarray, int]:
        """Convert Django uploaded file to numpy array."""
        try:
            audio_file.seek(0)
            data = audio_file.read()
            audio, sr = sf.read(io.BytesIO(data))
            if audio.ndim > 1:
                audio = audio.mean(axis=1)
            return audio.astype(np.float32), int(sr)
        except Exception as exc:
            logger.error(f"Cannot decode audio: {exc}")
            raise Exception(f"Cannot decode audio: {exc}")

    def _to_wav(self, audio: np.ndarray, sample_rate: int) -> bytes:
        """Convert numpy array back to WAV bytes."""
        buf = io.BytesIO()
        sf.write(buf, audio, sample_rate, format="WAV", subtype="FLOAT")
        return buf.getvalue()

    def translate_text(self, user, text: Optional[str], target_lang: str, source_lang: str = 'auto',
                       is_sms: bool = False, mode: str = 'SHORT', session_id: Optional[str] = None,
                       original_file_url: Optional[str] = None, title: Optional[str] = None) -> Dict[str, Any]:
        """Text-to-text translation using V2 models."""
        start_time = time.time()
        
        if not title:
            title = self._generate_default_title(text=text, url=original_file_url, prefix="Text (V2)")
            
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
            if not text and original_file_url:
                import requests
                response = requests.get(original_file_url, timeout=120)
                response.raise_for_status()
                text = response.text
                translation_record.original_text = text[:1000] + "..." if len(text) > 1000 else text
                translation_record.save()

            if not text:
                raise Exception("No text provided")

            # Route based on language
            # We assume source and target are explicitly set or easily inferred for EN/KIN
            # English -> Kinyarwanda
            if target_lang == 'rw':
                translation_record.original_language = 'en'
                result_text = pipeline_manager.en_kin.translate(text)
            # Kinyarwanda -> English
            elif target_lang == 'en':
                translation_record.original_language = 'rw'
                result_text = pipeline_manager.kin_en.translate(text)
            else:
                raise Exception("V2 API only supports English <-> Kinyarwanda")

            translation_record.translated_text = result_text
            translation_record.status = TranslationStatus.COMPLETED
            translation_record.total_processing_time = time.time() - start_time
            translation_record.save()
            
            return {
                'success': True,
                'translation_id': str(translation_record.id),
                'original_text': translation_record.original_text,
                'translated_text': translation_record.translated_text
            }
            
        except Exception as e:
            logger.error(f"V2 Orchestrator error in text translation: {str(e)}")
            translation_record.status = TranslationStatus.FAILED
            translation_record.error_message = str(e)
            translation_record.save()
            return {'success': False, 'error': str(e)}


    def speech_to_text(self, user, audio_file: Any, source_language: str = 'auto', 
                       target_language: Optional[str] = None,
                       mode: str = 'SHORT', session_id: Optional[str] = None,
                       original_file_url: Optional[str] = None,
                       translation_id: Optional[str] = None, title: Optional[str] = None) -> Dict[str, Any]:
        """Speech-to-Text (ASR) using V2 models."""
        target_lang = target_language or source_language
        start_time = time.time()
        
        if translation_id:
            translation_record = SpeechTranslation.objects.get(id=translation_id)
            translation_record.status = TranslationStatus.PROCESSING
            translation_record.save()
        else:
            if not title:
                title = self._generate_default_title(file_obj=audio_file, url=original_file_url, prefix="STT (V2)")
                
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
        
        if audio_file and hasattr(audio_file, 'name'):
            self._save_input_audio(
                translation_record=translation_record,
                audio_file=audio_file,
                filename=f"stt_input_{translation_record.id}.wav",
                user_id=translation_record.user_id,
                language=translation_record.original_language
            )
            
        try:
            if not audio_file:
                raise Exception("No audio file provided")

            audio_np, sr = self._read_audio(audio_file)

            if source_language == 'en':
                transcription = pipeline_manager.en_kin.transcribe(audio_np, sr)
                detected_source_lang = 'en'
            elif source_language == 'rw':
                transcription = pipeline_manager.kin_en.transcribe(audio_np, sr)
                detected_source_lang = 'rw'
            else:
                # Default assume English if auto for now, ideally we should detect
                transcription = pipeline_manager.en_kin.transcribe(audio_np, sr)
                detected_source_lang = 'en'

            translation_record.original_text = transcription
            translation_record.original_language = detected_source_lang
            
            final_text = ''
            if target_lang != detected_source_lang and target_lang != 'auto':
                if target_lang == 'rw':
                    final_text = pipeline_manager.en_kin.translate(transcription)
                elif target_lang == 'en':
                    final_text = pipeline_manager.kin_en.translate(transcription)
            
            translation_record.translated_text = final_text
            translation_record.status = TranslationStatus.COMPLETED
            translation_record.total_processing_time = time.time() - start_time
            translation_record.save()
            
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
                'language': translation_record.original_language
            }
            
        except Exception as e:
            logger.error(f"V2 Orchestrator error in STT: {str(e)}")
            translation_record.status = TranslationStatus.FAILED
            translation_record.error_message = str(e)
            translation_record.save()
            return {'success': False, 'error': str(e)}

    def text_to_speech(self, user, text: str, source_language: str = 'en', 
                       target_language: Optional[str] = None, voice: Optional[str] = None,
                       mode: str = 'SHORT', session_id: Optional[str] = None,
                       translation_id: Optional[str] = None, title: Optional[str] = None) -> Dict[str, Any]:
        """Text-to-Speech (TTS) using V2 models."""
        target_lang = target_language or source_language
        start_time = time.time()
        
        if translation_id:
            translation_record = SpeechTranslation.objects.get(id=translation_id)
            translation_record.status = TranslationStatus.PROCESSING
            translation_record.save()
        else:
            if not title:
                title = self._generate_default_title(text=text, prefix="TTS (V2)")
                
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
            text_to_synthesize = text
            if target_lang != source_language and source_language != 'auto':
                if target_lang == 'rw':
                    text_to_synthesize = pipeline_manager.en_kin.translate(text)
                elif target_lang == 'en':
                    text_to_synthesize = pipeline_manager.kin_en.translate(text)
            
            translation_record.translated_text = text_to_synthesize
            
            # Synthesize
            speaker = voice or ("male" if target_lang == 'en' else "male")
            if target_lang == 'rw':
                tts_sr, audio_np = pipeline_manager.en_kin.synthesize(text_to_synthesize, speaker=speaker)
            elif target_lang == 'en':
                tts_sr, audio_np = pipeline_manager.kin_en.synthesize(text_to_synthesize, speaker=speaker)
            else:
                raise Exception("V2 TTS only supports English and Kinyarwanda")
            
            audio_bytes = self._to_wav(audio_np, tts_sr)
            
            self._save_audio(
                translation_record=translation_record,
                audio_data=audio_bytes,
                filename=f"tts_v2_output_{translation_record.id}.wav",
                user_id=translation_record.user_id,
                language=translation_record.target_language
            )
            
            translation_record.status = TranslationStatus.COMPLETED
            translation_record.total_processing_time = time.time() - start_time
            translation_record.save()
            
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
            logger.error(f"V2 Orchestrator error in TTS: {str(e)}")
            translation_record.status = TranslationStatus.FAILED
            translation_record.error_message = str(e)
            translation_record.save()
            return {'success': False, 'error': str(e)}

    def translate_speech(self, user, audio_file: Any, target_lang: str, source_lang: str = 'auto', 
                         mode: str = 'SHORT', session_id: Optional[str] = None, 
                         original_file_url: Optional[str] = None,
                         translation_id: Optional[str] = None, title: Optional[str] = None) -> Dict[str, Any]:
        """Speech-to-Speech (STS) translation using V2 models."""
        start_time = time.time()
        
        if translation_id:
            translation_record = SpeechTranslation.objects.get(id=translation_id)
            translation_record.status = TranslationStatus.PROCESSING
            translation_record.save()
        else:
            if not title:
                title = self._generate_default_title(file_obj=audio_file, url=original_file_url, prefix="Speech (V2)")
                
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
        
        if audio_file and hasattr(audio_file, 'name'):
            self._save_input_audio(
                translation_record=translation_record,
                audio_file=audio_file,
                filename=f"input_{translation_record.id}.wav",
                user_id=translation_record.user_id,
                language=translation_record.original_language
            )
        
        try:
            if not audio_file:
                raise Exception("No audio file provided")

            audio_np, sr = self._read_audio(audio_file)
            
            # English -> Kinyarwanda
            if target_lang == 'rw':
                translation_record.original_language = 'en'
                result = pipeline_manager.en_kin.run(audio_np, sr)
                
                translation_record.original_text = result["english_text"]
                translation_record.translated_text = result["kinyarwanda_text"]
                tts_sr = result["sample_rate"]
                kin_audio = result["audio"]
                
                audio_bytes = self._to_wav(kin_audio, tts_sr)
                
            # Kinyarwanda -> English
            elif target_lang == 'en':
                translation_record.original_language = 'rw'
                result = pipeline_manager.kin_en.run(audio_np, sr)
                
                translation_record.original_text = result["kinyarwanda_text"]
                translation_record.translated_text = result["english_text"]
                tts_sr = result["sample_rate"]
                en_audio = result["audio"]
                
                audio_bytes = self._to_wav(en_audio, tts_sr)
            else:
                raise Exception("V2 STS only supports English and Kinyarwanda")

            self._save_audio(
                translation_record=translation_record,
                audio_data=audio_bytes,
                filename=f"output_{translation_record.id}.wav",
                user_id=translation_record.user_id,
                language=translation_record.target_language
            )
            
            translation_record.status = TranslationStatus.COMPLETED
            translation_record.total_processing_time = time.time() - start_time
            translation_record.save()
            
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
            logger.error(f"V2 Orchestrator error in STS: {str(e)}")
            translation_record.status = TranslationStatus.FAILED
            translation_record.error_message = str(e)
            translation_record.save()
            return {'success': False, 'error': str(e)}

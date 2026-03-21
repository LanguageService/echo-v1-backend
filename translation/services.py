"""
Voice Translation Services

Service classes for handling speech-to-text, text-to-speech, translation,
and audio processing using Google Gemini AI.
"""

import os
import logging
import time
import io
import wave
import base64
import asyncio
import struct
import json
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Any, Optional, BinaryIO, List
from google import genai
from google.genai import types
from langdetect import detect
from asgiref.sync import sync_to_async
from django.conf import settings
from django.db import transaction
from .models import TextTranslation, SpeechTranslation, ImageTranslation, UserSettings, AudioFile, LanguageSupport
import uuid
from .choices import FeatureType, TranslationStatus, TranslationMode
from .cloud_storage import cloud_storage
from .document_processors import DocxProcessor, PdfProcessor
from decouple import config
import requests
import tempfile
import shutil

logger = logging.getLogger(__name__)



# Initialize Gemini client
client = genai.Client(api_key=config("GEMINI_API_KEY",""))


class GeminiService:
    """Base service for Google Gemini AI operations"""
    
    def __init__(self):
        self.model = "gemini-2.5-flash"
        self.pro_model = "gemini-2.5-pro"
    
    def get_model(self, use_pro: bool = False) -> str:
        """Get the appropriate model based on settings"""
        return self.pro_model if use_pro else self.model

    def _detect_language_with_ai(self, text: str) -> str:
        """
        Use Gemini AI to detect language of text, especially good for African languages
        """
        try:
            if not text or len(text.strip()) == 0:
                return 'en'
                
            prompt = f"""Identify the language of this text and return ONLY the ISO 639-1 language code (2 letters).

Pay special attention to African languages:
- Kinyarwanda (rw) - common words: ubwoba, uyu, munsi, hamwe, ndabakunda, mwiza, reka
- Swahili (sw) - common words: hali, haya, siku, pamoja, ninawapenda, nzuri, hebu
- Hausa (ha) - common words: wannan, rana, tare, ina, kyakkyawa
- Yoruba (yo) - common words: eyi, ojo, pelu, mo, dara
- Igbo (ig) - common words: nke, ubochi, na, a, mma

Text: "{text[:500]}"

Language code:"""

            response = client.models.generate_content(
                model=self.model,
                contents=prompt
            )
            
            detected_code = response.text.strip().lower() if response.text else 'en'
            
            if len(detected_code) == 2 and detected_code.isalpha():
                logger.info(f"AI language detection: '{text[:50]}...' -> {detected_code}")
                return detected_code
            else:
                return detect(text)
                
        except Exception as e:
            logger.error(f"AI language detection failed: {str(e)}")
            try:
                return detect(text)
            except:
                return 'en'
    
    def _get_language_name(self, code: str) -> str:
        """Get full language name from code"""
        try:
            from .models import LanguageSupport
            language = LanguageSupport.objects.get(code=code)
            return language.name
        except Exception:
            return code.upper()


class SpeechService(GeminiService):
    """Service for handling speech-to-text operations"""
    
    def transcribe_audio(self, audio_file: BinaryIO, language: str = 'auto') -> Dict[str, Any]:
        """
        Convert speech to text using Gemini AI
        
        Args:
            audio_file: Audio file binary data
            language: Source language code (auto for auto-detection)
            
        Returns:
            Dictionary with transcription results
        """
        try:
            start_time = time.time()
            
            # Read audio data
            audio_data = audio_file.read()
            if isinstance(audio_file, str):
                with open(audio_file, 'rb') as f:
                    audio_data = f.read()
            
            # Create transcription prompt
            if language == 'auto':
                prompt = """Transcribe the speech in this audio file to text. Detect the language automatically and return the transcribed text exactly as spoken, preserving all words, names, and expressions. If you cannot detect any speech, return an empty string."""
            else:
                lang_name = self._get_language_name(language)
                prompt = f"""Transcribe the speech in this audio file to text. The audio is in {lang_name}. Return the transcribed text exactly as spoken, preserving all words, names, and expressions. If you cannot detect any speech, return an empty string."""
            
            # Process audio with Gemini
            response = client.models.generate_content(
                model=self.model,
                contents=[
                    types.Part.from_bytes(
                        data=audio_data,
                        mime_type="audio/wav",
                    ),
                    prompt
                ]
            )
            
            transcribed_text = response.text.strip() if response.text else ""
            processing_time = time.time() - start_time
            
            # Auto-detect language if not specified
            detected_language = language
            if language == 'auto' and transcribed_text:
                try:
                    # Use Gemini AI for more accurate language detection, especially for African languages
                    detected_language = self._detect_language_with_ai(transcribed_text)
                except:
                    try:
                        # Fallback to langdetect
                        detected_language = detect(transcribed_text)
                    except:
                        detected_language = 'en'  # final fallback
            
            # Calculate confidence based on transcription quality
            confidence = self._calculate_speech_confidence(transcribed_text, processing_time)
            
            logger.info(f"Speech-to-text completed in {processing_time:.2f}s. Language: {detected_language}")
            
            return {
                'text': transcribed_text,
                'language': detected_language,
                'confidence': confidence,
                'processing_time': processing_time,
                'success': bool(transcribed_text)
            }
            
        except Exception as e:
            logger.error(f"Error in speech-to-text: {str(e)}")
            return {
                'text': '',
                'language': language if language != 'auto' else 'unknown',
                'confidence': 0.0,
                'processing_time': time.time() - start_time if 'start_time' in locals() else 0.0,
                'success': False,
                'error': str(e)
            }
    
    def _calculate_speech_confidence(self, transcribed_text: str, processing_time: float) -> float:
        """Calculate speech-to-text confidence based on transcription quality"""
        if not transcribed_text:
            return 0.0
        
        base_confidence = 80.0
        
        # Text length and completeness
        text_length = len(transcribed_text.strip())
        words = transcribed_text.split()
        word_count = len(words)
        
        if text_length > 150:
            base_confidence += 12.0
        elif text_length > 80:
            base_confidence += 8.0
        elif text_length > 30:
            base_confidence += 4.0
        elif text_length < 10:
            base_confidence -= 25.0
        
        # Word structure and language patterns
        if word_count > 15:
            base_confidence += 8.0
        elif word_count > 8:
            base_confidence += 4.0
        elif word_count < 3:
            base_confidence -= 20.0
        
        # Processing time indicator (faster usually means clearer audio)
        if processing_time < 2.0:
            base_confidence += 10.0
        elif processing_time < 4.0:
            base_confidence += 5.0
        elif processing_time > 8.0:
            base_confidence -= 8.0
        
        # Check for sentence structure and punctuation
        if '.' in transcribed_text or '?' in transcribed_text or '!' in transcribed_text:
            base_confidence += 6.0
        
        # Check for proper capitalization (indicates clear speech)
        if any(word[0].isupper() for word in words if word):
            base_confidence += 5.0
        
        # Check for repetitive patterns (indicates poor audio quality)
        if any(transcribed_text.count(word) > 3 for word in words if len(word) > 3):
            base_confidence -= 15.0
        
        # Character diversity
        unique_chars = len(set(transcribed_text.lower()))
        if unique_chars > 12:
            base_confidence += 5.0
        elif unique_chars < 6:
            base_confidence -= 10.0
        
        return min(95.0, max(20.0, base_confidence))
    


class TranslationService(GeminiService):
    """Service for handling text translation operations"""
    
    def translate_text(self, text: str, source_lang: str, target_lang: str = 'en', 
                      use_pro: bool = False) -> Dict[str, Any]:
        """
        Translate text using Gemini AI
        
        Args:
            text: Text to translate
            source_lang: Source language code
            target_lang: Target language code
            use_pro: Whether to use Pro model
            
        Returns:
            Dictionary with translation results
        """
        try:
            start_time = time.time()
            
            if not text or len(text.strip()) == 0:
                return {
                    'translated_text': '',
                    'source_language': source_lang,
                    'target_language': target_lang,
                    'success': False,
                    'error': 'No text to translate'
                }
            
            # Skip translation if same language
            if source_lang == target_lang:
                return {
                    'translated_text': text,
                    'source_language': source_lang,
                    'target_language': target_lang,
                    'success': True,
                    'processing_time': 0.0,
                    'note': 'No translation needed - same language'
                }
            
            # Get language names
            source_name = self._get_language_name(source_lang)
            target_name = self._get_language_name(target_lang)
            
            # Create translation prompt
            prompt = f"""Translate the following text from {source_name} to {target_name}. Provide an accurate, natural translation that preserves the meaning and context. For names and proper nouns, translate their meanings when appropriate (especially for African names which often have specific meanings). Return only the translated text:

{text}"""
            
            # Use appropriate model
            model = self.get_model(use_pro)
            
            # Process translation with Gemini
            response = client.models.generate_content(
                model=model,
                contents=prompt
            )
            
            translated_text = response.text.strip() if response.text else ""
            processing_time = time.time() - start_time
            
            if not translated_text:
                raise ValueError("Empty translation response")
            
            logger.info(f"Translation completed in {processing_time:.2f}s: {source_lang} -> {target_lang}")
            
            return {
                'translated_text': translated_text,
                'source_language': source_lang,
                'target_language': target_lang,
                'processing_time': processing_time,
                'success': True
            }
            
        except Exception as e:
            logger.error(f"Error in translation: {str(e)}")
            return {
                'translated_text': '',
                'source_language': source_lang,
                'target_language': target_lang,
                'processing_time': time.time() - start_time if 'start_time' in locals() else 0.0,
                'success': False,
                'error': str(e)
            }
    

class TextToSpeechService(GeminiService):
    """Service for handling text-to-speech operations"""
    
    def synthesize_speech(self, text: str, language: str, voice: str = 'Zephyr') -> Dict[str, Any]:
        """
        Convert text to speech using Gemini AI
        
        Args:
            text: Text to convert to speech
            language: Language code
            voice: Voice selection
            
        Returns:
            Dictionary with speech synthesis results
        """
        try:
            start_time = time.time()
            
            if not text or len(text.strip()) == 0:
                return {
                    'success': False,
                    'error': 'No text to synthesize',
                    'audio_data': None
                }
            
            # Use Gemini TTS model
            model = "gemini-2.5-flash-preview-tts"
            
            # Map voice names if necessary, Gemini has specific voices like 'Aoede', 'Puck', 'Charon', 'Kore', 'Fenrir'
            # Default mapping from our app voices to Gemini voices
            voice_mapping = {
                'Zephyr': 'Puck', 
                'Echo': 'Aoede',
                'Sky': 'Kore',
                'Onyx': 'Fenrir'
            }
            gemini_voice = voice_mapping.get(voice, 'Aoede') 

            # Create TTS request
            response = client.models.generate_content(
                model=model,
                contents=text,
                config=types.GenerateContentConfig(
                    response_modalities=["AUDIO"],
                    speech_config=types.SpeechConfig(
                        voice_config=types.VoiceConfig(
                            prebuilt_voice_config=types.PrebuiltVoiceConfig(
                                voice_name=gemini_voice
                            )
                        )
                    )
                )
            )
            
            audio_data = None
            
            # Extract audio data
            if hasattr(response, 'candidates'):
                for cand in response.candidates:
                    if hasattr(cand, 'content') and hasattr(cand.content, 'parts'):
                        for part in cand.content.parts:
                            if hasattr(part, 'inline_data') and part.inline_data:
                                # Raw PCM data (usually 24kHz, 1 channel, 16-bit)
                                pcm_data = part.inline_data.data
                                # Wrap in WAV header
                                audio_data = self._pcm_to_wav(pcm_data)
                                logger.info(f"Generated real TTS audio: {len(audio_data)} bytes")
                                break
            
            if not audio_data:
                logger.warning("Gemini TTS returned no audio, falling back to silent generation")
                audio_data = self._generate_silent_wav(duration=1.0)
            
            logger.info(f"Text-to-speech request for {language} text (length: {len(text)})")
            
            processing_time = time.time() - start_time
            
            return {
                'success': True,
                'language': language,
                'voice': voice,
                'text_length': len(text),
                'processing_time': processing_time,
                'audio_data': audio_data,
                # 'note': 'TTS processed with Gemini 2.5 Flash TTS'
            }
            
        except Exception as e:
            logger.error(f"Error in text-to-speech: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'audio_data': None,
                'processing_time': time.time() - start_time if 'start_time' in locals() else 0.0
            }
    
    def _pcm_to_wav(self, pcm_data: bytes, sample_rate: int = 24000) -> bytes:
        """Convert raw PCM data to WAV format"""
        try:
            buffer = io.BytesIO()
            with wave.open(buffer, 'wb') as wav_file:
                wav_file.setnchannels(1)  # Mono
                wav_file.setsampwidth(2)  # 16-bit
                wav_file.setframerate(sample_rate)
                wav_file.writeframes(pcm_data)
            
            buffer.seek(0)
            return buffer.read()
        except Exception as e:
            logger.error(f"Error converting PCM to WAV: {e}")
            return None

    def _generate_silent_wav(self, duration: float = 1.0) -> bytes:
        """Generate a silent WAV file in memory"""
        try:
            buffer = io.BytesIO()
            with wave.open(buffer, 'wb') as wav_file:
                wav_file.setnchannels(1)  # mono
                wav_file.setsampwidth(2)  # 2 bytes per sample
                wav_file.setframerate(44100) # 44.1kHz
                
                num_samples = int(44100 * duration)
                
                # Write silence (0) - Optimized bulk write
                # 16-bit PCM silence is 0x0000
                data = b'\x00\x00' * num_samples
                wav_file.writeframes(data)
                    
            buffer.seek(0)
            data = buffer.read()
            logger.info(f"Generated silent WAV: {len(data)} bytes ({duration}s)")
            return data
        except Exception as e:
            logger.error(f"Failed to generate silent WAV: {e}")
            return None
            

    
    def _get_language_name(self, code: str) -> str:
        """Get full language name from code"""
        try:
            from .models import LanguageSupport
            language = LanguageSupport.objects.get(code=code)
            return language.name
        except Exception:
            # Fallback to uppercase code if DB is unavailable or language not found
            return code.upper()



class AudioService:
    """Service for audio file processing and management"""
    
    @staticmethod
    def validate_audio_file(audio_file) -> Dict[str, Any]:
        """
        Validate audio file format and size
        
        Args:
            audio_file: Django uploaded file
            
        Returns:
            Dictionary with validation results
        """
        try:
            from django.conf import settings
            # Check file size
            max_size = getattr(settings, 'MAX_AUDIO_FILE_SIZE', 10 * 1024 * 1024)
            if audio_file.size > max_size:
                return {
                    'valid': False,
                    'error': f'File too large. Maximum size is {max_size // (1024*1024)}MB'
                }
            
            # Check file format
            from django.conf import settings
            allowed_formats = getattr(settings, 'SUPPORTED_AUDIO_FORMATS', ['audio/wav', 'audio/mpeg', 'audio/mp4', 'audio/webm', 'audio/opus', 'audio/ogg'])
            if audio_file.content_type not in allowed_formats:
                return {
                    'valid': False,
                    'error': f'Unsupported format. Allowed: {", ".join(allowed_formats)}'
                }
            
            return {
                'valid': True,
                'size': audio_file.size,
                'format': audio_file.content_type
            }
            
        except Exception as e:
            return {
                'valid': False,
                'error': str(e)
            }
    
    @staticmethod
    def get_audio_duration(audio_file_path: str) -> float:
        """
        Get duration of audio file in seconds
        
        Args:
            audio_file_path: Path to audio file
            
        Returns:
            Duration in seconds
        """
        try:
            with wave.open(audio_file_path, 'rb') as wav_file:
                frames = wav_file.getnframes()
                sample_rate = wav_file.getframerate()
                duration = frames / float(sample_rate)
                return duration
        except Exception as e:
            logger.error(f"Error getting audio duration: {str(e)}")
            return 0.0


class VoiceTranslationService:
    """Main orchestrator service for complete voice translation pipeline"""
    
    def __init__(self):
        self.speech_service = SpeechService()
        self.translation_service = TranslationService()
        self.tts_service = TextToSpeechService()
        self.audio_service = AudioService()
    
    def process_voice_translation(self, user, audio_file, session_id: str = None, 
                                 target_language: str = 'en', mode: str = None) -> Dict[str, Any]:
        """
        Complete voice translation pipeline with automatic mode detection
        
        Args:
            audio_file: Audio file to process
            session_id: User session ID
            target_language: Target language for translation
            mode: Explicit mode ('SHORT' or 'LARGE'). If None, detected automatically.
            
        Returns:
            Dictionary with results (Sync) or task information (Async)
        """
        start_time = time.time()
        
        try:
            # 1. Validate audio file
            validation = self.audio_service.validate_audio_file(audio_file)
            if not validation['valid']:
                return {
                    'success': False,
                    'error': validation['error'],
                    'processing_time': time.time() - start_time
                }
            
            # 2. Determine Mode
            file_size = audio_file.size
            is_large = file_size > (5 * 1024 * 1024) # > 5MB
            
            # Try to get duration if possible (optional but helpful)
            # duration = self.audio_service.get_audio_duration(local_temp_path) 
            # (We'll stick to size for now as duration requires a local file)
            
            # Use explicit mode if provided, otherwise detect
            from .choices import TranslationMode, TranslationStatus
            final_mode = mode or (TranslationMode.LARGE if is_large else TranslationMode.SHORT)
            
            # 3. Handle LARGE mode (Asynchronous)
            if final_mode == TranslationMode.LARGE:
                logger.info(f"Large audio detected ({file_size} bytes). Moving to background...")
                
                # Save file locally for the worker
                temp_upload_dir = os.path.join(settings.MEDIA_ROOT, 'temp_uploads')
                os.makedirs(temp_upload_dir, exist_ok=True)
                
                original_filename = getattr(audio_file, 'name', 'audio_input.wav')
                file_ext = original_filename.split('.')[-1] if '.' in original_filename else 'wav'
                local_file_path = os.path.join(temp_upload_dir, f"voice_{uuid.uuid4().hex}.{file_ext}")
                
                with open(local_file_path, 'wb+') as destination:
                    for chunk in audio_file.chunks():
                        destination.write(chunk)
                
                # Create record
                from .models import TextTranslation
                translation_record = TextTranslation.objects.create(
                    user=user,
                    original_filename=original_filename,
                    target_language=target_language,
                    status=TranslationStatus.PENDING,
                    mode=TranslationMode.LARGE,
                    session_id=session_id or str(uuid.uuid4())
                )
                
                # Enqueue task
                from .tasks import async_voice_translation_task
                async_voice_translation_task.delay(
                    user_id=user.id if user else None,
                    audio_file_path=local_file_path,
                    translation_id=str(translation_record.id),
                    session_id=translation_record.session_id,
                    target_language=target_language
                )
                
                return {
                    'success': True,
                    'mode': TranslationMode.LARGE,
                    'status': TranslationStatus.PENDING,
                    'translation_id': str(translation_record.id),
                    'message': 'Large audio file is being processed in the background.',
                    'processing_time': time.time() - start_time
                }

            # 4. Handle SHORT mode (Synchronous)
            logger.info("Short audio detected. Processing synchronously...")
            # Existing sync logic...
            
            # Get user settings
            user_settings = None
            if user:
                try:
                    from .models import UserSettings
                    user_settings = UserSettings.objects.get(user=user)
                except UserSettings.DoesNotExist:
                    pass
            
            # Step 1: Speech to Text
            source_lang = user_settings.source_language if user_settings else 'auto'
            stt_result = self.speech_service.transcribe_audio(audio_file, source_lang)
            if not stt_result['success']:
                return {
                    'success': False,
                    'error': f"Speech-to-text failed: {stt_result.get('error', 'Unknown error')}",
                    'processing_time': time.time() - start_time
                }
            
            original_text = stt_result['text']
            detected_language = stt_result['language']
            
            # Step 2: Translation : text to text
            logger.info("Starting text translation...")
            use_pro = settings.model == 'gemini-2.5-pro' if settings else False
            
            translation_result = self.translation_service.translate_text(
                original_text, detected_language, target_language, use_pro
            )
            
            if not translation_result['success']:
                return {
                    'success': False,
                    'error': f"Translation failed: {translation_result.get('error', 'Unknown error')}",
                    'processing_time': time.time() - start_time,
                    'original_text': original_text,
                    'detected_language': detected_language
                }
            
            translated_text = translation_result['translated_text']
            
            # Step 3: Text to Speech (optional)
            tts_result = None
            # if settings :
            logger.info("Starting text-to-speech synthesis...")
            voice = settings.voice if settings else 'Zephyr'
            tts_result = self.tts_service.synthesize_speech(
                translated_text, target_language, voice
            )
            
            # Upload input audio to cloud storage
            original_audio_url = None
            original_filename = getattr(audio_file, 'name', 'audio_input')
            audio_format = original_filename.split('.')[-1].lower() if '.' in original_filename else 'wav'
            
            if cloud_storage.is_available():
                try:
                    # Reset file position for upload
                    audio_file.seek(0)
                    original_audio_url = cloud_storage.upload_voice_input_file(
                        audio_file, detected_language, str(user.id) if user else 'anonymous'
                    )
                    logger.info(f"Uploaded input audio to cloud storage: {original_audio_url}")
                except Exception as e:
                    logger.warning(f"Failed to upload input audio to cloud storage: {e}")
            
            # Upload output audio to cloud storage (if TTS was successful)
            translated_audio_url = None
            logger.info(f"TTS result: {tts_result}")
            if tts_result and tts_result.get('success') and tts_result.get('audio_data'):
                if cloud_storage.is_available():
                    try:
                        translated_audio_url = cloud_storage.upload_voice_output_file(
                            tts_result['audio_data'], target_language, 
                            str(user.id) if user else 'anonymous', 'wav'
                        )
                        logger.info(f"Uploaded output audio to cloud storage: {translated_audio_url}")
                    except Exception as e:
                        logger.warning(f"Failed to upload output audio to cloud storage: {e}")

            total_processing_time = time.time() - start_time
            
            # Save translation record
            from .models import SpeechTranslation
            translation_record = SpeechTranslation.objects.create(
                user=user,
                original_text=original_text,
                translated_text=translated_text,
                original_language=detected_language,
                target_language=target_language,
                original_audio_url=original_audio_url,
                translated_audio_url=translated_audio_url,
                original_filename=original_filename,
                audio_format=audio_format,
                confidence_score=stt_result['confidence'],
                total_processing_time=total_processing_time,
                session_id=session_id,
                feature_type=FeatureType.SPEECH_TRANSLATION
            )

            # Save processing times
            from .models import TextTranslation, SpeechTranslationProcessingTime
            
            TranslationProcessingTime.objects.create(
                translation=translation_record,
                speech_to_text=stt_result.get('processing_time', 0.0),
                text_to_text=translation_result.get('processing_time', 0.0),
                text_to_speech=tts_result.get('processing_time', 0.0) if tts_result else 0.0,
                total=total_processing_time
            )
            
            # Prepare response
            response = {
                'success': True,
                'translation_id': str(translation_record.id),
                'original_text': original_text,
                'translated_text': translated_text,
                'original_language': detected_language,
                'target_language': target_language,
                'original_audio_url': original_audio_url,
                'translated_audio_url': translated_audio_url,
                'confidence_score': stt_result['confidence'],
                'processing_time': total_processing_time,
                'steps': {
                    'speech_to_text': stt_result['processing_time'],
                    'translation': translation_result['processing_time'],
                    'text_to_speech': tts_result['processing_time'] if tts_result else 0
                }
            }
            
            if tts_result:
                response['audio_available'] = tts_result['success']
                response['tts_note'] = tts_result.get('note', '')
            
            logger.info(f"Voice translation completed in {response['processing_time']:.2f}s")
            return response
            
        except Exception as e:
            logger.error(f"Error in voice translation pipeline: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'processing_time': time.time() - start_time
            }


class DocumentTranslationService(GeminiService):
    """Service for handling document (PDF, DOCX) translation operations"""
    
    def __init__(self):
        super().__init__()
        self.docx_processor = DocxProcessor()
        self.pdf_processor = PdfProcessor()
        self.translation_service = TranslationService()

    def extract_document_text(self, uploaded_file) -> Dict[str, Any]:
        """
        Extract text from a document (PDF, DOCX) without cloud or DB dependencies.
        
        Args:
            uploaded_file: Django uploaded file or local file object
            
        Returns:
            Dictionary with extracted blocks and success status
        """
        start_time = time.time()
        if isinstance(uploaded_file, str):
            file_name = os.path.basename(uploaded_file)
        else:
            file_name = getattr(uploaded_file, 'name', 'document')
            
        file_ext = file_name.split('.')[-1].lower() if '.' in file_name else 'document'
        
        if file_ext not in ['pdf', 'docx', 'doc']:
            return {
                'success': False,
                'error': f"Unsupported file format: {file_ext}",
                'processing_time': time.time() - start_time
            }

        with tempfile.TemporaryDirectory() as temp_dir:
            input_path = os.path.join(temp_dir, f"input_{file_name}")
            
            # Save uploaded file to temp path
            if isinstance(uploaded_file, str):
                # If it's a path, copy the file
                shutil.copy2(uploaded_file, input_path)
            elif hasattr(uploaded_file, 'chunks'):
                # Django file with chunks
                with open(input_path, 'wb+') as destination:
                    for chunk in uploaded_file.chunks():
                        destination.write(chunk)
            else:
                # File-like object
                with open(input_path, 'wb+') as destination:
                    shutil.copyfileobj(uploaded_file, destination)

            try:
                # Extract text
                if file_ext == 'pdf':
                    blocks = self.pdf_processor.extract_text(input_path)
                else:
                    blocks = self.docx_processor.extract_text(input_path)

                processing_time = time.time() - start_time
                
                return {
                    'success': True,
                    'file_name': file_name,
                    'file_format': file_ext,
                    'blocks': blocks,
                    'total_blocks': len(blocks),
                    'processing_time': processing_time
                }

            except Exception as e:
                logger.error(f"Error during document extraction: {str(e)}")
                return {
                    'success': False,
                    'error': str(e),
                    'processing_time': time.time() - start_time
                }

    def translate_document_offline(self, uploaded_file, target_language: str = 'en', source_language: str = 'auto') -> Dict[str, Any]:

        """
        Translate a document (PDF, DOCX) without cloud or DB dependencies.
        Generates a new document file with translated text.
        
        Args:
            uploaded_file: Django uploaded file or local file object
            target_language: Target language code
            
            
        Returns:
            Dictionary with translated blocks and success status
        """
        start_time = time.time()
        
        if isinstance(uploaded_file, str):
            file_name = os.path.basename(uploaded_file)
        else:
            file_name = getattr(uploaded_file, 'name', 'document')
            
        file_ext = file_name.split('.')[-1].lower() if '.' in file_name else 'document'

        # Step 1: Extract text
        extraction_result = self.extract_document_text(uploaded_file)
        if not extraction_result['success']:
            return extraction_result
        print("extracted text")

        try:
            blocks = extraction_result['blocks']
            if source_language == 'auto' or not source_language:
                # Use a sample of the text for detection
                sample_text = "\n".join([b['text'] for b in blocks[:5]])
                detected_source_lang = self.translation_service._detect_language_with_ai(sample_text)
                print(f"Detected source language: {detected_source_lang}")
            else:
                detected_source_lang = source_language

            # Step 3: Translate blocks
            print("start translation")
            translated_blocks = self._translate_blocks(blocks, target_language, source_lang=detected_source_lang)
            print("end translation")

            # Step 3: Reconstruct document in a temporary location
            # Note: We'll use a predictable name in the same directory as input if possible, 
            # or in a temp directory.
            
            output_filename = f"translated_{target_language}_{file_name}"
            # Use same directory as input if it's a path, otherwise use current dir
            output_dir = os.getcwd()
            output_path = os.path.join(output_dir, output_filename)
            
            # We need the original file path to reconstruct
            # Since extract_document_text already handled copying it to a temp path, 
            # we should probably refactor to keep that path or re-copy here.
            
            with tempfile.TemporaryDirectory() as temp_dir:
                input_path = os.path.join(temp_dir, f"input_{file_name}")
                
                # Save uploaded file to temp path
                if isinstance(uploaded_file, str):
                    shutil.copy2(uploaded_file, input_path)
                elif hasattr(uploaded_file, 'chunks'):
                    uploaded_file.seek(0)
                    with open(input_path, 'wb+') as destination:
                        for chunk in uploaded_file.chunks():
                            destination.write(chunk)
                else:
                    uploaded_file.seek(0)
                    with open(input_path, 'wb+') as destination:
                        shutil.copyfileobj(uploaded_file, destination)

                # Generate the reconstructed document
                if file_ext == 'pdf':
                    self.pdf_processor.replace_text(input_path, translated_blocks, output_path)
                else:
                    self.docx_processor.replace_text(input_path, translated_blocks, output_path)

            processing_time = time.time() - start_time
            
            return {
                'success': True,
                'file_name': extraction_result['file_name'],
                'file_format': extraction_result['file_format'],
                'original_blocks': extraction_result['blocks'],
                'translated_blocks': translated_blocks,
                'total_blocks': len(translated_blocks),
                'translated_file_path': output_path,
                'processing_time': processing_time,
                'target_language': target_language
            }

        except Exception as e:
            logger.error(f"Error during offline document translation: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'processing_time': time.time() - start_time
            }

    def translate_document(self, user, uploaded_file, target_language: str = 'en', source_language: str = 'auto') -> Dict[str, Any]:
        """
        Modified entry point for document translation - now handles initial upload 
        and queues the background task.
        """
        from .models import TextTranslation, SpeechTranslation
        from .choices import FeatureType, TranslationStatus
        
        start_time = time.time()
        file_name = uploaded_file.name
        file_ext = file_name.split('.')[-1].lower()
        
        if file_ext not in ['pdf', 'docx', 'doc']:
            return {
                'success': False,
                'error': f"Unsupported file format: {file_ext}",
                'processing_time': time.time() - start_time
            }

        # Step 1: Save file locally for immediate response
        try:
            temp_upload_dir = os.path.join(settings.MEDIA_ROOT, 'temp_uploads')
            os.makedirs(temp_upload_dir, exist_ok=True)
            
            local_filename = f"{uuid.uuid4().hex}_{file_name}"
            local_file_path = os.path.join(temp_upload_dir, local_filename)
            
            with open(local_file_path, 'wb+') as destination:
                for chunk in uploaded_file.chunks():
                    destination.write(chunk)
            logger.info(f"Saved original file locally to {local_file_path}")
        except Exception as e:
            logger.error(f"Failed to save file locally: {str(e)}")
            return {
                'success': False,
                'error': f"Initial processing failed: {str(e)}",
                'processing_time': time.time() - start_time
            }

        # Step 2: Create a pending translation record (URL will be populated by worker)
        translation_record = TextTranslation.objects.create(
            user=user,
            feature_type=FeatureType.EBOOK_TRANSLATION,
            original_filename=file_name,
            file_format=file_ext,
            target_language=target_language,
            original_language='auto' if source_language == 'auto' else source_language,
            status=TranslationStatus.PENDING
        )

        # Step 3: Trigger background task with local path
        from .tasks import async_ebook_translation_task
        async_ebook_translation_task.delay(str(translation_record.id), local_file_path)

        return {
            'success': True,
            'message': "Translation is currently processing in the background.",
            'translation_id': str(translation_record.id),
            'status': TranslationStatus.PENDING,
            'processing_time': time.time() - start_time
        }

    def process_document_translation(self, translation_id: str, local_file_path: str = None) -> Dict[str, Any]:
        """
        Background processing logic for document translation.
        Called by Celery task.
        Now handles cloud upload of the original file as well.
        """
        from .models import TextTranslation, SpeechTranslation
        from .choices import TranslationStatus
        from .cloud_storage import cloud_storage
        import tempfile
        
        start_time = time.time()
        
        try:
            # 1. Get record and set status to PROCESSING
            try:
                translation_record = TextTranslation.objects.get(id=translation_id)
            except TextTranslation.DoesNotExist:
                logger.error(f"TextTranslation record {translation_id} not found")
                return {'success': False, 'error': "Record not found"}

            translation_record.status = TranslationStatus.PROCESSING
            translation_record.save()
            
            # Send initial WebSocket update
            from performance.celery_tasks import send_websocket_update
            if translation_record.user:
                send_websocket_update(translation_record.user.id, 'ebook', {
                    'type': 'task_started',
                    'translation_id': translation_id,
                    'message': 'Starting document processing...'
                })

            # 2. Upload original file to cloud storage
            if local_file_path and os.path.exists(local_file_path):
                logger.info(f"Uploading original file {local_file_path} to cloud storage...")
                try:
                    # Save locally first
                    from django.core.files import File
                    with open(local_file_path, 'rb') as f:
                        django_file = File(f)
                        django_file.name = translation_record.original_filename
                        translation_record.original_file.save(django_file.name, django_file, save=True)
                    
                    # Upload to cloud explicitly
                    if cloud_storage.is_available():
                        with open(local_file_path, 'rb') as f:
                            from django.core.files.base import ContentFile
                            # Use ContentFile and add content_type for the cloud_storage service
                            content_file = ContentFile(f.read(), name=translation_record.original_filename)
                            content_file.content_type = 'application/pdf' if file_ext == 'pdf' else 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
                            
                            remote_url = cloud_storage.upload_document_input_file(
                                file=content_file,
                                language=translation_record.original_language or 'en',
                                user_id=str(translation_record.user_id or 'anonymous')
                            )
                            if remote_url:
                                translation_record.original_file_url = remote_url
                                translation_record.save()
                except Exception as e:
                    logger.warning(f"Initial cloud upload for document failed: {e}")
            
            # 3. Setup processing environment
            file_ext = translation_record.file_format
            target_language = translation_record.target_language
            source_language = translation_record.original_language
            
            if not local_file_path or not os.path.exists(local_file_path):
                # Fallback to downloading if local file is missing but URL exists
                if not translation_record.original_file_url:
                    raise Exception("Original file not found locally or in cloud")
                
                import requests
                import tempfile
                logger.info(f"Downloading original file from {translation_record.original_file_url}")
                temp_dir = tempfile.mkdtemp()
                local_file_path = os.path.join(temp_dir, translation_record.original_filename)
                
                response = requests.get(translation_record.original_file_url, stream=True)
                if response.status_code != 200:
                    raise Exception(f"Failed to download original file: {response.status_code}")
                    
                with open(local_file_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)

            with tempfile.TemporaryDirectory() as temp_dir:
                output_path = os.path.join(temp_dir, f"output_{translation_record.original_filename}")
                
                # 4. Extract text
                if file_ext == 'pdf':
                    blocks = self.pdf_processor.extract_text(local_file_path)
                else:
                    blocks = self.docx_processor.extract_text(local_file_path)

                if not blocks:
                    raise Exception("No text found in document")

                # 5. Detect language if needed
                if source_language == 'auto' or not source_language:
                    sample_text = "\n".join([b['text'] for b in blocks[:5]])
                    detected_source_lang = self.translation_service._detect_language_with_ai(sample_text)
                    translation_record.original_language = detected_source_lang
                else:
                    detected_source_lang = source_language

                # 6. Translate blocks (Parallel Processing)
                translated_blocks = self._translate_blocks(blocks, target_language, source_lang=detected_source_lang)

                # 7. Reconstruct document
                if file_ext == 'pdf':
                    self.pdf_processor.replace_text(local_file_path, translated_blocks, output_path)
                else:
                    self.docx_processor.replace_text(local_file_path, translated_blocks, output_path)

                # 8. Save and Upload translated file
                # Save locally first
                from django.core.files import File
                with open(output_path, 'rb') as f:
                    django_output_file = File(f)
                    django_output_file.name = f"translated_{translation_record.original_filename}"
                    translation_record.translated_file.save(django_output_file.name, django_output_file, save=True)
                
                translated_url = translation_record.translated_file.url
                
                # Upload to cloud explicitly
                if cloud_storage.is_available():
                    try:
                        remote_translated_url = cloud_storage.upload_document_output_file(
                            file_path=output_path,
                            language=target_language,
                            user_id=str(translation_record.user_id or 'anonymous'),
                            file_format=file_ext
                        )
                        if remote_translated_url:
                            translated_url = remote_translated_url
                            translation_record.translated_file_url = remote_translated_url
                            # Clear local file if cloud upload was successful
                            local_output_path = translation_record.translated_file.path
                            if os.path.exists(local_output_path):
                                os.remove(local_output_path)
                            translation_record.translated_file.name = None
                            translation_record.save()
                    except Exception as e:
                        logger.warning(f"Cloud upload for translated document failed: {e}")

                # 9. Update record as COMPLETED
                processing_time = time.time() - start_time
                translation_record.translated_file_url = translated_url
                translation_record.total_processing_time = processing_time
                translation_record.status = TranslationStatus.COMPLETED
                translation_record.save()

                # 10. Final WebSocket update
                if translation_record.user:
                    send_websocket_update(translation_record.user.id, 'ebook', {
                        'type': 'task_complete',
                        'translation_id': translation_id,
                        'translated_file_url': translated_url,
                        'message': 'Document translation completed successfully!'
                    })

                return {
                    'success': True,
                    'translation_id': translation_id,
                    'translated_url': translated_url,
                    'processing_time': processing_time
                }

        except Exception as e:
            logger.error(f"Error during background document translation: {str(e)}")
            if 'translation_record' in locals():
                translation_record.status = TranslationStatus.FAILED
                translation_record.error_message = str(e)
                translation_record.save()
                
                if translation_record.user:
                    send_websocket_update(translation_record.user.id, 'ebook', {
                        'type': 'task_error',
                        'translation_id': translation_id,
                        'error': str(e)
                    })
                    
            return {'success': False, 'error': str(e)}
        finally:
            # Cleanup local temp file if it was provided
            if local_file_path and os.path.exists(local_file_path):
                try:
                    # Only remove if it's in our temp_uploads dir
                    if 'temp_uploads' in local_file_path:
                        os.remove(local_file_path)
                        logger.info(f"Cleaned up local file {local_file_path}")
                except Exception as e:
                    logger.warning(f"Failed to clean up local file {local_file_path}: {e}")


    def _translate_blocks(self, blocks: List[Dict[str, Any]], target_lang: str, source_lang: str = 'auto') -> List[Dict[str, Any]]:
        """
        Optimized parallel translation. Groups blocks by page and processes several pages concurrently.
        """
        # Group blocks by page
        pages = {}
        for block in blocks:
            page_num = block.get('page', 0)
            if page_num not in pages:
                pages[page_num] = []
            pages[page_num].append(block)

        source_name = self.translation_service._get_language_name(source_lang)
        target_name = self.translation_service._get_language_name(target_lang)
        
        def translate_single_page(page_num, page_blocks):
            """Helper function to translate a single page's blocks"""
            texts_to_translate = [b['text'] for b in page_blocks]
            
            prompt = f"""You are a professional translator. Translate the following list of text blocks from {source_name} to {target_name}. 
These blocks are from the SAME PAGE of a document, so maintain consistent terminology and a natural narrative flow across them.

IMPORTANT: Return the result EXCLUSIVELY as a JSON array of strings, where each string corresponds to the translation of the block at the same index. Do not include any other text or formatting.

Example Format:
["Translated Block 1", "Translated Block 2", ...]

Blocks to translate:
{json.dumps(texts_to_translate, ensure_ascii=False)}
"""
            try:
                model_name = self.translation_service.get_model(use_pro=True)
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt
                )
                
                result_text = response.text.strip()
                if "```json" in result_text:
                    result_text = result_text.split("```json")[1].split("```")[0].strip()
                elif "```" in result_text:
                    result_text = result_text.split("```")[1].split("```")[0].strip()
                
                translated_texts = json.loads(result_text)
                
                if isinstance(translated_texts, list) and len(translated_texts) == len(page_blocks):
                    for idx, block in enumerate(page_blocks):
                        block['translated_text'] = translated_texts[idx]
                    return page_num, True, page_blocks
                else:
                    raise ValueError(f"Mismatch in translation length or format: {len(translated_texts) if isinstance(translated_texts, list) else 'not a list'}")
            
            except Exception as e:
                # Fallback to block-by-block if JSON batch fails
                print(f"  [PAGE_FAIL] Page {page_num} batch failed ({e}). Falling back to block-by-block...")
                for block in page_blocks:
                    res = self.translation_service.translate_text(block['text'], source_lang, target_lang)
                    block['translated_text'] = res['translated_text'] if res['success'] else block['text']
                return page_num, False, page_blocks

        # Execute page translations in parallel
        # We limit max_workers to 5 to avoid aggressive rate-limiting on many-page documents
        max_workers = min(5, len(pages))
        translated_results_map = {}
        
        print(f"Starting parallel translation of {len(pages)} pages using {max_workers} threads...")
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_page = {executor.submit(translate_single_page, p_num, p_blocks): p_num for p_num, p_blocks in pages.items()}
            
            for future in as_completed(future_to_page):
                p_num, success, result_blocks = future.result()
                translated_results_map[p_num] = result_blocks
                status = "[OK]" if success else "[FALLBACK]"
                print(f"  {status} Finished Page {p_num}")

        # Flatten the results back into a single list sorted by page number
        final_list = []
        for p_num in sorted(translated_results_map.keys()):
            final_list.extend(translated_results_map[p_num])
            
        return final_list


# Async versions of the services
class AsyncGeminiService:
    """Async base service for Google Gemini AI operations"""
    
    def __init__(self):
        self.model = "gemini-2.5-flash"
        self.pro_model = "gemini-2.5-pro"
    
    def get_model(self, use_pro: bool = False) -> str:
        """Get the appropriate model based on settings"""
        return self.pro_model if use_pro else self.model


class AsyncSpeechService(AsyncGeminiService):
    """Async service for handling speech-to-text operations"""
    
    async def transcribe_audio(self, audio_file: BinaryIO, language: str = 'auto') -> Dict[str, Any]:
        """
        Convert speech to text using Gemini AI (async)
        
        Args:
            audio_file: Audio file binary data
            language: Source language code (auto for auto-detection)
            
        Returns:
            Dictionary with transcription results
        """
        try:
            start_time = time.time()
            
            # Read audio data asynchronously
            audio_data = await asyncio.get_event_loop().run_in_executor(
                None, lambda: audio_file.read()
            )
            if isinstance(audio_file, str):
                def read_file():
                    with open(audio_file, 'rb') as f:
                        return f.read()
                audio_data = await asyncio.get_event_loop().run_in_executor(None, read_file)
            
            # Create transcription prompt
            if language == 'auto':
                prompt = """Transcribe the speech in this audio file to text. Detect the language automatically and return the transcribed text exactly as spoken, preserving all words, names, and expressions. If you cannot detect any speech, return an empty string."""
            else:
                lang_name = await self._get_language_name_async(language)
                prompt = f"""Transcribe the speech in this audio file to text. The audio is in {lang_name}. Return the transcribed text exactly as spoken, preserving all words, names, and expressions. If you cannot detect any speech, return an empty string."""
            
            # Process audio with Gemini asynchronously
            def gemini_call():
                return client.models.generate_content(
                    model=self.model,
                    contents=[
                        types.Part.from_bytes(
                            data=audio_data,
                            mime_type="audio/wav",
                        ),
                        prompt
                    ]
                )
            
            response = await asyncio.get_event_loop().run_in_executor(None, gemini_call)
            
            transcribed_text = response.text.strip() if response.text else ""
            processing_time = time.time() - start_time
            
            # Auto-detect language if not specified
            detected_language = language
            if language == 'auto' and transcribed_text:
                try:
                    detected_language = await asyncio.get_event_loop().run_in_executor(
                        None, lambda: detect(transcribed_text)
                    )
                except:
                    detected_language = 'en'  # fallback
            
            # Calculate confidence based on transcription quality
            confidence = self._calculate_speech_confidence(transcribed_text, processing_time)
            
            logger.info(f"Async speech-to-text completed in {processing_time:.2f}s. Language: {detected_language}")
            
            return {
                'text': transcribed_text,
                'language': detected_language,
                'confidence': confidence,
                'processing_time': processing_time,
                'success': bool(transcribed_text)
            }
            
        except Exception as e:
            logger.error(f"Error in async speech-to-text: {str(e)}")
            return {
                'text': '',
                'language': language if language != 'auto' else 'unknown',
                'confidence': 0.0,
                'processing_time': time.time() - start_time if 'start_time' in locals() else 0.0,
                'success': False,
                'error': str(e)
            }
    
    def _calculate_speech_confidence(self, transcribed_text: str, processing_time: float) -> float:
        """Calculate speech-to-text confidence based on transcription quality"""
        if not transcribed_text:
            return 0.0
        
        base_confidence = 80.0
        
        # Text length and completeness
        text_length = len(transcribed_text.strip())
        words = transcribed_text.split()
        word_count = len(words)
        
        if text_length > 150:
            base_confidence += 12.0
        elif text_length > 80:
            base_confidence += 8.0
        elif text_length > 30:
            base_confidence += 4.0
        elif text_length < 10:
            base_confidence -= 25.0
        
        # Word structure and language patterns
        if word_count > 15:
            base_confidence += 8.0
        elif word_count > 8:
            base_confidence += 4.0
        elif word_count < 3:
            base_confidence -= 20.0
        
        # Processing time indicator (faster usually means clearer audio)
        if processing_time < 2.0:
            base_confidence += 10.0
        elif processing_time < 4.0:
            base_confidence += 5.0
        elif processing_time > 8.0:
            base_confidence -= 8.0
        
        # Check for sentence structure and punctuation
        if '.' in transcribed_text or '?' in transcribed_text or '!' in transcribed_text:
            base_confidence += 6.0
        
        # Check for proper capitalization (indicates clear speech)
        if any(word[0].isupper() for word in words if word):
            base_confidence += 5.0
        
        # Check for repetitive patterns (indicates poor audio quality)
        if any(transcribed_text.count(word) > 3 for word in words if len(word) > 3):
            base_confidence -= 15.0
        
        # Character diversity
        unique_chars = len(set(transcribed_text.lower()))
        if unique_chars > 12:
            base_confidence += 5.0
        elif unique_chars < 6:
            base_confidence -= 10.0
        
        return min(95.0, max(20.0, base_confidence))
    
    async def _get_language_name_async(self, code: str) -> str:
        """Get full language name from code (async)"""
        try:
            from .models import LanguageSupport
            language = await sync_to_async(LanguageSupport.objects.get)(code=code)
            return language.name
        except Exception:
            return code.upper()


class AsyncTranslationService(AsyncGeminiService):
    """Async service for handling text translation operations"""
    
    async def translate_text(self, text: str, source_lang: str, target_lang: str = 'en', 
                           use_pro: bool = False) -> Dict[str, Any]:
        """
        Translate text using Gemini AI (async)
        
        Args:
            text: Text to translate
            source_lang: Source language code
            target_lang: Target language code
            use_pro: Whether to use Pro model
            
        Returns:
            Dictionary with translation results
        """
        try:
            start_time = time.time()
            
            if not text or len(text.strip()) == 0:
                return {
                    'translated_text': '',
                    'source_language': source_lang,
                    'target_language': target_lang,
                    'success': False,
                    'error': 'No text to translate'
                }
            
            # Skip translation if same language
            if source_lang == target_lang:
                return {
                    'translated_text': text,
                    'source_language': source_lang,
                    'target_language': target_lang,
                    'success': True,
                    'processing_time': 0.0,
                    'note': 'No translation needed - same language'
                }
            
            # Get language names asynchronously
            source_name, target_name = await asyncio.gather(
                self._get_language_name_async(source_lang),
                self._get_language_name_async(target_lang)
            )
            
            # Create translation prompt
            prompt = f"""Translate the following text from {source_name} to {target_name}. Provide an accurate, natural translation that preserves the meaning and context. For names and proper nouns, translate their meanings when appropriate (especially for African names which often have specific meanings). Return only the translated text:

{text}"""
            
            # Use appropriate model
            model = self.get_model(use_pro)
            
            # Process translation with Gemini asynchronously
            def gemini_call():
                return client.models.generate_content(
                    model=model,
                    contents=prompt
                )
            
            response = await asyncio.get_event_loop().run_in_executor(None, gemini_call)
            
            translated_text = response.text.strip() if response.text else ""
            processing_time = time.time() - start_time
            
            if not translated_text:
                raise ValueError("Empty translation response")
            
            logger.info(f"Async translation completed in {processing_time:.2f}s: {source_lang} -> {target_lang}")
            
            return {
                'translated_text': translated_text,
                'source_language': source_lang,
                'target_language': target_lang,
                'processing_time': processing_time,
                'success': True
            }
            
        except Exception as e:
            logger.error(f"Error in async translation: {str(e)}")
            return {
                'translated_text': '',
                'source_language': source_lang,
                'target_language': target_lang,
                'processing_time': time.time() - start_time if 'start_time' in locals() else 0.0,
                'success': False,
                'error': str(e)
            }
    
    async def _get_language_name_async(self, code: str) -> str:
        """Get full language name from code (async)"""
        try:
            from .models import LanguageSupport
            language = await sync_to_async(LanguageSupport.objects.get)(code=code)
            return language.name
        except Exception:
            return code.upper()


class AsyncTextToSpeechService(AsyncGeminiService):
    """Async service for handling text-to-speech operations"""
    
    async def synthesize_speech(self, text: str, language: str, voice: str = 'Zephyr') -> Dict[str, Any]:
        """
        Convert text to speech using Gemini AI (async)
        
        Args:
            text: Text to convert to speech
            language: Target language code
            voice: Voice model to use
            
        Returns:
            Dictionary with synthesis results
        """
        try:
            start_time = time.time()
            
            if not text or len(text.strip()) == 0:
                return {
                    'success': False,
                    'error': 'No text to synthesize',
                    'processing_time': 0.0
                }
            
            # Get language name
            lang_name = await self._get_language_name_async(language)
            
            # Use Gemini TTS model
            model = "gemini-2.5-flash-preview-tts"
            
            # Map voice names
            voice_mapping = {
                'Zephyr': 'Puck', 
                'Echo': 'Aoede',
                'Sky': 'Kore',
                'Onyx': 'Fenrir'
            }
            gemini_voice = voice_mapping.get(voice, 'Aoede')
            
            # Helper to run sync gemini call in thread
            def gemini_tts_call():
                return client.models.generate_content(
                    model=model,
                    contents=text,
                    config=types.GenerateContentConfig(
                        response_modalities=["AUDIO"],
                        speech_config=types.SpeechConfig(
                            voice_config=types.VoiceConfig(
                                prebuilt_voice_config=types.PrebuiltVoiceConfig(
                                    voice_name=gemini_voice
                                )
                            )
                        )
                    )
                )

            # Execute async
            response = await asyncio.get_event_loop().run_in_executor(None, gemini_tts_call)
            
            audio_data = None
            
            # Extract audio data (CPU bound, run in executor too if large, but fast enough here)
            if hasattr(response, 'candidates'):
                for cand in response.candidates:
                    if hasattr(cand, 'content') and hasattr(cand.content, 'parts'):
                        for part in cand.content.parts:
                            if hasattr(part, 'inline_data') and part.inline_data:
                                pcm_data = part.inline_data.data
                                # Need access to the sync service for helper or duplicate it.
                                # Since this class doesn't inherit from sync service, I'll duplicate the helper 
                                # or better, use the sync service implementation?
                                # Creating a temporary sync service to use its helper
                                temp_sync_service = TextToSpeechService()
                                audio_data = temp_sync_service._pcm_to_wav(pcm_data)
                                logger.info(f"Generated real async TTS audio: {len(audio_data)} bytes")
                                break
            
            if not audio_data:
                 # Fallback to silent
                 temp_sync_service = TextToSpeechService()
                 audio_data = temp_sync_service._generate_silent_wav(duration=1.0)
            
            processing_time = time.time() - start_time
            
            return {
                'success': True,
                'audio_available': True,
                'processing_time': processing_time,
                'note': f'TTS processed with Gemini 2.5 Flash TTS',
                'language': language,
                'voice': voice,
                'audio_data': audio_data
            }
            
        except Exception as e:
            logger.error(f"Error in async text-to-speech: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'processing_time': time.time() - start_time if 'start_time' in locals() else 0.0
            }
    
    async def _get_language_name_async(self, code: str) -> str:
        """Get full language name from code (async)"""
        try:
            from .models import LanguageSupport
            language = await sync_to_async(LanguageSupport.objects.get)(code=code)
            return language.name
        except Exception:
            return code.upper()


class AsyncVoiceTranslationService:
    """Async main orchestrator service for complete voice translation pipeline"""
    
    def __init__(self):
        self.speech_service = AsyncSpeechService()
        self.translation_service = AsyncTranslationService()
        self.tts_service = AsyncTextToSpeechService()
        self.audio_service = AudioService()  # Keep sync for file validation
    
    async def process_voice_translation(self, user, audio_file, session_id: str = None, 
                                      target_language: str = 'en') -> Dict[str, Any]:
        """
        Complete voice translation pipeline (async)
        
        Args:
            user: User object
            audio_file: Audio file to process
            session_id: User session ID
            target_language: Target language for translation
            
        Returns:
            Dictionary with complete translation results
        """
        start_time = time.time()
        
        try:
            # Get user settings asynchronously
            settings = None
            if user:
                try:
                    from .models import UserSettings
                    settings = await sync_to_async(UserSettings.objects.get)(
                        user=user
                    )
                except Exception:
                    pass
            
            # Validate audio file (sync operation)
            validation = await asyncio.get_event_loop().run_in_executor(
                None, self.audio_service.validate_audio_file, audio_file
            )
            if not validation['valid']:
                return {
                    'success': False,
                    'error': validation['error'],
                    'processing_time': time.time() - start_time
                }
            
            # Step 1: Speech to Text
            logger.info("Starting async speech-to-text conversion...")
            source_lang = settings.source_language if settings else 'auto'
            
            stt_result = await self.speech_service.transcribe_audio(audio_file, source_lang)
            if not stt_result['success']:
                return {
                    'success': False,
                    'error': f"Speech-to-text failed: {stt_result.get('error', 'Unknown error')}",
                    'processing_time': time.time() - start_time
                }
            
            original_text = stt_result['text']
            detected_language = stt_result['language']
            
            # Step 2: Translation
            logger.info("Starting async text translation...")
            use_pro = settings.model == 'gemini-2.5-pro' if settings else False
            
            translation_result = await self.translation_service.translate_text(
                original_text, detected_language, target_language, use_pro
            )
            
            if not translation_result['success']:
                return {
                    'success': False,
                    'error': f"Translation failed: {translation_result.get('error', 'Unknown error')}",
                    'processing_time': time.time() - start_time,
                    'original_text': original_text,
                    'detected_language': detected_language
                }
            
            translated_text = translation_result['translated_text']
            
            # Step 3: Text to Speech (optional) - run concurrently with database save
            tts_task = None
            if settings and settings.autoplay:
                logger.info("Starting async text-to-speech synthesis...")
                voice = settings.voice if settings else 'Zephyr'
                tts_task = asyncio.create_task(
                    self.tts_service.synthesize_speech(translated_text, target_language, voice)
                )
            
            # Upload input audio to cloud storage asynchronously
            async def upload_input_audio():
                if cloud_storage.is_available():
                    try:
                        # Reset file position for upload
                        audio_file.seek(0)
                        return await asyncio.get_event_loop().run_in_executor(
                            None, 
                            cloud_storage.upload_voice_input_file,
                            audio_file, detected_language, str(user.id) if user else 'anonymous'
                        )
                    except Exception as e:
                        logger.warning(f"Failed to upload input audio to cloud storage: {e}")
                return None
            
            # Save translation record asynchronously
            async def save_translation(original_audio_url=None, translated_audio_url=None):
                total_processing_time = time.time() - start_time
                original_filename = getattr(audio_file, 'name', 'audio_input')
                audio_format = original_filename.split('.')[-1].lower() if '.' in original_filename else 'wav'
                
                from django.db import transaction
                async with transaction.atomic():
                    from .models import SpeechTranslation
                    translation_record = await sync_to_async(SpeechTranslation.objects.create)(
                        user=user,
                        original_text=original_text,
                        translated_text=translated_text,
                        original_language=detected_language,
                        target_language=target_language,
                        original_audio_url=original_audio_url,
                        translated_audio_url=translated_audio_url,
                        original_filename=original_filename,
                        audio_format=audio_format,
                        confidence_score=stt_result['confidence'],
                        total_processing_time=total_processing_time,
                        session_id=session_id
                    )
                    # Save processing times
                    from .models import TextTranslation, SpeechTranslationProcessingTime
                    await sync_to_async(TranslationProcessingTime.objects.create)(
                        translation=translation_record,
                        speech_to_text=stt_result.get('processing_time', 0.0),
                        text_to_text=translation_result.get('processing_time', 0.0),
                        text_to_speech=tts_result.get('processing_time', 0.0) if tts_result else 0.0,
                        total=total_processing_time
                    )
                return translation_record
            
            # Upload input audio and run TTS concurrently
            upload_task = upload_input_audio()
            
            if tts_task:
                original_audio_url, tts_result = await asyncio.gather(upload_task, tts_task)
                
                # Upload output audio if TTS was successful
                translated_audio_url = None
                if tts_result and tts_result.get('success') and tts_result.get('audio_data'):
                    if cloud_storage.is_available():
                        try:
                            translated_audio_url = await asyncio.get_event_loop().run_in_executor(
                                None,
                                cloud_storage.upload_voice_output_file,
                                tts_result['audio_data'], target_language, 
                                str(user.id) if user else 'anonymous', 'wav'
                            )
                            logger.info(f"Uploaded output audio to cloud storage: {translated_audio_url}")
                        except Exception as e:
                            logger.warning(f"Failed to upload output audio to cloud storage: {e}")
                
                translation_record = await save_translation(original_audio_url, translated_audio_url)
            else:
                original_audio_url = await upload_task
                translation_record = await save_translation(original_audio_url, None)
                tts_result = None
            
            # Prepare response
            response = {
                'success': True,
                'translation_id': str(translation_record.id),
                'original_text': original_text,
                'translated_text': translated_text,
                'original_language': detected_language,
                'target_language': target_language,
                'original_audio_url': original_audio_url,
                'translated_audio_url': translated_audio_url,
                'confidence_score': stt_result['confidence'],
                'processing_time': time.time() - start_time,
                'steps': {
                    'speech_to_text': stt_result['processing_time'],
                    'translation': translation_result['processing_time'],
                    'text_to_speech': tts_result['processing_time'] if tts_result else 0
                }
            }
            
            if tts_result:
                response['audio_available'] = tts_result['success']
                response['tts_note'] = tts_result.get('note', '')
            
            logger.info(f"Async voice translation completed in {response['processing_time']:.2f}s")
            return response
            
        except Exception as e:
            logger.error(f"Error in async voice translation pipeline: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'processing_time': time.time() - start_time
            }

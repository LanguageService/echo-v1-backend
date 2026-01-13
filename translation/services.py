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
from typing import Dict, Any, Optional, BinaryIO
from google import genai
from google.genai import types
from langdetect import detect
from asgiref.sync import sync_to_async
from django.db import transaction
from django.conf import settings
from .models import Translation, UserSettings, AudioFile, LanguageSupport
from .cloud_storage import cloud_storage
from decouple import config

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
    
    def _detect_language_with_ai(self, text: str) -> str:
        """
        Use Gemini AI to detect language of text, especially good for African languages
        
        Args:
            text: Text to analyze
            
        Returns:
            Language code (e.g., 'rw', 'sw', 'en')
        """
        try:
            prompt = f"""Identify the language of this text and return ONLY the ISO 639-1 language code (2 letters).

Pay special attention to African languages:
- Kinyarwanda (rw) - common words: ubwoba, uyu, munsi, hamwe, ndabakunda, mwiza, reka
- Swahili (sw) - common words: hali, haya, siku, pamoja, ninawapenda, nzuri, hebu
- Hausa (ha) - common words: wannan, rana, tare, ina, kyakkyawa
- Yoruba (yo) - common words: eyi, ojo, pelu, mo, dara
- Igbo (ig) - common words: nke, ubochi, na, a, mma

Text: "{text}"

Language code:"""

            response = client.models.generate_content(
                model=self.model,
                contents=prompt
            )
            
            detected_code = response.text.strip().lower() if response.text else 'en'
            
            # Validate that it's a proper language code
            if len(detected_code) == 2 and detected_code.isalpha():
                logger.info(f"AI language detection: '{text[:50]}...' -> {detected_code}")
                return detected_code
            else:
                # If AI returns something unexpected, fallback to langdetect
                return detect(text)
                
        except Exception as e:
            logger.error(f"AI language detection failed: {str(e)}")
            # Fallback to langdetect
            return detect(text)
    
    def _get_language_name(self, code: str) -> str:
        """Get full language name from code"""
        try:
            language = LanguageSupport.objects.get(code=code)
            return language.name
        except LanguageSupport.DoesNotExist:
            return code.upper()


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
    
    def _get_language_name(self, code: str) -> str:
        """Get full language name from code"""
        try:
            language = LanguageSupport.objects.get(code=code)
            return language.name
        except LanguageSupport.DoesNotExist:
            return code.upper()


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
            
            # Get language name
            lang_name = self._get_language_name(language)
            
            # Create TTS prompt
            prompt = f"""Generate natural-sounding speech for the following {lang_name} text using a {voice} voice style. The speech should be clear, well-paced, and expressive:

{text}"""
            
            # Generate silent audio as fallback/simulation
            audio_data = self._generate_silent_wav()
            
            logger.info(f"Text-to-speech request for {language} text (length: {len(text)})")
            
            processing_time = time.time() - start_time
            
            return {
                'success': True,
                'language': language,
                'voice': voice,
                'text_length': len(text),
                'processing_time': processing_time,
                'audio_data': audio_data,
                'note': 'TTS processing simulated with silent audio placeholder'
            }
            
        except Exception as e:
            logger.error(f"Error in text-to-speech: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'audio_data': None,
                'processing_time': time.time() - start_time if 'start_time' in locals() else 0.0
            }
    
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
            language = LanguageSupport.objects.get(code=code)
            return language.name
        except LanguageSupport.DoesNotExist:
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
            # Check file size
            max_size = getattr(settings, 'MAX_AUDIO_FILE_SIZE', 10 * 1024 * 1024)
            if audio_file.size > max_size:
                return {
                    'valid': False,
                    'error': f'File too large. Maximum size is {max_size // (1024*1024)}MB'
                }
            
            # Check file format
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
                                 target_language: str = 'en') -> Dict[str, Any]:
        """
        Complete voice translation pipeline
        
        Args:
            audio_file: Audio file to process
            session_id: User session ID
            target_language: Target language for translation
            
        Returns:
            Dictionary with complete translation results
        """
        start_time = time.time()
        
        try:
            # Get user settings
            settings = None
            if user:
                try:
                    settings = UserSettings.objects.get(user=user)
                except UserSettings.DoesNotExist:
                    pass
            
            # Validate audio file
            validation = self.audio_service.validate_audio_file(audio_file)
            if not validation['valid']:
                return {
                    'success': False,
                    'error': validation['error'],
                    'processing_time': time.time() - start_time
                }
            
            # Step 1: Speech to Text
            logger.info("Starting speech-to-text conversion...")
            source_lang = settings.source_language if settings else 'auto'

            # TODO: rename the api source and target field to language1 and language2
            # after the ASR detect the source, then we set the source and target to be saved in the db
            
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
            translation_record = Translation.objects.create(
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
            from .models import TranslationProcessingTime
            
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
    
    async def _get_language_name_async(self, code: str) -> str:
        """Get full language name from code (async)"""
        try:
            language = await sync_to_async(LanguageSupport.objects.get)(code=code)
            return language.name
        except LanguageSupport.DoesNotExist:
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
            language = await sync_to_async(LanguageSupport.objects.get)(code=code)
            return language.name
        except LanguageSupport.DoesNotExist:
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
            
            # Note: Gemini doesn't directly support TTS yet, so we simulate the process
            # In a real implementation, you would integrate with a TTS service
            logger.info(f"Simulating TTS synthesis for {lang_name} text: {text[:50]}...")
            
            # Simulate processing time
            await asyncio.sleep(0.1)
            
            processing_time = time.time() - start_time
            
            return {
                'success': True,
                'audio_available': False,
                'processing_time': processing_time,
                'note': f'TTS synthesis simulated for {lang_name} using {voice} voice model',
                'language': language,
                'voice': voice
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
            language = await sync_to_async(LanguageSupport.objects.get)(code=code)
            return language.name
        except LanguageSupport.DoesNotExist:
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
                    settings = await sync_to_async(UserSettings.objects.get)(
                        user=user
                    )
                except UserSettings.DoesNotExist:
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
                
                async with transaction.atomic():
                    translation_record = await sync_to_async(Translation.objects.create)(
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
                    from .models import TranslationProcessingTime
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

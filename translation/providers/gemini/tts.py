import io
import logging
import time
import wave
import base64
from typing import Dict, Any, Optional
from google import genai
from google.genai import types
from django.conf import settings
from translation.providers.base import BaseTTSProvider

logger = logging.getLogger(__name__)

# Initialize GenAI client
client = genai.Client(api_key=settings.GEMINI_API_KEY)

class GeminiTTSProvider(BaseTTSProvider):
    """Gemini-based Text-to-Speech (TTS) provider"""
    
    def __init__(self, model: str = "gemini-2.5-flash-preview-tts"):
        self.model = model

    @staticmethod
    def _pcm_to_wav(pcm_data: bytes, sample_rate: int = 24000,
                    num_channels: int = 1, sample_width: int = 2) -> bytes:
        """Wrap raw PCM bytes in a proper WAV (RIFF) container.
        
        Gemini TTS returns 24 kHz, 16-bit (2-byte), mono PCM.
        Without this header, the file cannot be played by any standard player.
        """
        buf = io.BytesIO()
        with wave.open(buf, 'wb') as wf:
            wf.setnchannels(num_channels)
            wf.setsampwidth(sample_width)
            wf.setframerate(sample_rate)
            wf.writeframes(pcm_data)
        return buf.getvalue()
    
    def synthesize(self, text: str, language: str, voice: Optional[str] = 'Zephyr') -> Dict[str, Any]:
        """Synthesize text to speech using Gemini AI"""
        start_time = time.time()
        try:
            if not text or len(text.strip()) == 0:
                return { 'success': False, 'audio_data': None, 'error': 'No text to synthesize' }
            
            # Map common voice names to Gemini names
            voice_mapping = {
                'Zephyr': 'Zephyr',
                'Nova': 'Puck',
                'Orbit': 'Charon',
                'Echo': 'Kore',
                'Breeze': 'Fenrir',
                'Aria': 'Aoede'
            }
            gemini_voice = voice_mapping.get(voice, 'Aoede')
            
            # Model ID with prefix
            if not self.model.startswith("models/"):
                model_id = f"models/{self.model}"
            else:
                model_id = self.model
                
            # Use a more explicit prompt for -tts models to satisfy guardrails
            # This prevents the "Model tried to generate text" error
            prompt = f"Please synthesize the following text into audio, no text response: {text}"
            
            response = client.models.generate_content(
                model=model_id,
                contents=prompt,
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
            if hasattr(response, 'candidates') and response.candidates:
                cand = response.candidates[0]
                if cand.finish_reason and cand.finish_reason != 'STOP':
                    logger.warning(f"Gemini TTS Finish Reason: {cand.finish_reason}")
                
                if hasattr(cand, 'content') and hasattr(cand.content, 'parts'):
                    for part in cand.content.parts:
                        if hasattr(part, 'inline_data') and part.inline_data:
                            # Gemini returns raw 24kHz 16-bit mono PCM — wrap it in a WAV header
                            audio_data = self._pcm_to_wav(part.inline_data.data)
                            break
                        elif hasattr(part, 'text') and part.text:
                            logger.warning(f"Model returned text instead of audio: {part.text[:100]}")
            else:
                logger.error("No candidates returned from Gemini TTS model.")
            
            processing_time = time.time() - start_time
            
            # Extract usage
            usage = None
            if hasattr(response, 'usage_metadata'):
                usage = {
                    'prompt_tokens': response.usage_metadata.prompt_token_count,
                    'candidates_tokens': response.usage_metadata.candidates_token_count,
                    'total_tokens': response.usage_metadata.total_token_count
                }
            
            return {
                'success': True if audio_data else False,
                'audio_data': audio_data,
                'processing_time': processing_time,
                'usage': usage,
                'char_count': len(text),
                'error': None if audio_data else 'No audio data returned from model',
                'model': model_id,
                'provider': 'Google'
            }
            
        except Exception as e:
            logger.error(f"Error in Gemini TTS provider: {str(e)}")
            return {
                'success': False,
                'audio_data': None,
                'error': str(e),
                'processing_time': time.time() - start_time
            }

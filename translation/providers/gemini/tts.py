import logging
import time
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
    
    def __init__(self, model: str = "gemini-2.0-flash"):
        self.model = model
    
    def synthesize(self, text: str, language: str, voice: Optional[str] = 'Zephyr') -> Dict[str, Any]:
        """Synthesize text to speech using Gemini AI"""
        start_time = time.time()
        try:
            if not text or len(text.strip()) == 0:
                return { 'success': False, 'audio_data': None, 'error': 'No text to synthesize' }
            
            # Map common voice names to Gemini names
            voice_mapping = {
                'Zephyr': 'Puck', 
                'Echo': 'Aoede',
                'Sky': 'Kore',
                'Onyx': 'Fenrir'
            }
            gemini_voice = voice_mapping.get(voice, 'Aoede')
            
            # Process synthesis
            response = client.models.generate_content(
                model=self.model,
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
            if hasattr(response, 'candidates'):
                for cand in response.candidates:
                    if hasattr(cand, 'content') and hasattr(cand.content, 'parts'):
                        for part in cand.content.parts:
                            if hasattr(part, 'inline_data') and part.inline_data:
                                # Gemini returns PCM (usually), but we might need to convert it or return it raw
                                audio_data = part.inline_data.data # Bytes
                                break
            
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
                'model': self.model,
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

import logging
import time
from typing import Dict, Any, BinaryIO
from google import genai
from google.genai import types
from django.conf import settings
from translation.providers.base import BaseASRProvider

logger = logging.getLogger(__name__)

# Initialize GenAI client
client = genai.Client(api_key=settings.GEMINI_API_KEY)

class GeminiASRProvider(BaseASRProvider):
    """Gemini-based Speech-to-Text (ASR) provider"""
    
    def __init__(self, model: str = "gemini-2.0-flash"):
        self.model = model
    
    def transcribe(self, audio_file: Any, language: str = 'auto') -> Dict[str, Any]:
        """Transcribe audio to text using Gemini AI"""
        start_time = time.time()
        try:
            audio_data = None
            
            # Handle BinaryIO (file uploads)
            if hasattr(audio_file, 'read'):
                audio_file.seek(0)
                audio_data = audio_file.read()
            # Handle string (public URLs)
            elif isinstance(audio_file, str) and (audio_file.startswith('http://') or audio_file.startswith('https://')):
                import requests
                response = requests.get(audio_file, timeout=60)
                response.raise_for_status()
                audio_data = response.content
            # Handle raw bytes
            elif isinstance(audio_file, bytes):
                audio_data = audio_file
            
            if not audio_data:
                raise Exception("No audio data provided or could not download from URL")
            
            # Create transcription prompt
            if language == 'auto':
                prompt = """Transcribe the speech in this audio file to text. Detect the language automatically and return the transcribed text exactly as spoken."""
            else:
                prompt = f"""Transcribe the speech in this audio file to text. The audio is in {language}. Return the transcribed text exactly as spoken."""
            
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
            
            # Extract token usage
            usage = None
            if hasattr(response, 'usage_metadata'):
                usage = {
                    'prompt_tokens': response.usage_metadata.prompt_token_count,
                    'candidates_tokens': response.usage_metadata.candidates_token_count,
                    'total_tokens': response.usage_metadata.total_token_count
                }
            
            # Basic confidence score (Gemini doesn't provide it directly in standard response)
            confidence = 0.95 if transcribed_text else 0.0
            
            return {
                'success': True,
                'text': transcribed_text,
                'language': language, 
                'confidence': confidence,
                'processing_time': processing_time,
                'usage': usage,
                'model': self.model,
                'provider': 'Google'
            }
            
        except Exception as e:
            logger.error(f"Error in Gemini ASR provider: {str(e)}")
            return {
                'success': False,
                'text': '',
                'language': language,
                'confidence': 0.0,
                'error': str(e),
                'processing_time': time.time() - start_time
            }

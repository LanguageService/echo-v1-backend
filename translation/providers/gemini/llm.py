import logging
import time
from typing import Dict, Any
from google import genai
from django.conf import settings
from translation.providers.base import BaseTranslationProvider

logger = logging.getLogger(__name__)

# Initialize GenAI client
client = genai.Client(api_key=settings.GEMINI_API_KEY)

class GeminiTranslationProvider(BaseTranslationProvider):
    """Gemini-based Text Translation provider"""
    
    def __init__(self, model: str = "gemini-2.0-flash"):
        self.model = model
    
    def translate(self, text: str, source_lang: str, target_lang: str) -> Dict[str, Any]:
        """Translate text from source to target language using Gemini AI"""
        start_time = time.time()
        try:
            if not text or len(text.strip()) == 0:
                return { 'success': False, 'translated_text': '', 'error': 'No text to translate' }
            
            # Skip translation if same language
            if source_lang == target_lang:
                return { 'success': True, 'translated_text': text, 'processing_time': 0.0 }
            
            # Create translation prompt
            prompt = f"""Translate the following text from {source_lang} to {target_lang}. Return only the translated text:
            
            {text}"""
            
            # Process translation
            response = client.models.generate_content(
                model=self.model,
                contents=prompt
            )
            
            translated_text = response.text.strip() if response.text else ""
            processing_time = time.time() - start_time
            
            # Extract token usage
            usage = None
            if hasattr(response, 'usage_metadata'):
                usage = {
                    'prompt_tokens': response.usage_metadata.prompt_token_count,
                    'candidates_tokens': response.usage_metadata.candidates_token_count,
                    'total_tokens': response.usage_metadata.total_token_count
                }
            
            return {
                'success': True,
                'translated_text': translated_text,
                'processing_time': processing_time,
                'usage': usage,
                'model': self.model,
                'provider': 'Google'
            }
            
        except Exception as e:
            logger.error(f"Error in Gemini Translation provider: {str(e)}")
            return {
                'success': False,
                'translated_text': '',
                'error': str(e),
                'processing_time': time.time() - start_time
            }

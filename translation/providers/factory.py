from django.conf import settings
from translation.providers.gemini.asr import GeminiASRProvider
from translation.providers.gemini.llm import GeminiTranslationProvider
from translation.providers.gemini.tts import GeminiTTSProvider
from translation.providers.base import BaseASRProvider, BaseTranslationProvider, BaseTTSProvider

class ProviderFactory:
    """Factory to get the active translation providers"""
    
    @staticmethod
    def get_asr_provider() -> BaseASRProvider:
        # We could use settings to switch providers
        # provider_type = getattr(settings, 'ASR_PROVIDER', 'gemini')
        return GeminiASRProvider()
    
    @staticmethod
    def get_translation_provider() -> BaseTranslationProvider:
        return GeminiTranslationProvider()
    
    @staticmethod
    def get_tts_provider() -> BaseTTSProvider:
        return GeminiTTSProvider()

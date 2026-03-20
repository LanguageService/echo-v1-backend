from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, BinaryIO

class BaseASRProvider(ABC):
    """Abstract Base Class for Speech-to-Text (ASR) providers"""
    
    @abstractmethod
    def transcribe(self, audio_file: BinaryIO, language: str = 'auto') -> Dict[str, Any]:
        """
        Transcribe audio to text
        Returns: { 'success': bool, 'text': str, 'language': str, 'confidence': float, 'error': str }
        """
        pass

class BaseTranslationProvider(ABC):
    """Abstract Base Class for Text Translation providers"""
    
    @abstractmethod
    def translate(self, text: str, source_lang: str, target_lang: str) -> Dict[str, Any]:
        """
        Translate text from source to target language
        Returns: { 'success': bool, 'translated_text': str, 'error': str }
        """
        pass

class BaseTTSProvider(ABC):
    """Abstract Base Class for Text-to-Speech (TTS) providers"""
    
    @abstractmethod
    def synthesize(self, text: str, language: str, voice: Optional[str] = None) -> Dict[str, Any]:
        """
        Synthesize text to speech
        Returns: { 'success': bool, 'audio_data': bytes, 'error': str }
        """
        pass

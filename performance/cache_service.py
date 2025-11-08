"""
Smart caching service for performance optimization
"""
import hashlib
import json
import time
from typing import Dict, Any, Optional
from django.core.cache import cache
from django.conf import settings


class CacheService:
    """Intelligent caching service for OCR results and translations"""
    
    def __init__(self):
        self.default_ttl = 3600  # 1 hour
        self.translation_ttl = 86400  # 24 hours
        self.image_ttl = 1800  # 30 minutes
        
    def get_image_hash(self, image_path: str) -> str:
        """Generate unique hash for image content"""
        try:
            with open(image_path, 'rb') as f:
                content = f.read()
            return hashlib.md5(content).hexdigest()
        except Exception:
            # Fallback to filename if file read fails
            return hashlib.md5(image_path.encode()).hexdigest()
    
    def get_text_hash(self, text: str) -> str:
        """Generate unique hash for text content"""
        return hashlib.md5(text.encode('utf-8')).hexdigest()
    
    # OCR Result Caching
    def cache_ocr_result(self, image_hash: str, result: Dict[str, Any]) -> None:
        """Cache OCR extraction results"""
        cache_key = f"ocr:result:{image_hash}"
        
        # Add metadata
        cached_data = {
            'result': result,
            'cached_at': time.time(),
            'version': '1.0'
        }
        
        cache.set(cache_key, cached_data, self.image_ttl)
    
    def get_cached_ocr_result(self, image_hash: str) -> Optional[Dict[str, Any]]:
        """Retrieve cached OCR result"""
        cache_key = f"ocr:result:{image_hash}"
        cached_data = cache.get(cache_key)
        
        if cached_data and isinstance(cached_data, dict):
            return cached_data.get('result')
        return None
    
    # Translation Caching
    def cache_translation(self, text_hash: str, source_lang: str, 
                         target_lang: str, translation: str, 
                         service_used: str = 'gemini') -> None:
        """Cache translation results"""
        cache_key = f"trans:{text_hash}:{source_lang}:{target_lang}"
        
        cached_data = {
            'translation': translation,
            'service_used': service_used,
            'cached_at': time.time(),
            'source_lang': source_lang,
            'target_lang': target_lang
        }
        
        cache.set(cache_key, cached_data, self.translation_ttl)
    
    def get_cached_translation(self, text_hash: str, source_lang: str, 
                              target_lang: str) -> Optional[Dict[str, Any]]:
        """Retrieve cached translation"""
        cache_key = f"trans:{text_hash}:{source_lang}:{target_lang}"
        cached_data = cache.get(cache_key)
        
        if cached_data and isinstance(cached_data, dict):
            return {
                'translation': cached_data.get('translation'),
                'service_used': cached_data.get('service_used', 'unknown'),
                'cached': True
            }
        return None
    
    # Language Detection Caching
    def cache_language_detection(self, text_hash: str, detected_lang: str, 
                                confidence: float = 0.0) -> None:
        """Cache language detection results"""
        cache_key = f"lang:{text_hash}"
        
        cached_data = {
            'language': detected_lang,
            'confidence': confidence,
            'cached_at': time.time()
        }
        
        cache.set(cache_key, cached_data, self.default_ttl)
    
    def get_cached_language_detection(self, text_hash: str) -> Optional[Dict[str, Any]]:
        """Retrieve cached language detection"""
        cache_key = f"lang:{text_hash}"
        cached_data = cache.get(cache_key)
        
        if cached_data and isinstance(cached_data, dict):
            return {
                'language': cached_data.get('language'),
                'confidence': cached_data.get('confidence', 0.0),
                'cached': True
            }
        return None
    
    # Voice Processing Caching
    def cache_voice_transcription(self, audio_hash: str, transcription: str, 
                                 language: str) -> None:
        """Cache voice transcription results"""
        cache_key = f"voice:transcript:{audio_hash}"
        
        cached_data = {
            'transcription': transcription,
            'language': language,
            'cached_at': time.time()
        }
        
        cache.set(cache_key, cached_data, self.default_ttl)
    
    def get_cached_voice_transcription(self, audio_hash: str) -> Optional[Dict[str, Any]]:
        """Retrieve cached voice transcription"""
        cache_key = f"voice:transcript:{audio_hash}"
        cached_data = cache.get(cache_key)
        
        if cached_data and isinstance(cached_data, dict):
            return {
                'transcription': cached_data.get('transcription'),
                'language': cached_data.get('language'),
                'cached': True
            }
        return None
    
    # User-specific caching
    def cache_user_preferences(self, user_id: int, preferences: Dict[str, Any]) -> None:
        """Cache user preferences for faster access"""
        cache_key = f"user:prefs:{user_id}"
        cache.set(cache_key, preferences, self.translation_ttl)
    
    def get_cached_user_preferences(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Retrieve cached user preferences"""
        cache_key = f"user:prefs:{user_id}"
        return cache.get(cache_key)
    
    # Cache statistics and monitoring
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache performance statistics"""
        try:
            # This is a simplified version - in production you'd use Redis INFO
            cache_info = {
                'backend': getattr(settings, 'CACHES', {}).get('default', {}).get('BACKEND', 'unknown'),
                'status': 'active',
                'estimated_entries': 'unknown'  # Would require Redis connection for accurate count
            }
            return cache_info
        except Exception:
            return {'status': 'error', 'backend': 'unknown'}
    
    def clear_user_cache(self, user_id: int) -> None:
        """Clear all cache entries for a specific user"""
        patterns = [
            f"user:prefs:{user_id}",
            f"ocr:*:user:{user_id}",
            f"voice:*:user:{user_id}"
        ]
        
        # Note: This is simplified - in production with Redis you'd use SCAN
        for pattern in patterns:
            try:
                cache.delete(pattern)
            except Exception:
                pass
    
    def warm_cache(self, user_id: int, common_translations: list) -> None:
        """Pre-warm cache with common translations for user"""
        for translation_data in common_translations:
            text = translation_data.get('text', '')
            source_lang = translation_data.get('source_lang', 'auto')
            target_lang = translation_data.get('target_lang', 'en')
            result = translation_data.get('translation', '')
            
            if text and result:
                text_hash = self.get_text_hash(text)
                self.cache_translation(text_hash, source_lang, target_lang, result)


# Global cache service instance
cache_service = CacheService()
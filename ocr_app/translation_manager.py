"""
Translation Service Manager

Manages multiple translation service providers with intelligent fallback,
load balancing, and service selection capabilities.
"""

import logging
import time
from typing import List, Dict, Optional, Tuple
from .translation_services import (
    BaseTranslationService, 
    TranslationProvider, 
    TranslationResult,
    GeminiTranslationService,
    OpenAITranslationService,
    AnthropicTranslationService
)

logger = logging.getLogger(__name__)


class TranslationServiceManager:
    """Manages multiple translation services with fallback logic"""
    
    def __init__(self):
        self.services: Dict[TranslationProvider, BaseTranslationService] = {}
        self.service_priorities = [
            TranslationProvider.GEMINI,    # Primary (free tier available)
            TranslationProvider.OPENAI,    # Secondary (high quality)
            TranslationProvider.ANTHROPIC  # Tertiary (excellent quality)
        ]
        self._initialize_services()
    
    def _initialize_services(self):
        """Initialize all available translation services"""
        service_classes = {
            TranslationProvider.GEMINI: GeminiTranslationService,
            TranslationProvider.OPENAI: OpenAITranslationService,
            TranslationProvider.ANTHROPIC: AnthropicTranslationService
        }
        
        for provider, service_class in service_classes.items():
            try:
                service = service_class()
                if service.is_available:
                    self.services[provider] = service
                    logger.info(f"Initialized {provider.value} translation service")
                else:
                    logger.warning(f"Service {provider.value} not available (missing API key)")
            except Exception as e:
                logger.error(f"Failed to initialize {provider.value} service: {str(e)}")
    
    def get_available_services(self) -> List[TranslationProvider]:
        """Get list of available translation services"""
        return list(self.services.keys())
    
    def translate_with_fallback(self, 
                               text: str,
                               target_language: str = "en",
                               source_language: str = "auto",
                               preferred_service: Optional[TranslationProvider] = None,
                               user=None,
                               ocr_result=None) -> TranslationResult:
        """
        Translate text with automatic fallback to other services if primary fails
        
        Args:
            text: Text to translate
            target_language: Target language code
            source_language: Source language code (auto for detection)
            preferred_service: Preferred translation service
            
        Returns:
            TranslationResult with success/failure information
        """
        if not self.services:
            return TranslationResult(
                translated_text=text,
                confidence_score=0.0,
                provider=TranslationProvider.GEMINI,
                source_language=source_language,
                target_language=target_language,
                error_message="No translation services available"
            )
        
        # Determine service order
        service_order = self._get_service_order(preferred_service)
        
        last_error = None
        failed_providers = []
        
        for provider in service_order:
            if provider not in self.services:
                continue
                
            try:
                logger.info(f"Attempting translation with {provider.value}")
                result = self.services[provider].translate_text(
                    text=text,
                    target_language=target_language,
                    source_language=source_language
                )
                
                if result.success:
                    logger.info(f"Translation successful with {provider.value} (confidence: {result.confidence_score})")
                    # Mark any previous failures as resolved if we had them
                    if failed_providers:
                        self._log_resolved_failures(failed_providers, provider.value, user, ocr_result)
                    return result
                else:
                    last_error = result.error_message
                    logger.warning(f"Translation failed with {provider.value}: {last_error}")
                    failed_providers.append((provider, last_error, 'api_error'))
                    self._log_translation_failure(provider, text, source_language, target_language, last_error, 'api_error', user, ocr_result)
                    
            except Exception as e:
                last_error = str(e)
                logger.error(f"Exception with {provider.value}: {last_error}")
                failed_providers.append((provider, last_error, 'unknown'))
                self._log_translation_failure(provider, text, source_language, target_language, last_error, 'unknown', user, ocr_result)
                continue
        
        # All services failed
        return TranslationResult(
            translated_text=text,
            confidence_score=0.0,
            provider=service_order[0] if service_order else TranslationProvider.GEMINI,
            source_language=source_language,
            target_language=target_language,
            error_message=f"All translation services failed. Last error: {last_error}"
        )
    
    def translate_with_comparison(self, 
                                 text: str,
                                 target_language: str = "en",
                                 source_language: str = "auto") -> Dict[str, TranslationResult]:
        """
        Translate using multiple services and return comparison results
        
        Returns:
            Dictionary mapping provider names to translation results
        """
        results = {}
        
        for provider, service in self.services.items():
            try:
                result = service.translate_text(
                    text=text,
                    target_language=target_language,
                    source_language=source_language
                )
                results[provider.value] = result
            except Exception as e:
                logger.error(f"Error translating with {provider.value}: {str(e)}")
                results[provider.value] = TranslationResult(
                    translated_text=text,
                    confidence_score=0.0,
                    provider=provider,
                    source_language=source_language,
                    target_language=target_language,
                    error_message=str(e)
                )
        
        return results
    
    def get_best_translation(self,
                           text: str,
                           target_language: str = "en",
                           source_language: str = "auto") -> TranslationResult:
        """
        Get the best translation by comparing results from multiple services
        
        Returns:
            The translation result with highest confidence score
        """
        results = self.translate_with_comparison(text, target_language, source_language)
        
        if not results:
            return TranslationResult(
                translated_text=text,
                confidence_score=0.0,
                provider=TranslationProvider.GEMINI,
                source_language=source_language,
                target_language=target_language,
                error_message="No translation services available"
            )
        
        # Find result with highest confidence
        best_result = None
        highest_confidence = -1.0
        
        for provider_name, result in results.items():
            if result.success and result.confidence_score > highest_confidence:
                highest_confidence = result.confidence_score
                best_result = result
        
        # If no successful results, return the first one
        if best_result is None:
            best_result = next(iter(results.values()))
        
        return best_result
    
    def _get_service_order(self, preferred_service: Optional[TranslationProvider]) -> List[TranslationProvider]:
        """Get ordered list of services to try"""
        if preferred_service and preferred_service in self.services:
            # Put preferred service first, then others by priority
            order = [preferred_service]
            for provider in self.service_priorities:
                if provider != preferred_service and provider in self.services:
                    order.append(provider)
            return order
        else:
            # Use default priority order
            return [p for p in self.service_priorities if p in self.services]
    
    def get_service_status(self) -> Dict[str, Dict[str, any]]:
        """Get status information for all services"""
        status = {}
        
        for provider, service in self.services.items():
            status[provider.value] = {
                "available": service.is_available,
                "supported_languages": len(service.get_supported_languages()),
                "provider_name": provider.value.title()
            }
        
        # Add unavailable services
        all_providers = [TranslationProvider.GEMINI, TranslationProvider.OPENAI, TranslationProvider.ANTHROPIC]
        for provider in all_providers:
            if provider not in self.services:
                status[provider.value] = {
                    "available": False,
                    "supported_languages": 0,
                    "provider_name": provider.value.title(),
                    "reason": "API key not configured"
                }
        
        return status
    
    def get_all_supported_languages(self) -> List[Dict[str, str]]:
        """Get combined list of all supported languages from all services"""
        all_languages = {}
        
        for service in self.services.values():
            for lang in service.get_supported_languages():
                if lang["code"] not in all_languages:
                    all_languages[lang["code"]] = lang["name"]
        
        return [{"code": code, "name": name} for code, name in sorted(all_languages.items())]
    
    def _log_translation_failure(self, provider, text, source_language, target_language, error_message, error_type, user=None, ocr_result=None):
        """Log a translation failure to the database"""
        try:
            # Avoid circular import by importing here
            from .models import TranslationFailureLog
            
            # Determine error type based on error message
            if "quota" in error_message.lower() or "limit" in error_message.lower():
                error_type = "quota_exceeded"
            elif "auth" in error_message.lower() or "key" in error_message.lower():
                error_type = "auth_error"
            elif "timeout" in error_message.lower():
                error_type = "timeout"
            elif "network" in error_message.lower() or "connection" in error_message.lower():
                error_type = "network_error"
            
            failure_log = TranslationFailureLog.objects.create(
                user=user,
                ocr_result=ocr_result,
                source_text=text[:1000],  # Limit text length
                source_language=source_language,
                target_language=target_language,
                attempted_provider=provider.value,
                error_message=error_message[:500],  # Limit error message length
                error_type=error_type,
                retry_count=0
            )
            logger.info(f"Logged translation failure: {failure_log.id}")
            
        except Exception as e:
            logger.error(f"Failed to log translation failure: {str(e)}")
    
    def _log_resolved_failures(self, failed_providers, successful_provider, user=None, ocr_result=None):
        """Mark previous failures as resolved with successful fallback"""
        try:
            from .models import TranslationFailureLog
            
            # Find recent failures for this user/OCR result
            recent_failures = TranslationFailureLog.objects.filter(
                user=user,
                ocr_result=ocr_result,
                resolved_at__isnull=True
            ).order_by('-created_at')[:len(failed_providers)]
            
            for failure in recent_failures:
                failure.mark_resolved(fallback_provider=successful_provider)
                logger.info(f"Marked failure {failure.id} as resolved with {successful_provider}")
                
        except Exception as e:
            logger.error(f"Failed to mark failures as resolved: {str(e)}")


# Global instance
translation_manager = TranslationServiceManager()
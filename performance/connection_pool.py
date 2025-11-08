"""
Connection pooling and optimization for external API calls
"""
import httpx
import asyncio
import time
import logging
from typing import Dict, Any, Optional, List
from contextlib import asynccontextmanager
from google import genai
import os
from decouple import config

logger = logging.getLogger(__name__)
GEMINI_API_KEY = config("GEMINI_API_KEY", "")

class ConnectionPoolManager:
    """Manage HTTP connection pools for optimal API performance"""
    
    def __init__(self):
        self.pools = {}
        self.stats = {
            'requests_made': 0,
            'cache_hits': 0,
            'errors': 0,
            'total_time': 0.0
        }
    
    def get_http_client(self, service: str = 'default') -> httpx.AsyncClient:
        """Get optimized HTTP client with connection pooling"""
        if service not in self.pools:
            limits = httpx.Limits(
                max_keepalive_connections=10,
                max_connections=20,
                keepalive_expiry=30
            )
            
            timeout = httpx.Timeout(
                connect=10.0,
                read=30.0,
                write=10.0,
                pool=5.0
            )
            
            self.pools[service] = httpx.AsyncClient(
                limits=limits,
                timeout=timeout,
                http2=True  # Enable HTTP/2 for better performance
            )
        
        return self.pools[service]
    
    async def close_all_pools(self):
        """Close all connection pools"""
        for client in self.pools.values():
            await client.aclose()
        self.pools.clear()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get connection pool statistics"""
        return {
            'active_pools': len(self.pools),
            'total_requests': self.stats['requests_made'],
            'cache_hits': self.stats['cache_hits'],
            'errors': self.stats['errors'],
            'avg_response_time': (
                self.stats['total_time'] / self.stats['requests_made'] 
                if self.stats['requests_made'] > 0 else 0
            )
        }


class OptimizedGeminiClient:
    """Optimized Gemini client with connection pooling and retry logic"""
    
    def __init__(self):
        self.connection_manager = ConnectionPoolManager()
        self.retry_config = {
            'max_retries': 3,
            'backoff_factor': 0.5,
            'retry_statuses': [429, 500, 502, 503, 504]
        }
        
        # Initialize Gemini client with optimized HTTP client
        self.client = None
        self._initialize_client()
    
    def _initialize_client(self):
        """Initialize Gemini client with connection pooling"""
        try:
            api_key = GEMINI_API_KEY
            if not api_key:
                logger.warning("GEMINI_API_KEY not found")
                return
            
            # Create optimized HTTP client for Gemini
            http_client = self.connection_manager.get_http_client('gemini')
            
            self.client = genai.Client(
                api_key=api_key,
                # http_client=http_client  # Enable when Gemini SDK supports it
            )
            
        except Exception as e:
            logger.error(f"Failed to initialize Gemini client: {str(e)}")
    
    async def process_image_with_retry(self, image_path: str, prompt: str) -> Dict[str, Any]:
        """Process image with retry logic and error handling"""
        if not self.client:
            raise ValueError("Gemini client not initialized")
        
        start_time = time.time()
        
        for attempt in range(self.retry_config['max_retries']):
            try:
                # Read image
                with open(image_path, 'rb') as f:
                    image_data = f.read()
                
                # Process with Gemini (adapt to your actual implementation)
                response = await self._process_with_gemini(image_data, prompt)
                
                # Update stats
                self.connection_manager.stats['requests_made'] += 1
                self.connection_manager.stats['total_time'] += time.time() - start_time
                
                return {
                    'text': response.text or '',
                    'confidence': 0.9,  # Placeholder
                    'processing_time': time.time() - start_time,
                    'attempts': attempt + 1
                }
                
            except Exception as e:
                logger.warning(f"Gemini API attempt {attempt + 1} failed: {str(e)}")
                
                if attempt == self.retry_config['max_retries'] - 1:
                    self.connection_manager.stats['errors'] += 1
                    raise
                
                # Exponential backoff
                await asyncio.sleep(
                    self.retry_config['backoff_factor'] * (2 ** attempt)
                )
    
    async def translate_with_retry(self, text: str, target_language: str) -> Dict[str, Any]:
        """Translate text with retry logic"""
        if not self.client:
            raise ValueError("Gemini client not initialized")
        
        start_time = time.time()
        
        for attempt in range(self.retry_config['max_retries']):
            try:
                prompt = f"Translate the following text to {target_language}: {text}"
                
                response = self.client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=prompt
                )
                
                self.connection_manager.stats['requests_made'] += 1
                self.connection_manager.stats['total_time'] += time.time() - start_time
                
                return {
                    'translation': response.text or text,
                    'service_used': 'gemini',
                    'processing_time': time.time() - start_time,
                    'attempts': attempt + 1
                }
                
            except Exception as e:
                logger.warning(f"Translation attempt {attempt + 1} failed: {str(e)}")
                
                if attempt == self.retry_config['max_retries'] - 1:
                    self.connection_manager.stats['errors'] += 1
                    raise
                
                await asyncio.sleep(
                    self.retry_config['backoff_factor'] * (2 ** attempt)
                )
    
    async def _process_with_gemini(self, image_data: bytes, prompt: str):
        """Process image with Gemini API"""
        from google.genai import types
        
        response = self.client.models.generate_content(
            model="gemini-2.5-pro",
            contents=[
                types.Part.from_bytes(
                    data=image_data,
                    mime_type="image/jpeg",
                ),
                prompt
            ],
        )
        
        return response


class BatchProcessor:
    """Batch processing for multiple API requests"""
    
    def __init__(self, max_concurrent: int = 5):
        self.max_concurrent = max_concurrent
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.results = []
    
    async def process_batch(self, requests: List[Dict[str, Any]], 
                          processor_func) -> List[Dict[str, Any]]:
        """Process multiple requests concurrently with rate limiting"""
        tasks = []
        
        for request_data in requests:
            task = self._process_single_request(request_data, processor_func)
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Filter out exceptions and add to results
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                processed_results.append({
                    'error': str(result),
                    'request_index': i
                })
            else:
                processed_results.append(result)
        
        return processed_results
    
    async def _process_single_request(self, request_data: Dict[str, Any], 
                                    processor_func) -> Dict[str, Any]:
        """Process single request with semaphore rate limiting"""
        async with self.semaphore:
            try:
                result = await processor_func(request_data)
                return result
            except Exception as e:
                logger.error(f"Batch request failed: {str(e)}")
                raise


class ServiceManager:
    """Manage multiple AI services with fallback and load balancing"""
    
    def __init__(self):
        self.services = {
            'gemini': OptimizedGeminiClient(),
            # Add other services here
        }
        
        self.service_health = {
            'gemini': {'status': 'healthy', 'last_check': time.time()}
        }
        
        self.fallback_order = ['gemini']  # Add more services as needed
    
    async def process_with_fallback(self, request_type: str, 
                                  request_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process request with automatic service fallback"""
        errors = []
        
        for service_name in self.fallback_order:
            try:
                service = self.services.get(service_name)
                if not service:
                    continue
                
                # Check service health
                if not self._is_service_healthy(service_name):
                    continue
                
                if request_type == 'ocr':
                    result = await service.process_image_with_retry(
                        request_data['image_path'],
                        request_data.get('prompt', 'Extract all text from this image')
                    )
                elif request_type == 'translation':
                    result = await service.translate_with_retry(
                        request_data['text'],
                        request_data['target_language']
                    )
                else:
                    raise ValueError(f"Unknown request type: {request_type}")
                
                result['service_used'] = service_name
                return result
                
            except Exception as e:
                error_msg = f"{service_name}: {str(e)}"
                errors.append(error_msg)
                logger.warning(f"Service {service_name} failed: {str(e)}")
                
                # Mark service as unhealthy on repeated failures
                self._update_service_health(service_name, False)
        
        # All services failed
        raise Exception(f"All services failed: {'; '.join(errors)}")
    
    def _is_service_healthy(self, service_name: str) -> bool:
        """Check if service is healthy"""
        health_info = self.service_health.get(service_name, {})
        return health_info.get('status') == 'healthy'
    
    def _update_service_health(self, service_name: str, is_healthy: bool):
        """Update service health status"""
        self.service_health[service_name] = {
            'status': 'healthy' if is_healthy else 'unhealthy',
            'last_check': time.time()
        }
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on all services"""
        health_status = {}
        
        for service_name, service in self.services.items():
            try:
                # Perform a lightweight test request
                start_time = time.time()
                
                if hasattr(service, 'client') and service.client:
                    # Test with a simple request
                    test_result = await service.translate_with_retry("Hello", "es")
                    response_time = time.time() - start_time
                    
                    health_status[service_name] = {
                        'status': 'healthy',
                        'response_time': response_time,
                        'last_check': time.time()
                    }
                    
                    self._update_service_health(service_name, True)
                else:
                    health_status[service_name] = {
                        'status': 'unavailable',
                        'error': 'Client not initialized',
                        'last_check': time.time()
                    }
                    
                    self._update_service_health(service_name, False)
                
            except Exception as e:
                health_status[service_name] = {
                    'status': 'unhealthy',
                    'error': str(e),
                    'last_check': time.time()
                }
                
                self._update_service_health(service_name, False)
        
        return health_status
    
    async def get_service_stats(self) -> Dict[str, Any]:
        """Get statistics from all services"""
        stats = {}
        
        for service_name, service in self.services.items():
            if hasattr(service, 'connection_manager'):
                stats[service_name] = service.connection_manager.get_stats()
        
        return stats


# Global instances
connection_pool_manager = ConnectionPoolManager()
service_manager = ServiceManager()

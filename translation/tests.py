"""
Comprehensive unit tests for voice translation functionality

Tests cover async services, API endpoints, authentication, error handling,
and background task processing.
"""

import asyncio
import tempfile
import os
import json
from unittest.mock import Mock, patch, AsyncMock
from django.test import TestCase, TransactionTestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken
from celery.result import AsyncResult

from .models import Translation, UserSettings, LanguageSupport
from .services import (
    AsyncVoiceTranslationService, AsyncSpeechService, 
    AsyncTranslationService, AsyncTextToSpeechService
)
from .tasks import async_voice_translation_task, batch_translation_task

User = get_user_model()


class AsyncServiceTestCase(TestCase):
    """Test cases for async voice translation services"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
        
        # Create test language support
        LanguageSupport.objects.create(
            code='en',
            name='English',
            speech_to_text_supported=True,
            text_to_speech_supported=True,
            translation_supported=True
        )
        LanguageSupport.objects.create(
            code='es',
            name='Spanish',
            speech_to_text_supported=True,
            text_to_speech_supported=True,
            translation_supported=True
        )
        
        # Create mock audio file
        self.audio_content = b"fake audio content"
        self.audio_file = SimpleUploadedFile(
            "test_audio.wav",
            self.audio_content,
            content_type="audio/wav"
        )

    def test_async_speech_service_transcription(self):
        """Test async speech-to-text functionality"""
        async def run_test():
            speech_service = AsyncSpeechService()
            
            # Mock Gemini response
            mock_response = Mock()
            mock_response.text = "Hello, this is a test transcription"
            
            with patch('translation.services.client') as mock_client:
                mock_client.models.generate_content.return_value = mock_response
                
                # Reset file pointer
                self.audio_file.seek(0)
                
                result = await speech_service.transcribe_audio(
                    self.audio_file, 
                    language='auto'
                )
                
                self.assertTrue(result['success'])
                self.assertEqual(result['text'], "Hello, this is a test transcription")
                self.assertGreater(result['confidence'], 0)
                self.assertIsInstance(result['processing_time'], float)
        
        # Run async test
        asyncio.run(run_test())

    def test_async_translation_service(self):
        """Test async text translation functionality"""
        async def run_test():
            translation_service = AsyncTranslationService()
            
            # Mock Gemini response
            mock_response = Mock()
            mock_response.text = "Hola, esta es una prueba"
            
            with patch('translation.services.client') as mock_client:
                mock_client.models.generate_content.return_value = mock_response
                
                result = await translation_service.translate_text(
                    "Hello, this is a test",
                    source_lang='en',
                    target_lang='es'
                )
                
                self.assertTrue(result['success'])
                self.assertEqual(result['translated_text'], "Hola, esta es una prueba")
                self.assertEqual(result['source_language'], 'en')
                self.assertEqual(result['target_language'], 'es')
        
        asyncio.run(run_test())

    def test_async_text_to_speech_service(self):
        """Test async text-to-speech functionality"""
        async def run_test():
            tts_service = AsyncTextToSpeechService()
            
            result = await tts_service.synthesize_speech(
                "Hello world",
                language='en',
                voice='Zephyr'
            )
            
            self.assertTrue(result['success'])
            self.assertEqual(result['language'], 'en')
            self.assertEqual(result['voice'], 'Zephyr')
            self.assertIsInstance(result['processing_time'], float)
        
        asyncio.run(run_test())

    def test_async_voice_translation_service_full_pipeline(self):
        """Test complete async voice translation pipeline"""
        async def run_test():
            service = AsyncVoiceTranslationService()
            
            # Mock all external services
            with patch.object(service.speech_service, 'transcribe_audio') as mock_stt, \
                 patch.object(service.translation_service, 'translate_text') as mock_translate, \
                 patch.object(service.tts_service, 'synthesize_speech') as mock_tts:
                
                # Configure mocks
                mock_stt.return_value = {
                    'success': True,
                    'text': 'Hello world',
                    'language': 'en',
                    'confidence': 0.95,
                    'processing_time': 1.0
                }
                
                mock_translate.return_value = {
                    'success': True,
                    'translated_text': 'Hola mundo',
                    'source_language': 'en',
                    'target_language': 'es',
                    'processing_time': 0.5
                }
                
                mock_tts.return_value = {
                    'success': True,
                    'processing_time': 0.3
                }
                
                # Reset file pointer
                self.audio_file.seek(0)
                
                result = await service.process_voice_translation(
                    user=self.user,
                    audio_file=self.audio_file,
                    session_id='test-session',
                    target_language='es'
                )
                
                self.assertTrue(result['success'])
                self.assertEqual(result['original_text'], 'Hello world')
                self.assertEqual(result['translated_text'], 'Hola mundo')
                self.assertEqual(result['original_language'], 'en')
                self.assertEqual(result['target_language'], 'es')
                self.assertIn('translation_id', result)
        
        asyncio.run(run_test())


class VoiceTranslationAPITestCase(APITestCase):
    """Test cases for voice translation API endpoints"""
    
    def setUp(self):
        """Set up test data and authentication"""
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
        
        # Create JWT token for authentication
        refresh = RefreshToken.for_user(self.user)
        self.access_token = str(refresh.access_token)
        
        # Set up authenticated client
        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.access_token}')
        
        # Create test language support
        LanguageSupport.objects.create(
            code='en',
            name='English',
            speech_to_text_supported=True,
            text_to_speech_supported=True,
            translation_supported=True
        )
        
        # Create mock audio file
        self.audio_file = SimpleUploadedFile(
            "test_audio.wav",
            b"fake audio content",
            content_type="audio/wav"
        )

    def test_regular_voice_translation_endpoint(self):
        """Test regular voice translation endpoint"""
        url = reverse('translation:voice_translate')
        
        with patch('translation.services.VoiceTranslationService.process_voice_translation') as mock_process:
            mock_process.return_value = {
                'success': True,
                'translation_id': 'test-id',
                'original_text': 'Hello',
                'translated_text': 'Hola',
                'original_language': 'en',
                'target_language': 'es',
                'confidence_score': 0.95,
                'processing_time': 2.0
            }
            
            response = self.client.post(url, {
                'audio_file': self.audio_file,
                'target_language': 'es'
            }, format='multipart')
            
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertTrue(response.data['success'])
            self.assertEqual(response.data['original_text'], 'Hello')

    def test_async_voice_translation_endpoint(self):
        """Test async voice translation endpoint"""
        url = reverse('translation:async_voice_translate')
        
        with patch('translation.services.AsyncVoiceTranslationService.process_voice_translation') as mock_process:
            # Configure async mock
            async def mock_async_process(*args, **kwargs):
                return {
                    'success': True,
                    'translation_id': 'async-test-id',
                    'original_text': 'Hello async',
                    'translated_text': 'Hola async',
                    'original_language': 'en',
                    'target_language': 'es',
                    'confidence_score': 0.95,
                    'processing_time': 1.5
                }
            
            mock_process.side_effect = mock_async_process
            
            response = self.client.post(url, {
                'audio_file': self.audio_file,
                'target_language': 'es'
            }, format='multipart')
            
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertTrue(response.data['success'])
            self.assertIn('async_note', response.data)

    def test_background_translation_endpoint(self):
        """Test background translation with Celery task"""
        url = reverse('translation:background_voice_translate')
        
        with patch('translation.tasks.async_voice_translation_task.delay') as mock_delay:
            mock_task = Mock()
            mock_task.id = 'test-task-id'
            mock_delay.return_value = mock_task
            
            response = self.client.post(url, {
                'audio_file': self.audio_file,
                'target_language': 'es'
            }, format='multipart')
            
            self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
            self.assertTrue(response.data['success'])
            self.assertEqual(response.data['task_id'], 'test-task-id')
            self.assertEqual(response.data['status'], 'dispatched')

    def test_task_status_endpoint(self):
        """Test task status checking endpoint"""
        task_id = 'test-task-id'
        url = reverse('translation:task_status', kwargs={'task_id': task_id})
        
        with patch('celery.result.AsyncResult') as mock_result:
            mock_task = Mock()
            mock_task.state = 'SUCCESS'
            mock_task.result = {
                'success': True,
                'original_text': 'Test result',
                'translated_text': 'Resultado de prueba'
            }
            mock_result.return_value = mock_task
            
            response = self.client.get(url)
            
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertEqual(response.data['status'], 'completed')
            self.assertIn('result', response.data)

    def test_async_translation_history_endpoint(self):
        """Test async translation history endpoint"""
        url = reverse('translation:async_translation_history')
        
        # Create test translation
        Translation.objects.create(
            user=self.user,
            original_text='Test text',
            translated_text='Texto de prueba',
            original_language='en',
            target_language='es',
            confidence_score=0.95,
            processing_time=1.0
        )
        
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreater(response.data['count'], 0)
        self.assertIn('async_note', response.data)

    def test_authentication_required(self):
        """Test that authentication is required for protected endpoints"""
        # Remove authentication
        self.client.credentials()
        
        urls = [
            reverse('translation:voice_translate'),
            reverse('translation:async_voice_translate'),
            reverse('translation:background_voice_translate'),
            reverse('translation:async_translation_history'),
        ]
        
        for url in urls:
            response = self.client.post(url, {})
            self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_invalid_audio_file(self):
        """Test handling of invalid audio files"""
        url = reverse('translation:voice_translate')
        
        invalid_file = SimpleUploadedFile(
            "test.txt",
            b"not an audio file",
            content_type="text/plain"
        )
        
        response = self.client.post(url, {
            'audio_file': invalid_file,
            'target_language': 'es'
        }, format='multipart')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class CeleryTaskTestCase(TransactionTestCase):
    """Test cases for Celery background tasks"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
        
        # Create test language support
        LanguageSupport.objects.create(
            code='en',
            name='English',
            speech_to_text_supported=True,
            text_to_speech_supported=True,
            translation_supported=True
        )

    def test_async_voice_translation_task(self):
        """Test async voice translation Celery task"""
        # Create temporary audio file
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
            temp_file.write(b"fake audio content")
            temp_file_path = temp_file.name
        
        try:
            with patch('translation.tasks.AsyncVoiceTranslationService') as mock_service_class:
                mock_service = Mock()
                mock_service_class.return_value = mock_service
                
                # Mock async method
                async def mock_process(*args, **kwargs):
                    return {
                        'success': True,
                        'translation_id': 'task-test-id',
                        'original_text': 'Task test',
                        'translated_text': 'Prueba de tarea',
                        'processing_time': 2.0
                    }
                
                mock_service.process_voice_translation = mock_process
                
                # Execute task synchronously for testing
                result = async_voice_translation_task(
                    user_id=self.user.id,
                    audio_file_path=temp_file_path,
                    session_id='test-session',
                    target_language='es'
                )
                
                self.assertTrue(result['success'])
                self.assertTrue(result['processed_in_background'])
                self.assertIn('task_id', result)
                
        finally:
            # Clean up temporary file
            if os.path.exists(temp_file_path):
                os.unlink(temp_file_path)

    def test_batch_translation_task(self):
        """Test batch translation task"""
        translation_requests = [
            {
                'user_id': self.user.id,
                'audio_file_path': '/fake/path1.wav',
                'session_id': 'session1',
                'target_language': 'es',
                'request_id': 'req1'
            },
            {
                'user_id': self.user.id,
                'audio_file_path': '/fake/path2.wav',
                'session_id': 'session2',
                'target_language': 'fr',
                'request_id': 'req2'
            }
        ]
        
        with patch('translation.tasks.async_voice_translation_task.delay') as mock_delay:
            mock_task = Mock()
            mock_task.id = 'batch-task-id'
            mock_delay.return_value = mock_task
            
            result = batch_translation_task(translation_requests)
            
            self.assertEqual(result['total_requests'], 2)
            self.assertEqual(result['successful_dispatches'], 2)
            self.assertEqual(result['errors'], 0)
            self.assertEqual(len(result['results']), 2)


class ModelTestCase(TestCase):
    """Test cases for voice translation models"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )

    def test_translation_model_creation(self):
        """Test translation model creation and methods"""
        translation = Translation.objects.create(
            user=self.user,
            original_text='Hello world',
            translated_text='Hola mundo',
            original_language='en',
            target_language='es',
            confidence_score=0.95,
            processing_time=1.5,
            session_id='test-session'
        )
        
        self.assertEqual(str(translation), 'en -> es: Hello world...')
        self.assertEqual(translation.user, self.user)
        self.assertTrue(translation.id)
        self.assertIsNotNone(translation.created_at)

    def test_user_settings_model(self):
        """Test user settings model"""
        settings = UserSettings.objects.create(
            user=self.user,
            session_id='test-session',
            source_language='en',
            target_language='es',
            model='gemini-2.5-pro',
            voice='Zephyr',
            autoplay=True
        )
        
        self.assertEqual(settings.user, self.user)
        self.assertEqual(settings.model, 'gemini-2.5-pro')
        self.assertTrue(settings.autoplay)

    def test_language_support_model(self):
        """Test language support model"""
        language = LanguageSupport.objects.create(
            code='sw',
            name='Swahili',
            native_name='Kiswahili',
            speech_to_text_supported=True,
            text_to_speech_supported=True,
            translation_supported=True,
            is_african_language=True
        )
        
        self.assertEqual(str(language), 'Swahili (sw)')
        self.assertTrue(language.is_african_language)
        self.assertTrue(language.speech_to_text_supported)


class ErrorHandlingTestCase(APITestCase):
    """Test cases for error handling scenarios"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
        
        refresh = RefreshToken.for_user(self.user)
        self.access_token = str(refresh.access_token)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.access_token}')

    def test_service_error_handling(self):
        """Test error handling in services"""
        async def run_test():
            service = AsyncVoiceTranslationService()
            
            # Test with invalid audio file
            with patch.object(service.audio_service, 'validate_audio_file') as mock_validate:
                mock_validate.return_value = {
                    'valid': False,
                    'error': 'Invalid audio format'
                }
                
                invalid_file = SimpleUploadedFile("test.txt", b"not audio")
                result = await service.process_voice_translation(
                    user=self.user,
                    audio_file=invalid_file,
                    target_language='es'
                )
                
                self.assertFalse(result['success'])
                self.assertIn('error', result)
        
        asyncio.run(run_test())

    def test_api_error_responses(self):
        """Test API error response handling"""
        url = reverse('translation:voice_translate')
        
        # Test missing required fields
        response = self.client.post(url, {}, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        
        # Test invalid target language
        audio_file = SimpleUploadedFile("test.wav", b"fake audio")
        response = self.client.post(url, {
            'audio_file': audio_file,
            'target_language': 'invalid'
        }, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_database_error_handling(self):
        """Test database error scenarios"""
        url = reverse('translation:voice_translate')
        
        with patch('translation.models.Translation.objects.create') as mock_create:
            mock_create.side_effect = Exception("Database error")
            
            audio_file = SimpleUploadedFile("test.wav", b"fake audio")
            response = self.client.post(url, {
                'audio_file': audio_file,
                'target_language': 'es'
            }, format='multipart')
            
            self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)


class PerformanceTestCase(TestCase):
    """Test cases for performance and async behavior"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )

    def test_concurrent_async_operations(self):
        """Test concurrent async operations performance"""
        async def run_test():
            service = AsyncVoiceTranslationService()
            
            # Mock services to simulate processing time
            async def mock_stt(*args, **kwargs):
                await asyncio.sleep(0.1)  # Simulate processing
                return {
                    'success': True,
                    'text': 'Test text',
                    'language': 'en',
                    'confidence': 0.95,
                    'processing_time': 0.1
                }
            
            async def mock_translate(*args, **kwargs):
                await asyncio.sleep(0.1)  # Simulate processing
                return {
                    'success': True,
                    'translated_text': 'Texto de prueba',
                    'source_language': 'en',
                    'target_language': 'es',
                    'processing_time': 0.1
                }
            
            async def mock_tts(*args, **kwargs):
                await asyncio.sleep(0.1)  # Simulate processing
                return {
                    'success': True,
                    'processing_time': 0.1
                }
            
            with patch.object(service.speech_service, 'transcribe_audio', side_effect=mock_stt), \
                 patch.object(service.translation_service, 'translate_text', side_effect=mock_translate), \
                 patch.object(service.tts_service, 'synthesize_speech', side_effect=mock_tts):
                
                import time
                start_time = time.time()
                
                # Process multiple requests concurrently
                tasks = []
                for i in range(3):
                    audio_file = SimpleUploadedFile(f"test{i}.wav", b"fake audio")
                    task = service.process_voice_translation(
                        user=self.user,
                        audio_file=audio_file,
                        target_language='es'
                    )
                    tasks.append(task)
                
                results = await asyncio.gather(*tasks)
                
                end_time = time.time()
                total_time = end_time - start_time
                
                # Verify all tasks completed successfully
                for result in results:
                    self.assertTrue(result['success'])
                
                # Async processing should be faster than sequential
                # With 3 tasks taking ~0.3s each, async should be ~0.3s total vs ~0.9s sequential
                self.assertLess(total_time, 0.8)  # Allow some margin for overhead
        
        asyncio.run(run_test())

    def test_memory_usage_with_large_files(self):
        """Test memory handling with larger audio files"""
        # Create a larger mock audio file (1MB)
        large_audio_content = b"x" * (1024 * 1024)
        large_audio_file = SimpleUploadedFile(
            "large_test.wav",
            large_audio_content,
            content_type="audio/wav"
        )
        
        async def run_test():
            service = AsyncVoiceTranslationService()
            
            with patch.object(service.speech_service, 'transcribe_audio') as mock_stt:
                mock_stt.return_value = {
                    'success': True,
                    'text': 'Large file test',
                    'language': 'en',
                    'confidence': 0.95,
                    'processing_time': 2.0
                }
                
                result = await service.process_voice_translation(
                    user=self.user,
                    audio_file=large_audio_file,
                    target_language='es'
                )
                
                # Should handle large files without issues
                self.assertTrue(result['success'])
        
        asyncio.run(run_test())

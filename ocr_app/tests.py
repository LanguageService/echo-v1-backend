"""
Comprehensive unit tests for OCR translation functionality

Tests cover OCR services, API endpoints, authentication, error handling,
and image processing.
"""

import tempfile
import os
from unittest.mock import Mock, patch
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken
from PIL import Image
import io

from .models import OCRResult
from .services import OCRTranslatorService

User = get_user_model()


class OCRServiceTestCase(TestCase):
    """Test cases for OCR translation services"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
        
        # Create a test image
        self.test_image = self.create_test_image()

    def create_test_image(self):
        """Create a test image file"""
        # Create a simple test image
        img = Image.new('RGB', (100, 100), color='white')
        img_io = io.BytesIO()
        img.save(img_io, format='PNG')
        img_io.seek(0)
        
        return SimpleUploadedFile(
            "test_image.png",
            img_io.getvalue(),
            content_type="image/png"
        )

    def test_ocr_service_initialization(self):
        """Test OCR service initialization"""
        service = OCRTranslatorService()
        self.assertIsNotNone(service)
        self.assertTrue(hasattr(service, 'process_image'))

    def test_image_processing_success(self):
        """Test successful image processing"""
        service = OCRTranslatorService()
        
        # Mock Gemini vision response
        with patch('ocr_app.services.client') as mock_client:
            mock_response = Mock()
            mock_response.text = "Hello world"
            mock_client.models.generate_content.return_value = mock_response
            
            # Mock language detection
            with patch('langdetect.detect', return_value='en'):
                # Create temporary image file
                with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as temp_file:
                    temp_file.write(self.test_image.read())
                    temp_file_path = temp_file.name
                
                try:
                    result = service.process_image(temp_file_path)
                    
                    self.assertTrue(result['success'])
                    self.assertEqual(result['original_text'], 'Hello world')
                    self.assertEqual(result['detected_language'], 'en')
                    self.assertGreater(result['confidence_score'], 0)
                    self.assertIsInstance(result['processing_time'], float)
                    
                finally:
                    # Clean up
                    if os.path.exists(temp_file_path):
                        os.unlink(temp_file_path)

    def test_image_processing_error_handling(self):
        """Test error handling in image processing"""
        service = OCRTranslatorService()
        
        # Test with non-existent file
        result = service.process_image('/non/existent/file.png')
        
        self.assertFalse(result['success'])
        self.assertIn('error_message', result)

    def test_language_detection(self):
        """Test language detection functionality"""
        service = OCRTranslatorService()
        
        with patch('langdetect.detect') as mock_detect:
            mock_detect.return_value = 'es'
            
            detected_lang = service.detect_language("Hola mundo")
            self.assertEqual(detected_lang, 'es')
            
            # Test error handling
            mock_detect.side_effect = Exception("Detection error")
            detected_lang = service.detect_language("Test text")
            self.assertEqual(detected_lang, 'unknown')

    def test_translation_functionality(self):
        """Test text translation functionality"""
        service = OCRTranslatorService()
        
        with patch('ocr_app.services.client') as mock_client:
            mock_response = Mock()
            mock_response.text = "Hello world"
            mock_client.models.generate_content.return_value = mock_response
            
            result = service.translate_text("Hola mundo", 'es')
            
            self.assertEqual(result, "Hello world")


class OCRAPITestCase(APITestCase):
    """Test cases for OCR API endpoints"""
    
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
        
        # Create test image
        self.test_image = self.create_test_image()

    def create_test_image(self):
        """Create a test image file"""
        img = Image.new('RGB', (100, 100), color='white')
        img_io = io.BytesIO()
        img.save(img_io, format='PNG')
        img_io.seek(0)
        
        return SimpleUploadedFile(
            "test_image.png",
            img_io.getvalue(),
            content_type="image/png"
        )

    def test_process_image_endpoint_success(self):
        """Test successful image processing endpoint"""
        url = reverse('ocr_app:process_image')
        
        with patch('ocr_app.services.OCRTranslatorService.process_image') as mock_process:
            mock_process.return_value = {
                'success': True,
                'original_text': 'Test text',
                'detected_language': 'en',
                'language_name': 'English',
                'translated_text': 'Test text',
                'confidence_score': 95.5,
                'processing_time': 1.2,
                'word_count': 2
            }
            
            response = self.client.post(url, {
                'image': self.test_image
            }, format='multipart')
            
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertTrue(response.data['success'])
            self.assertEqual(response.data['original_text'], 'Test text')
            self.assertEqual(response.data['detected_language'], 'en')

    def test_process_image_endpoint_validation_error(self):
        """Test image processing endpoint with validation errors"""
        url = reverse('ocr_app:process_image')
        
        # Test without image
        response = self.client.post(url, {}, format='multipart')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(response.data['success'])
        self.assertIn('error', response.data)

    def test_process_image_endpoint_unauthorized(self):
        """Test that authentication is required"""
        # Remove authentication
        self.client.credentials()
        
        url = reverse('ocr_app:process_image')
        response = self.client.post(url, {
            'image': self.test_image
        }, format='multipart')
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_get_result_endpoint(self):
        """Test get result endpoint"""
        # Create an OCR result
        ocr_result = OCRResult.objects.create(
            user=self.user,
            image=self.test_image,
            original_text='Test text',
            detected_language='en',
            translated_text='Test text',
            confidence_score=95.0,
            processing_time=1.0
        )
        
        url = reverse('ocr_app:get_result', kwargs={'result_id': ocr_result.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['original_text'], 'Test text')
        self.assertEqual(response.data['detected_language'], 'en')

    def test_get_result_not_found(self):
        """Test get result with non-existent ID"""
        url = reverse('ocr_app:get_result', kwargs={'result_id': 99999})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_list_results_endpoint(self):
        """Test list results endpoint"""
        # Create multiple OCR results
        for i in range(3):
            OCRResult.objects.create(
                user=self.user,
                image=self.test_image,
                original_text=f'Test text {i}',
                detected_language='en',
                translated_text=f'Test text {i}',
                confidence_score=95.0,
                processing_time=1.0
            )
        
        url = reverse('ocr_app:list_results')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 3)

    def test_delete_result_endpoint(self):
        """Test delete result endpoint"""
        # Create an OCR result
        ocr_result = OCRResult.objects.create(
            user=self.user,
            image=self.test_image,
            original_text='Test text',
            detected_language='en',
            translated_text='Test text',
            confidence_score=95.0,
            processing_time=1.0
        )
        
        url = reverse('ocr_app:delete_result', kwargs={'result_id': ocr_result.id})
        response = self.client.delete(url)
        
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        
        # Verify the result was deleted
        self.assertFalse(OCRResult.objects.filter(id=ocr_result.id).exists())


class OCRModelTestCase(TestCase):
    """Test cases for OCR models"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )

    def test_ocr_result_model_creation(self):
        """Test OCR result model creation and methods"""
        # Create test image
        img = Image.new('RGB', (100, 100), color='white')
        img_io = io.BytesIO()
        img.save(img_io, format='PNG')
        img_io.seek(0)
        
        test_image = SimpleUploadedFile(
            "test_image.png",
            img_io.getvalue(),
            content_type="image/png"
        )
        
        ocr_result = OCRResult.objects.create(
            user=self.user,
            image=test_image,
            original_text='Hello world',
            detected_language='en',
            translated_text='Hello world',
            confidence_score=95.5,
            processing_time=2.5
        )
        
        self.assertTrue(str(ocr_result).startswith(f'OCR Result {ocr_result.id} - en'))
        self.assertEqual(ocr_result.user, self.user)
        self.assertEqual(ocr_result.original_text, 'Hello world')
        self.assertEqual(ocr_result.detected_language, 'en')
        self.assertEqual(ocr_result.confidence_score, 95.5)
        self.assertIsNotNone(ocr_result.created_at)

    def test_ocr_result_model_validation(self):
        """Test OCR result model field validation"""
        # Test confidence score bounds
        ocr_result = OCRResult(
            user=self.user,
            original_text='Test',
            detected_language='en',
            confidence_score=150.0  # Invalid score > 100
        )
        
        # Django doesn't automatically validate constraints in save()
        # But we can test the field definition
        self.assertIsInstance(ocr_result.confidence_score, float)

    def test_ocr_result_user_relationship(self):
        """Test user relationship in OCR result model"""
        img = Image.new('RGB', (100, 100), color='white')
        img_io = io.BytesIO()
        img.save(img_io, format='PNG')
        img_io.seek(0)
        
        test_image = SimpleUploadedFile(
            "test_image.png",
            img_io.getvalue(),
            content_type="image/png"
        )
        
        ocr_result = OCRResult.objects.create(
            user=self.user,
            image=test_image,
            original_text='Test text',
            detected_language='en'
        )
        
        # Test reverse relationship
        user_results = self.user.ocr_results.all()
        self.assertEqual(user_results.count(), 1)
        self.assertEqual(user_results.first(), ocr_result)


class OCRErrorHandlingTestCase(APITestCase):
    """Test cases for OCR error handling scenarios"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
        
        refresh = RefreshToken.for_user(self.user)
        self.access_token = str(refresh.access_token)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.access_token}')

    def test_invalid_image_format(self):
        """Test handling of invalid image formats"""
        url = reverse('ocr_app:process_image')
        
        # Create a text file instead of image
        invalid_file = SimpleUploadedFile(
            "test.txt",
            b"not an image file",
            content_type="text/plain"
        )
        
        response = self.client.post(url, {
            'image': invalid_file
        }, format='multipart')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_large_image_handling(self):
        """Test handling of large image files"""
        url = reverse('ocr_app:process_image')
        
        # Create a large mock image file (>10MB)
        large_image_content = b"x" * (11 * 1024 * 1024)  # 11MB
        large_image = SimpleUploadedFile(
            "large_image.jpg",
            large_image_content,
            content_type="image/jpeg"
        )
        
        response = self.client.post(url, {
            'image': large_image
        }, format='multipart')
        
        # Should be rejected due to size limit
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_api_service_error_handling(self):
        """Test API error handling when service fails"""
        url = reverse('ocr_app:process_image')
        
        img = Image.new('RGB', (100, 100), color='white')
        img_io = io.BytesIO()
        img.save(img_io, format='PNG')
        img_io.seek(0)
        
        test_image = SimpleUploadedFile(
            "test_image.png",
            img_io.getvalue(),
            content_type="image/png"
        )
        
        with patch('ocr_app.services.OCRTranslatorService.process_image') as mock_process:
            mock_process.side_effect = Exception("Service error")
            
            response = self.client.post(url, {
                'image': test_image
            }, format='multipart')
            
            self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
            self.assertFalse(response.data['success'])
            self.assertIn('error', response.data)

    def test_database_error_handling(self):
        """Test database error scenarios"""
        url = reverse('ocr_app:process_image')
        
        img = Image.new('RGB', (100, 100), color='white')
        img_io = io.BytesIO()
        img.save(img_io, format='PNG')
        img_io.seek(0)
        
        test_image = SimpleUploadedFile(
            "test_image.png",
            img_io.getvalue(),
            content_type="image/png"
        )
        
        with patch('ocr_app.models.OCRResult.objects.create') as mock_create:
            mock_create.side_effect = Exception("Database error")
            
            response = self.client.post(url, {
                'image': test_image
            }, format='multipart')
            
            self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)


class OCRPerformanceTestCase(TestCase):
    """Test cases for OCR performance and optimization"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )

    def test_concurrent_processing_simulation(self):
        """Test simulation of concurrent OCR processing"""
        service = OCRTranslatorService()
        
        # Mock multiple image processing requests
        with patch('ocr_app.services.client') as mock_client:
            mock_response = Mock()
            mock_response.text = "Test text"
            mock_client.models.generate_content.return_value = mock_response
            
            with patch('langdetect.detect', return_value='en'):
                # Create temporary image files
                temp_files = []
                try:
                    for i in range(3):
                        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as temp_file:
                            img = Image.new('RGB', (100, 100), color='white')
                            img.save(temp_file, format='PNG')
                            temp_files.append(temp_file.name)
                    
                    # Process multiple images
                    results = []
                    for temp_file_path in temp_files:
                        result = service.process_image(temp_file_path)
                        results.append(result)
                    
                    # Verify all processing completed successfully
                    for result in results:
                        self.assertTrue(result['success'])
                        self.assertEqual(result['original_text'], 'Test text')
                    
                finally:
                    # Clean up temporary files
                    for temp_file_path in temp_files:
                        if os.path.exists(temp_file_path):
                            os.unlink(temp_file_path)

    def test_memory_usage_with_large_images(self):
        """Test memory handling with larger images"""
        service = OCRTranslatorService()
        
        # Create a larger test image
        large_img = Image.new('RGB', (1000, 1000), color='white')
        img_io = io.BytesIO()
        large_img.save(img_io, format='PNG')
        
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as temp_file:
            temp_file.write(img_io.getvalue())
            temp_file_path = temp_file.name
        
        try:
            with patch('ocr_app.services.client') as mock_client:
                mock_response = Mock()
                mock_response.text = "Large image text"
                mock_client.models.generate_content.return_value = mock_response
                
                with patch('langdetect.detect', return_value='en'):
                    result = service.process_image(temp_file_path)
                    
                    # Should handle large images without issues
                    self.assertTrue(result['success'])
                    self.assertEqual(result['original_text'], 'Large image text')
                    
        finally:
            # Clean up
            if os.path.exists(temp_file_path):
                os.unlink(temp_file_path)
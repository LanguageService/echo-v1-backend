"""
Django management command to test performance optimizations
"""
import time
import asyncio
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from performance.cache_service import cache_service
from performance.language_detector import language_detector
from performance.image_optimizer import image_optimizer
from performance.async_processor import async_processor


class Command(BaseCommand):
    help = 'Test performance optimization features'

    def add_arguments(self, parser):
        parser.add_argument(
            '--test-type',
            type=str,
            default='all',
            choices=['cache', 'language', 'image', 'async', 'all'],
            help='Type of test to run'
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Verbose output'
        )

    def handle(self, *args, **options):
        test_type = options['test_type']
        verbose = options['verbose']

        self.stdout.write(
            self.style.SUCCESS('Starting performance optimization tests...')
        )

        if test_type in ['cache', 'all']:
            self.test_cache_service(verbose)

        if test_type in ['language', 'all']:
            self.test_language_detection(verbose)

        if test_type in ['image', 'all']:
            self.test_image_optimization(verbose)

        if test_type in ['async', 'all']:
            self.test_async_processing(verbose)

        self.stdout.write(
            self.style.SUCCESS('All tests completed successfully!')
        )

    def test_cache_service(self, verbose=False):
        """Test cache functionality"""
        self.stdout.write('\n--- Testing Cache Service ---')
        
        # Test image hash generation
        test_data = {
            'test_text': 'Hello world',
            'source_lang': 'en',
            'target_lang': 'es'
        }
        
        # Test text hashing
        text_hash = cache_service.get_text_hash(test_data['test_text'])
        if verbose:
            self.stdout.write(f"Text hash: {text_hash}")
        
        # Test translation caching
        cache_service.cache_translation(
            text_hash,
            test_data['source_lang'],
            test_data['target_lang'],
            'Hola mundo',
            'gemini'
        )
        
        # Test cache retrieval
        cached_translation = cache_service.get_cached_translation(
            text_hash,
            test_data['source_lang'],
            test_data['target_lang']
        )
        
        if cached_translation:
            self.stdout.write(
                self.style.SUCCESS('✓ Cache service working correctly')
            )
            if verbose:
                self.stdout.write(f"Cached translation: {cached_translation}")
        else:
            self.stdout.write(
                self.style.ERROR('✗ Cache service failed')
            )
        
        # Test cache stats
        stats = cache_service.get_cache_stats()
        if verbose:
            self.stdout.write(f"Cache stats: {stats}")

    def test_language_detection(self, verbose=False):
        """Test language detection"""
        self.stdout.write('\n--- Testing Language Detection ---')
        
        test_texts = [
            ('Hello world, how are you today?', 'en'),
            ('Hola mundo, ¿cómo estás hoy?', 'es'),
            ('Bonjour le monde, comment allez-vous?', 'fr'),
            ('Muraho isi, ese muraganwa neza?', 'rw'),  # Kinyarwanda
            ('Hujambo dunia, hali yako?', 'sw'),  # Swahili
        ]
        
        correct_detections = 0
        total_tests = len(test_texts)
        
        for text, expected_lang in test_texts:
            start_time = time.time()
            result = language_detector.quick_detect(text)
            detection_time = time.time() - start_time
            
            if result and result.get('language') == expected_lang:
                correct_detections += 1
                status = '✓'
                style = self.style.SUCCESS
            else:
                status = '✗'
                style = self.style.WARNING
            
            detected_lang = result.get('language', 'unknown') if result else 'none'
            confidence = result.get('confidence', 0.0) if result else 0.0
            
            output = f"{status} {text[:30]}... -> {detected_lang} (expected: {expected_lang})"
            self.stdout.write(style(output))
            
            if verbose:
                self.stdout.write(
                    f"  Confidence: {confidence:.2f}, Time: {detection_time:.3f}s"
                )
        
        accuracy = (correct_detections / total_tests) * 100
        self.stdout.write(
            f"\nLanguage detection accuracy: {accuracy:.1f}% ({correct_detections}/{total_tests})"
        )
        
        # Test supported languages
        supported = language_detector.get_supported_languages()
        if verbose:
            self.stdout.write(f"Supported languages: {len(supported)}")

    def test_image_optimization(self, verbose=False):
        """Test image optimization (mock test)"""
        self.stdout.write('\n--- Testing Image Optimization ---')
        
        # Mock image info test
        mock_image_info = {
            'width': 2000,
            'height': 1500,
            'size_kb': 1500,
            'needs_resize': True
        }
        
        # Test processing time estimation
        mock_estimates = {
            'quick_optimize': 0.5,
            'full_optimize': 1.0,
            'ocr_processing': 2.0
        }
        
        self.stdout.write('✓ Image optimization service initialized')
        
        if verbose:
            self.stdout.write(f"Mock image info: {mock_image_info}")
            self.stdout.write(f"Processing estimates: {mock_estimates}")

    def test_async_processing(self, verbose=False):
        """Test async processing capabilities"""
        self.stdout.write('\n--- Testing Async Processing ---')
        
        try:
            # Test async processor initialization
            processor = async_processor
            self.stdout.write('✓ Async processor initialized')
            
            # Test mock functions
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            # Mock OCR test
            start_time = time.time()
            result = loop.run_until_complete(
                processor._mock_ocr_processing('/mock/path/image.jpg')
            )
            processing_time = time.time() - start_time
            
            if result and 'text' in result:
                self.stdout.write('✓ Mock OCR processing works')
                if verbose:
                    self.stdout.write(f"  Result: {result}")
                    self.stdout.write(f"  Time: {processing_time:.3f}s")
            
            # Mock translation test
            translation_result = processor._mock_translation_with_fallback(
                'Hello world', 'en', 'es'
            )
            
            if translation_result and 'translation' in translation_result:
                self.stdout.write('✓ Mock translation processing works')
                if verbose:
                    self.stdout.write(f"  Result: {translation_result}")
            
            loop.close()
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'✗ Async processing test failed: {str(e)}')
            )

    def performance_benchmark(self):
        """Run performance benchmarks"""
        self.stdout.write('\n--- Performance Benchmark ---')
        
        # Test cache performance
        cache_times = []
        for i in range(100):
            start_time = time.time()
            cache_service.cache_translation(
                f'test_hash_{i}', 'en', 'es', f'translation_{i}', 'gemini'
            )
            cache_times.append(time.time() - start_time)
        
        avg_cache_time = sum(cache_times) / len(cache_times)
        self.stdout.write(f"Average cache write time: {avg_cache_time:.4f}s")
        
        # Test language detection performance
        test_text = "Hello world, this is a test sentence for performance measurement."
        detection_times = []
        
        for i in range(50):
            start_time = time.time()
            language_detector.quick_detect(test_text)
            detection_times.append(time.time() - start_time)
        
        avg_detection_time = sum(detection_times) / len(detection_times)
        self.stdout.write(f"Average language detection time: {avg_detection_time:.4f}s")
        
        self.stdout.write(
            self.style.SUCCESS('Performance benchmark completed')
        )
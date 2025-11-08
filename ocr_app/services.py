"""
OCR and Translation Services Module

This module provides comprehensive image processing, text extraction, 
language detection, and translation services using Gemini Vision API,
and Google Translate APIs.
"""

import os
import logging
import time
import base64
import mimetypes
from typing import Dict, Tuple, Optional, Any
from google import genai
from google.genai import types
from langdetect import detect, DetectorFactory
from .translation_manager import translation_manager
from .translation_services import TranslationProvider
from decouple import config

# Set seed for consistent language detection results
DetectorFactory.seed = 0

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Gemini client
client = genai.Client(api_key=config("GEMINI_API_KEY",""))


class GeminiVisionProcessor:
    """Handles text extraction from images using Gemini Vision API"""
    
    def __init__(self):
        self.model = "gemini-2.5-flash"
    
    def extract_text(self, image_path: str) -> Dict[str, Any]:
        """
        Extract text from image using Gemini Vision API
        
        Args:
            image_path: Path to the image file
            
        Returns:
            Dictionary containing extracted text and confidence score
        """
        try:
            # Read and encode image
            with open(image_path, "rb") as f:
                image_bytes = f.read()
            
            # Auto-detect mime type based on file extension
            mime_type, _ = mimetypes.guess_type(image_path)
            if not mime_type or not mime_type.startswith('image/'):
                # Default to JPEG if can't detect or not an image
                mime_type = "image/jpeg"
            
            logger.info(f"Processing image with detected mime type: {mime_type}")
            
            # Create prompt for text extraction with emphasis on preserving special characters
            prompt = """Extract all text from this image exactly as it appears, preserving ALL special characters, diacritical marks, tone marks, accents, and Unicode characters. This includes but not limited to: áéíóú, àèìòù, âêîôû, ãẽĩõũ, ąęįųō, ñç, ş, ğ, and any tonal marks or linguistic symbols. Return only the extracted text without any commentary, explanations, or formatting. If there is no text in the image, return an empty string."""
            
            # Process image with Gemini
            response = client.models.generate_content(
                model=self.model,
                contents=[
                    types.Part.from_bytes(
                        data=image_bytes,
                        mime_type=mime_type,
                    ),
                    prompt
                ],
            )
            
            extracted_text = response.text.strip() if response.text else ""
            
            # Calculate confidence based on response characteristics and text quality
            confidence = self._calculate_ocr_confidence(extracted_text, response)
            
            logger.info(f"Gemini Vision text extraction completed. Text length: {len(extracted_text)}")
            
            return {
                'text': extracted_text,
                'confidence': confidence,
                'word_count': len(extracted_text.split()) if extracted_text else 0
            }
            
        except Exception as e:
            logger.error(f"Error in Gemini Vision text extraction: {str(e)}")
            raise
    
    def _calculate_ocr_confidence(self, extracted_text: str, response) -> float:
        """Calculate OCR confidence based on text quality indicators"""
        if not extracted_text:
            return 0.0
        
        base_confidence = 75.0
        
        # Text length indicator (longer coherent text suggests better detection)
        text_length = len(extracted_text.strip())
        if text_length > 100:
            base_confidence += 15.0
        elif text_length > 50:
            base_confidence += 10.0
        elif text_length > 20:
            base_confidence += 5.0
        elif text_length < 5:
            base_confidence -= 20.0
        
        # Word count and structure
        words = extracted_text.split()
        word_count = len(words)
        if word_count > 20:
            base_confidence += 10.0
        elif word_count > 10:
            base_confidence += 5.0
        elif word_count < 3:
            base_confidence -= 15.0
        
        # Character diversity (more diverse characters suggest real text)
        unique_chars = len(set(extracted_text.lower()))
        if unique_chars > 15:
            base_confidence += 8.0
        elif unique_chars > 10:
            base_confidence += 4.0
        elif unique_chars < 5:
            base_confidence -= 10.0
        
        # Check for common OCR errors or artifacts
        if extracted_text.count('|') > text_length * 0.1:  # Too many pipe characters
            base_confidence -= 15.0
        if extracted_text.count('1') > text_length * 0.3:  # Too many 1s (common OCR error)
            base_confidence -= 10.0
        
        # Check for sentence structure (periods, proper capitalization)
        if '.' in extracted_text and any(word[0].isupper() for word in words if word):
            base_confidence += 8.0
        
        # Ensure confidence is in valid range
        return min(95.0, max(15.0, base_confidence))


class GeminiLanguageDetector:
    """Handles language detection using Google Gemini AI for superior accuracy"""
    
    def __init__(self):
        self.model = "gemini-2.5-flash"
    
    def detect_language(self, text: str) -> Dict[str, Any]:
        """
        Detect language of the given text using Gemini AI with enhanced accuracy
        
        Args:
            text: Text to analyze
            
        Returns:
            Dictionary containing detected language and confidence
        """
        try:
            if not text or len(text.strip()) < 3:
                return {
                    'language': 'unknown',
                    'language_name': 'Unknown',
                    'confidence': 0.0
                }
            
            # Clean text for better detection
            cleaned_text = text.strip()
            
            # Create prompt for Gemini AI language detection with special character awareness
            prompt = f"""Identify the language of the following text, paying attention to special characters, diacritical marks, and tone marks which are important linguistic indicators. Return only the ISO 639-1 language code (2 letters like 'en', 'fr', 'rw', 'yo', etc.) without any additional text or explanation:

{cleaned_text}"""
            
            # Use Gemini AI for language detection
            response = client.models.generate_content(
                model=self.model,
                contents=prompt
            )
            
            detected_lang = response.text.strip().lower() if response.text else ""
            
            # Validate the response is a valid language code
            if not detected_lang or len(detected_lang) != 2 or not detected_lang.isalpha():
                # Fallback to langdetect library if Gemini response is invalid
                logger.warning(f"Invalid Gemini language detection response: '{detected_lang}', falling back to langdetect")
                try:
                    detected_lang = detect(cleaned_text)
                except Exception:
                    detected_lang = 'en'
            
            # Extended language code to name mapping
            lang_names = {
                'en': 'English', 'es': 'Spanish', 'fr': 'French', 'de': 'German',
                'it': 'Italian', 'pt': 'Portuguese', 'ru': 'Russian', 'ja': 'Japanese',
                'ko': 'Korean', 'zh': 'Chinese', 'ar': 'Arabic', 'hi': 'Hindi',
                'th': 'Thai', 'vi': 'Vietnamese', 'nl': 'Dutch', 'pl': 'Polish',
                'tr': 'Turkish', 'sv': 'Swedish', 'da': 'Danish', 'no': 'Norwegian',
                'fi': 'Finnish', 'hu': 'Hungarian', 'cs': 'Czech', 'sk': 'Slovak',
                'bg': 'Bulgarian', 'hr': 'Croatian', 'sr': 'Serbian', 'sl': 'Slovenian',
                'et': 'Estonian', 'lv': 'Latvian', 'lt': 'Lithuanian', 'ro': 'Romanian',
                'el': 'Greek', 'he': 'Hebrew', 'fa': 'Persian', 'ur': 'Urdu',
                'bn': 'Bengali', 'ta': 'Tamil', 'te': 'Telugu', 'ml': 'Malayalam',
                'kn': 'Kannada', 'gu': 'Gujarati', 'mr': 'Marathi', 'ne': 'Nepali',
                'si': 'Sinhala', 'my': 'Myanmar', 'km': 'Khmer', 'lo': 'Lao',
                'ka': 'Georgian', 'am': 'Amharic', 'is': 'Icelandic', 'mt': 'Maltese',
                'cy': 'Welsh', 'ga': 'Irish', 'eu': 'Basque', 'ca': 'Catalan',
                'gl': 'Galician', 'af': 'Afrikaans', 'sw': 'Swahili', 'zu': 'Zulu',
                'xh': 'Xhosa', 'st': 'Sesotho', 'tn': 'Setswana', 'ss': 'Siswati',
                'rw': 'Kinyarwanda', 'lg': 'Luganda', 'yo': 'Yoruba', 'ig': 'Igbo',
                'ha': 'Hausa', 'so': 'Somali', 'om': 'Oromo', 'ti': 'Tigrinya',
                'wo': 'Wolof', 'ff': 'Fulah', 'ln': 'Lingala', 'kg': 'Kongo',
                'ny': 'Chichewa', 'sn': 'Shona', 'nd': 'Ndebele', 'mg': 'Malagasy'
            }
            
            language_name = lang_names.get(detected_lang, detected_lang.capitalize())
            
            # Calculate confidence based on detection quality
            confidence = self._calculate_language_confidence(cleaned_text, detected_lang, True)
            
            logger.info(f"Gemini AI language detected: {language_name} ({detected_lang}) with confidence {confidence}")
            
            return {
                'language': detected_lang,
                'language_name': language_name,
                'confidence': confidence
            }
            
        except Exception as e:
            logger.error(f"Error in Gemini AI language detection: {str(e)}")
            # Fallback to langdetect library
            try:
                detected_lang = detect(text.strip())
                lang_names = {
                    'en': 'English', 'es': 'Spanish', 'fr': 'French', 'de': 'German',
                    'it': 'Italian', 'pt': 'Portuguese', 'ru': 'Russian', 'ja': 'Japanese',
                    'rw': 'Kinyarwanda', 'sw': 'Swahili', 'so': 'Somali'
                }
                language_name = lang_names.get(detected_lang, detected_lang.capitalize())
                
                return {
                    'language': detected_lang,
                    'language_name': language_name,
                    'confidence': self._calculate_language_confidence(text.strip(), detected_lang, False)
                }
            except Exception:
                return {
                    'language': 'en',
                    'language_name': 'English',
                    'confidence': 0.3  # Low confidence for final fallback
                }
    
    def _calculate_language_confidence(self, text: str, detected_lang: str, is_gemini: bool) -> float:
        """Calculate language detection confidence based on text characteristics and detection method"""
        if not text or not detected_lang:
            return 0.0
        
        # Base confidence varies by detection method
        base_confidence = 88.0 if is_gemini else 75.0
        
        # Text length factor (longer text gives more reliable detection)
        text_length = len(text.strip())
        if text_length > 200:
            base_confidence += 10.0
        elif text_length > 100:
            base_confidence += 6.0
        elif text_length > 50:
            base_confidence += 3.0
        elif text_length < 20:
            base_confidence -= 15.0
        elif text_length < 10:
            base_confidence -= 25.0
        
        # Word count factor
        words = text.split()
        word_count = len(words)
        if word_count > 30:
            base_confidence += 8.0
        elif word_count > 15:
            base_confidence += 4.0
        elif word_count < 5:
            base_confidence -= 12.0
        
        # Language-specific character patterns
        # Check for language-specific characteristics
        if detected_lang == 'rw':  # Kinyarwanda
            kinyarwanda_words = ['mu', 'ku', 'n', 'ni', 'nk', 'ubwoba', 'mwiza', 'uyu']
            if any(word in text.lower() for word in kinyarwanda_words):
                base_confidence += 8.0
        elif detected_lang == 'sw':  # Swahili
            swahili_words = ['na', 'ya', 'wa', 'ni', 'hali', 'siku', 'pamoja']
            if any(word in text.lower() for word in swahili_words):
                base_confidence += 8.0
        elif detected_lang == 'yo':  # Yoruba
            yoruba_words = ['ati', 'ni', 'won', 'o', 'je', 'fun', 'ti']
            if any(word in text.lower() for word in yoruba_words):
                base_confidence += 8.0
        elif detected_lang == 'ha':  # Hausa
            hausa_words = ['da', 'na', 'ya', 'za', 'sun', 'an', 'ko']
            if any(word in text.lower() for word in hausa_words):
                base_confidence += 8.0
        
        # Check for special characters that are language-specific
        if any(char in text for char in 'àáèéìíòóùúñç'):  # Romance languages
            if detected_lang in ['es', 'fr', 'pt', 'it']:
                base_confidence += 6.0
        
        # Check for language scripts
        if any(ord(char) > 127 for char in text):  # Non-ASCII characters
            base_confidence += 4.0
        
        # Character diversity (more diverse suggests real language)
        unique_chars = len(set(text.lower()))
        if unique_chars > 20:
            base_confidence += 5.0
        elif unique_chars < 8:
            base_confidence -= 8.0
        
        return min(95.0, max(30.0, base_confidence))


class GeminiTranslator:
    """Handles text translation using Google Gemini AI"""
    
    def __init__(self):
        self.model = "gemini-2.5-flash"
    
    def translate_to_english(self, text: str, source_lang: str = None) -> Dict[str, Any]:
        """
        Translate text to English using Google Gemini AI with auto-detection
        
        Args:
            text: Text to translate
            source_lang: Source language code (optional, will auto-detect if None)
            
        Returns:
            Dictionary containing translated text and metadata
        """
        try:
            if not text or len(text.strip()) == 0:
                return {
                    'translated_text': '',
                    'source_language': source_lang or 'unknown',
                    'target_language': 'en',
                    'success': False,
                    'error': 'No text to translate'
                }
            
            # Auto-detect source language if not provided
            if not source_lang or source_lang == 'unknown':
                try:
                    auto_detected = detect(text.strip())
                    source_lang = auto_detected
                    logger.info(f"Auto-detected source language for translation: {source_lang}")
                except Exception:
                    source_lang = 'auto'
                    logger.info("Will use Gemini AI for language auto-detection")
            
            # Skip translation if text is already in English
            if source_lang == 'en':
                return {
                    'translated_text': text,
                    'source_language': 'en',
                    'target_language': 'en',
                    'success': True,
                    'note': 'Text is already in English'
                }
            
            # Create translation prompt for Gemini with full translation
            if source_lang and source_lang != 'auto':
                prompt = f"""Translate the following text from {source_lang} to English. Translate ALL words including names and proper nouns to their English meanings. If a name has a specific meaning (like Yoruba names often do), provide the English translation of that meaning. Return only the translated text without any additional commentary, explanations, or formatting:

{text}"""
            else:
                prompt = f"""Detect the language of the following text and translate it to English. Translate ALL words including names and proper nouns to their English meanings. If a name has a specific meaning, provide the English translation of that meaning. Return only the translated English text without any additional commentary, explanations, or formatting:

{text}"""
            
            # Perform translation with Gemini AI
            response = client.models.generate_content(
                model=self.model,
                contents=prompt
            )
            
            translated_text = response.text.strip() if response.text else ""
            
            if not translated_text:
                raise ValueError("Empty response from Gemini translation")
            
            logger.info(f"Gemini AI translation completed: {source_lang} -> en")
            
            return {
                'translated_text': translated_text,
                'source_language': source_lang,
                'target_language': 'en',
                'success': True
            }
            
        except Exception as e:
            logger.error(f"Error in Gemini AI translation: {str(e)}")
            return {
                'translated_text': '',
                'source_language': source_lang or 'unknown',
                'target_language': 'en',
                'success': False,
                'error': str(e)
            }


class OCRTranslatorService:
    """Main service class that orchestrates the entire OCR and translation process"""
    
    def __init__(self, preferred_translation_service: TranslationProvider = None):
        self.vision_processor = GeminiVisionProcessor()
        self.language_detector = GeminiLanguageDetector()
        self.translator = GeminiTranslator()  # Keep for backward compatibility
        self.preferred_translation_service = preferred_translation_service
    
    def process_image(self, image_path: str, user=None, ocr_result_instance=None) -> Dict[str, Any]:
        """
        Complete image processing pipeline: OCR -> Language Detection -> Translation
        
        Args:
            image_path: Path to the image file
            
        Returns:
            Dictionary containing all processing results
        """
        start_time = time.time()
        
        try:
            # Initialize result structure
            result = {
                'success': False,
                'original_text': '',
                'detected_language': 'unknown',
                'language_name': 'Unknown',
                'translated_text': '',
                'confidence_score': 0.0,
                'processing_time': 0.0,
                'word_count': 0,
                'error_message': None
            }
            
            # Step 1: Extract text using Gemini Vision
            logger.info("Extracting text from image using Gemini Vision...")
            ocr_result = self.vision_processor.extract_text(image_path)
            
            result['original_text'] = ocr_result['text']
            result['confidence_score'] = ocr_result['confidence']
            result['word_count'] = ocr_result['word_count']
            
            # Check if text was extracted
            if not ocr_result['text']:
                result['error_message'] = "No text detected in the image"
                result['processing_time'] = time.time() - start_time
                return result
            
            # Step 2: Detect language
            logger.info("Detecting language...")
            lang_result = self.language_detector.detect_language(ocr_result['text'])
            
            result['detected_language'] = lang_result['language']
            result['language_name'] = lang_result['language_name']
            
            # Step 3: Translate to English using multiple translation providers
            logger.info("Translating text using multiple translation services...")
            
            # Use the new translation manager with fallback
            translation_result = translation_manager.translate_with_fallback(
                text=ocr_result['text'],
                target_language='en',
                source_language=lang_result['language'],
                preferred_service=self.preferred_translation_service,
                user=user,
                ocr_result=ocr_result_instance
            )
            
            if translation_result.success:
                result['translated_text'] = translation_result.translated_text
                result['confidence_score'] = max(result['confidence_score'], translation_result.confidence_score)
                result['success'] = True
                result['translation_provider'] = translation_result.provider.value
                logger.info(f"Translation successful using {translation_result.provider.value}")
            else:
                # Fallback to legacy translator if all services fail
                logger.warning("All translation services failed, trying legacy translator...")
                legacy_result = self.translator.translate_to_english(
                    ocr_result['text'], 
                    lang_result['language']
                )
                
                if legacy_result['success']:
                    result['translated_text'] = legacy_result['translated_text']
                    result['success'] = True
                    result['translation_provider'] = 'gemini_legacy'
                else:
                    result['error_message'] = f"Translation failed: {translation_result.error_message}"
            
            # Calculate processing time
            result['processing_time'] = time.time() - start_time
            
            logger.info(f"Processing completed successfully in {result['processing_time']:.2f} seconds")
            
            return result
            
        except Exception as e:
            error_msg = f"Error in OCR processing pipeline: {str(e)}"
            logger.error(error_msg)
            
            return {
                'success': False,
                'original_text': '',
                'detected_language': 'unknown',
                'language_name': 'Unknown',
                'translated_text': '',
                'confidence_score': 0.0,
                'processing_time': time.time() - start_time,
                'word_count': 0,
                'error_message': error_msg
            }


# Convenience function for direct usage
def process_image_file(image_path: str) -> Dict[str, Any]:
    """
    Convenience function to process an image file through the complete pipeline
    
    Args:
        image_path: Path to the image file
        
    Returns:
        Processing results dictionary
    """
    service = OCRTranslatorService()
    return service.process_image(image_path)


# Example usage and testing function
def main():
    """Example usage of the OCR Translation Service"""
    if len(sys.argv) != 2:
        print("Usage: python services.py <image_path>")
        return
    
    image_path = sys.argv[1]
    
    if not os.path.exists(image_path):
        print(f"Error: Image file '{image_path}' not found")
        return
    
    print("Processing image...")
    result = process_image_file(image_path)
    
    print("\n" + "="*50)
    print("OCR TRANSLATION RESULTS")
    print("="*50)
    
    if result['success']:
        print(f"Original Text: {result['original_text']}")
        print(f"Detected Language: {result['language_name']} ({result['detected_language']})")
        print(f"Translated Text: {result['translated_text']}")
        print(f"Confidence Score: {result['confidence_score']:.2f}%")
        print(f"Word Count: {result['word_count']}")
        print(f"Processing Time: {result['processing_time']:.2f} seconds")
    else:
        print(f"Processing failed: {result['error_message']}")


if __name__ == "__main__":
    import sys
    main()

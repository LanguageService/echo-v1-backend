"""
Smart language detection with pattern matching and caching
"""
import re
from typing import Optional, Dict, Any, List
from .cache_service import cache_service


class SmartLanguageDetector:
    """Fast pattern-based language detection with AI fallback"""
    
    def __init__(self):
        # Common word patterns for quick detection
        self.language_patterns = {
            'en': {
                'words': ['the', 'and', 'to', 'of', 'a', 'in', 'is', 'it', 'you', 'that', 'he', 'was', 'for', 'on', 'are', 'as', 'with', 'his', 'they', 'i'],
                'regex': [r'\b(the|and|to|of|a)\b'],
                'weight': 1.0
            },
            'es': {
                'words': ['el', 'de', 'que', 'y', 'a', 'en', 'un', 'es', 'se', 'no', 'te', 'lo', 'le', 'da', 'su', 'por', 'son', 'con', 'para', 'al'],
                'regex': [r'\b(el|de|que|y|es)\b'],
                'weight': 1.0
            },
            'fr': {
                'words': ['le', 'de', 'et', 'à', 'un', 'il', 'être', 'et', 'en', 'avoir', 'que', 'pour', 'dans', 'ce', 'son', 'une', 'sur', 'avec', 'ne', 'se'],
                'regex': [r'\b(le|de|et|à|un)\b'],
                'weight': 1.0
            },
            'pt': {
                'words': ['o', 'de', 'e', 'do', 'a', 'em', 'um', 'para', 'é', 'com', 'não', 'uma', 'os', 'no', 'se', 'na', 'por', 'mais', 'as', 'dos'],
                'regex': [r'\b(o|de|e|do|a)\b'],
                'weight': 1.0
            },
            'it': {
                'words': ['il', 'di', 'che', 'e', 'la', 'per', 'un', 'in', 'con', 'del', 'da', 'a', 'al', 'dei', 'le', 'si', 'ci', 'non', 'sua', 'loro'],
                'regex': [r'\b(il|di|che|e|la)\b'],
                'weight': 1.0
            },
            'de': {
                'words': ['der', 'die', 'und', 'in', 'den', 'von', 'zu', 'das', 'mit', 'sich', 'des', 'auf', 'für', 'ist', 'im', 'dem', 'nicht', 'ein', 'eine', 'als'],
                'regex': [r'\b(der|die|und|in|den)\b'],
                'weight': 1.0
            },
            # African Languages
            'sw': {  # Swahili
                'words': ['na', 'ya', 'wa', 'ni', 'la', 'za', 'kwa', 'au', 'hii', 'huo', 'ile', 'wao', 'mimi', 'wewe', 'yeye', 'sisi', 'nyinyi', 'kutoka', 'kwenda', 'kuja'],
                'regex': [r'\b(na|ya|wa|ni|la)\b'],
                'weight': 1.2  # Boost African languages
            },
            'rw': {  # Kinyarwanda
                'words': ['mu', 'n', 'ni', 'ku', 'na', 'no', 'ko', 'kandi', 'cyangwa', 'nk', 'uko', 'ubu', 'iki', 'ibi', 'aba', 'uyu', 'iyi', 'iri', 'ayo', 'ariko'],
                'regex': [r'\b(mu|ni|ku|na|ko)\b'],
                'weight': 1.2
            },
            'yo': {  # Yoruba
                'words': ['ni', 'ti', 'si', 'ko', 'bi', 'fi', 'fun', 'naa', 'ati', 'tabi', 'sugbon', 'nitori', 'lati', 'sinu', 'pada', 'wa', 'lo', 'mu', 'gbe', 'je'],
                'regex': [r'\b(ni|ti|si|ko|bi)\b'],
                'weight': 1.2
            },
            'ha': {  # Hausa
                'words': ['da', 'na', 'ya', 'ta', 'ba', 'ko', 'don', 'akan', 'idan', 'wannan', 'waccan', 'su', 'mu', 'ku', 'shi', 'ita', 'mun', 'kun', 'sun', 'an'],
                'regex': [r'\b(da|na|ya|ta|ba)\b'],
                'weight': 1.2
            },
            'ig': {  # Igbo
                'words': ['na', 'nke', 'ka', 'ga', 'ndi', 'ya', 'ha', 'any', 'nwe', 'eme', 'kwuo', 'gaa', 'bia', 'bu', 'ghi', 'unu', 'onye', 'ihe', 'oge', 'ebe'],
                'regex': [r'\b(na|nke|ka|ga|ndi)\b'],
                'weight': 1.2
            },
            'zu': {  # Zulu
                'words': ['ku', 'nga', 'ukuthi', 'uma', 'noma', 'kodwa', 'futhi', 'ngo', 'kwa', 'e', 'la', 'le', 'lo', 'aba', 'ama', 'imi', 'izi', 'ubu', 'uku', 'ulu'],
                'regex': [r'\b(ku|nga|uma|noma|kodwa)\b'],
                'weight': 1.2
            }
        }
        
        # Character patterns for additional detection
        self.char_patterns = {
            'zh': [r'[\u4e00-\u9fff]'],  # Chinese characters
            'ar': [r'[\u0600-\u06ff]'],  # Arabic script
            'ru': [r'[\u0400-\u04ff]'],  # Cyrillic script
            'ja': [r'[\u3040-\u309f\u30a0-\u30ff]'],  # Hiragana, Katakana
            'ko': [r'[\uac00-\ud7af]'],  # Hangul
        }
    
    def quick_detect(self, text: str, min_confidence: float = 0.3) -> Optional[Dict[str, Any]]:
        """Fast pattern-based detection before AI call"""
        if not text or len(text.strip()) < 10:
            return None
            
        # Check cache first
        text_hash = cache_service.get_text_hash(text)
        cached_result = cache_service.get_cached_language_detection(text_hash)
        if cached_result:
            return cached_result
        
        text_lower = text.lower()
        words = re.findall(r'\b\w+\b', text_lower)
        
        if len(words) < 3:
            return None
        
        # Sample first 20 words for efficiency
        sample_words = words[:20]
        scores = {}
        
        # Check character patterns first
        for lang, patterns in self.char_patterns.items():
            for pattern in patterns:
                if re.search(pattern, text):
                    scores[lang] = scores.get(lang, 0) + 5  # High score for character match
        
        # Check word patterns
        for lang, lang_data in self.language_patterns.items():
            lang_words = lang_data['words']
            weight = lang_data.get('weight', 1.0)
            score = 0
            
            # Count word matches
            for word in sample_words:
                if word in lang_words:
                    score += weight
            
            # Check regex patterns
            for pattern in lang_data.get('regex', []):
                matches = len(re.findall(pattern, text_lower))
                score += matches * weight
            
            if score > 0:
                scores[lang] = score
        
        if not scores:
            return None
        
        # Calculate confidence
        total_words = len(sample_words)
        best_lang = max(scores, key=scores.get)
        best_score = scores[best_lang]
        confidence = min(best_score / total_words, 1.0)
        
        if confidence >= min_confidence:
            result = {
                'language': best_lang,
                'confidence': confidence,
                'method': 'pattern_matching',
                'cached': False
            }
            
            # Cache the result
            cache_service.cache_language_detection(text_hash, best_lang, confidence)
            return result
        
        return None
    
    def get_supported_languages(self) -> List[Dict[str, Any]]:
        """Get list of languages supported by quick detection"""
        languages = []
        
        lang_names = {
            'en': 'English',
            'es': 'Spanish',
            'fr': 'French',
            'pt': 'Portuguese', 
            'it': 'Italian',
            'de': 'German',
            'sw': 'Swahili',
            'rw': 'Kinyarwanda',
            'yo': 'Yoruba',
            'ha': 'Hausa',
            'ig': 'Igbo',
            'zu': 'Zulu',
            'zh': 'Chinese',
            'ar': 'Arabic',
            'ru': 'Russian',
            'ja': 'Japanese',
            'ko': 'Korean'
        }
        
        for code, data in self.language_patterns.items():
            languages.append({
                'code': code,
                'name': lang_names.get(code, code.upper()),
                'detection_method': 'pattern_matching',
                'confidence_boost': data.get('weight', 1.0)
            })
        
        for code in self.char_patterns.keys():
            if code not in [lang['code'] for lang in languages]:
                languages.append({
                    'code': code,
                    'name': lang_names.get(code, code.upper()),
                    'detection_method': 'character_pattern',
                    'confidence_boost': 1.0
                })
        
        return languages
    
    def analyze_text_complexity(self, text: str) -> Dict[str, Any]:
        """Analyze text to determine optimal processing strategy"""
        words = re.findall(r'\b\w+\b', text.lower())
        sentences = re.split(r'[.!?]+', text)
        
        analysis = {
            'word_count': len(words),
            'sentence_count': len(sentences),
            'avg_word_length': sum(len(word) for word in words) / len(words) if words else 0,
            'complexity': 'simple' if len(words) < 10 else 'medium' if len(words) < 50 else 'complex',
            'quick_detection_suitable': len(words) >= 3 and len(words) <= 100
        }
        
        return analysis


# Global detector instance
language_detector = SmartLanguageDetector()
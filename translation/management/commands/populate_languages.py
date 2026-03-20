"""
Management command to populate supported languages in the database.
"""

from django.core.management.base import BaseCommand
from translation.models import LanguageSupport


class Command(BaseCommand):
    help = 'Populate supported languages in the database'
    
    def handle(self, *args, **options):
        """Populate the database with regional priority languages"""
        
        # 0. Reset all existing languages to False for all support fields
        self.stdout.write('Resetting all language support flags to False...')
        LanguageSupport.objects.all().update(
            speech_to_text_supported=False,
            text_to_speech_supported=False,
            text_to_text_supported=False,
            speech_to_speech_translation_supported=False,
            image_translation_supported=False,
            document_translation_supported=False
        )
        
        # Priority languages: All Boolean flags set to True
        priority_langs = [
            ('en', 'English', 'English', '🇺🇸', False),
            ('sw', 'Swahili', 'Kiswahili', '🇰🇪', True),
            ('rw', 'Kinyarwanda', 'Ikinyarwanda', '🇷🇼', True),
            ('yo', 'Yoruba', 'Yorùbá', '🇳🇬', True),
            ('ha', 'Hausa', 'Hausa', '🇳🇬', True),
            ('ig', 'Igbo', 'Igbo', '🇳🇬', True),
        ]
        
        # All other languages will be set to False for support fields
        all_langs = [
            # Major world languages
            ('es', 'Spanish', 'Español', '🇪🇸', False),
            ('fr', 'French', 'Français', '🇫🇷', False),
            ('de', 'German', 'Deutsch', '🇩🇪', False),
            ('zh', 'Chinese', '中文', '🇨🇳', False),
            ('ja', 'Japanese', '日本語', '🇯🇵', False),
            ('ko', 'Korean', '한국어', '🇰🇷', False),
            ('ar', 'Arabic', 'العربية', '🇸🇦', False),
            ('hi', 'Hindi', 'हिन्दी', '🇮🇳', False),
            ('pt', 'Portuguese', 'Português', '🇵🇹', False),
            ('ru', 'Russian', 'Русский', '🇷🇺', False),
            ('it', 'Italian', 'Italiano', '🇮🇹', False),
            
            # Other African languages
            ('am', 'Amharic', 'አማርኛ', '🇪🇹', True),
            ('zu', 'Zulu', 'isiZulu', '🇿🇦', True),
            ('xh', 'Xhosa', 'isiXhosa', '🇿🇦', True),
            ('af', 'Afrikaans', 'Afrikaans', '🇿🇦', True),
            ('so', 'Somali', 'Soomaali', '🇸🇴', True),
        ]
        
        created_count = 0
        updated_count = 0
        
        # 1. Process Priority Languages
        for code, name, native_name, flag, african in priority_langs:
            lang, created = LanguageSupport.objects.update_or_create(
                code=code,
                defaults={
                    'name': name,
                    'native_name': native_name,
                    'flag_emoji': flag,
                    'speech_to_text_supported': True,
                    'text_to_speech_supported': True,
                    'text_to_text_supported': True,
                    'speech_to_speech_translation_supported': True,
                    'image_translation_supported': True,
                    'document_translation_supported': True,
                    'is_african_language': african,
                }
            )
            if created: created_count += 1
            else: updated_count += 1
            self.stdout.write(f'Enabled all services for: {name} ({code})')

        # 2. Process Other Languages (Disabled by default)
        for code, name, native_name, flag, african in all_langs:
            lang, created = LanguageSupport.objects.update_or_create(
                code=code,
                defaults={
                    'name': name,
                    'native_name': native_name,
                    'flag_emoji': flag,
                    'speech_to_text_supported': False,
                    'text_to_speech_supported': False,
                    'text_to_text_supported': False,
                    'speech_to_speech_translation_supported': False,
                    'image_translation_supported': False,
                    'document_translation_supported': False,
                    'is_african_language': african,
                }
            )
            if created: 
                created_count += 1
            else: 
                updated_count += 1
            self.stdout.write(f'Disabled all services for: {name} ({code})')
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully populated languages: {created_count} created, {updated_count} updated'
            )
        )

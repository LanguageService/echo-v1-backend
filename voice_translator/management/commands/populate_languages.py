"""
Management command to populate supported languages in the database.
"""

from django.core.management.base import BaseCommand
from voice_translator.models import LanguageSupport


class Command(BaseCommand):
    help = 'Populate supported languages in the database'
    
    def handle(self, *args, **options):
        """Populate the database with supported languages"""
        
        languages = [
            # Major world languages
            ('en', 'English', 'English', '🇺🇸', True, True, True, False),
            ('es', 'Spanish', 'Español', '🇪🇸', True, True, True, False),
            ('fr', 'French', 'Français', '🇫🇷', True, True, True, False),
            ('de', 'German', 'Deutsch', '🇩🇪', True, True, True, False),
            ('zh', 'Chinese', '中文', '🇨🇳', True, True, True, False),
            ('ja', 'Japanese', '日本語', '🇯🇵', True, True, True, False),
            ('ko', 'Korean', '한국어', '🇰🇷', True, True, True, False),
            ('ar', 'Arabic', 'العربية', '🇸🇦', True, True, True, False),
            ('hi', 'Hindi', 'हिन्दी', '🇮🇳', True, True, True, False),
            ('pt', 'Portuguese', 'Português', '🇵🇹', True, True, True, False),
            ('ru', 'Russian', 'Русский', '🇷🇺', True, True, True, False),
            ('it', 'Italian', 'Italiano', '🇮🇹', True, True, True, False),
            
            # African languages
            ('rw', 'Kinyarwanda', 'Ikinyarwanda', '🇷🇼', True, True, True, True),
            ('sw', 'Swahili', 'Kiswahili', '🇰🇪', True, True, True, True),
            ('am', 'Amharic', 'አማርኛ', '🇪🇹', True, True, True, True),
            ('yo', 'Yoruba', 'Yorùbá', '🇳🇬', True, True, True, True),
            ('ha', 'Hausa', 'Hausa', '🇳🇬', True, True, True, True),
            ('ig', 'Igbo', 'Igbo', '🇳🇬', True, True, True, True),
            ('zu', 'Zulu', 'isiZulu', '🇿🇦', True, True, True, True),
            ('xh', 'Xhosa', 'isiXhosa', '🇿🇦', True, True, True, True),
            ('af', 'Afrikaans', 'Afrikaans', '🇿🇦', True, True, True, True),
            ('so', 'Somali', 'Soomaali', '🇸🇴', True, True, True, True),
        ]
        
        created_count = 0
        updated_count = 0
        
        for code, name, native_name, flag, stt, tts, trans, african in languages:
            language, created = LanguageSupport.objects.get_or_create(
                code=code,
                defaults={
                    'name': name,
                    'native_name': native_name,
                    'flag_emoji': flag,
                    'speech_to_text_supported': stt,
                    'text_to_speech_supported': tts,
                    'translation_supported': trans,
                    'is_african_language': african,
                }
            )
            
            if created:
                created_count += 1
                self.stdout.write(f'Created language: {name} ({code})')
            else:
                # Update existing language
                language.name = name
                language.native_name = native_name
                language.flag_emoji = flag
                language.speech_to_text_supported = stt
                language.text_to_speech_supported = tts
                language.translation_supported = trans
                language.is_african_language = african
                language.save()
                updated_count += 1
                self.stdout.write(f'Updated language: {name} ({code})')
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully populated languages: {created_count} created, {updated_count} updated'
            )
        )
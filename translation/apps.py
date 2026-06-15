from django.apps import AppConfig
import sys

class VoiceTranslatorConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'translation'

    def ready(self):
        import translation.signals
        
        # Eagerly load ML models if we are running the actual server (not migrate/shell etc.)
        # This avoids downloading/loading huge models during migrations or management commands.
        if 'runserver' in sys.argv or 'gunicorn' in sys.modules or 'uvicorn' in sys.argv:
            from .providers.v2_pipelines import pipeline_manager
            pipeline_manager.initialize()

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

class PipelineManager:
    """
    Manages the V2 ML pipelines. Can be initialized eagerly during Django startup.
    Instantiates EnKinPipeline and KinEnPipeline as singletons.
    """
    _instance = None
    _en_kin_pipeline = None
    _kin_en_pipeline = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(PipelineManager, cls).__new__(cls)
        return cls._instance

    def initialize(self):
        """Eagerly loads models during server startup."""
        logger.info("Initializing V2 ML Pipelines on startup...")
        if os.environ.get('DISABLE_ML_PIPELINES') == '1':
            logger.info("ML Pipelines disabled via environment variable.")
            return

        from django.conf import settings
        if not getattr(settings, 'CUSTOM_MODEL', False):
            logger.info("CUSTOM_MODEL is False. Skipping ML Pipelines initialization.")
            return

        # Preload pipelines
        _ = self.en_kin
        _ = self.kin_en
        logger.info("V2 ML Pipelines successfully initialized.")

    @property
    def en_kin(self):
        from django.conf import settings
        if not getattr(settings, 'CUSTOM_MODEL', False):
            raise Exception("CUSTOM_MODEL is disabled in settings. Cannot load EnKinPipeline.")
            
        if self._en_kin_pipeline is None:
            logger.info("Initializing EnKinPipeline...")
            try:
                from custom_models.pipeline import EnKinPipeline
                self._en_kin_pipeline = EnKinPipeline()
            except Exception as e:
                logger.error(f"Failed to load EnKinPipeline: {e}")
                raise
        return self._en_kin_pipeline

    @property
    def kin_en(self):
        from django.conf import settings
        if not getattr(settings, 'CUSTOM_MODEL', False):
            raise Exception("CUSTOM_MODEL is disabled in settings. Cannot load KinEnPipeline.")
            
        if self._kin_en_pipeline is None:
            logger.info("Initializing KinEnPipeline...")
            try:
                from custom_models.kin_en_pipeline import KinEnPipeline
                self._kin_en_pipeline = KinEnPipeline()
            except Exception as e:
                logger.error(f"Failed to load KinEnPipeline: {e}")
                raise
        return self._kin_en_pipeline

# Global instance
pipeline_manager = PipelineManager()

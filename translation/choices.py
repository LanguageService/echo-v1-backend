from django.db import models
from django.utils.translation import gettext_lazy as _



class FeatureType(models.TextChoices):
    """
    Feature Types
    """


    SPEECH_TRANSLATION = "SPEECH_TRANSLATION", _("SPEECH_TRANSLATION")
    IMAGE_TRANSLATION = "IMAGE_TRANSLATION", _("IMAGE_TRANSLATION")
    SMS_TRANSLATION  = "SMS_TRANSLATION", _("SMS_TRANSLATION")
    TEXT_TRANSLATION  = "TEXT_TRANSLATION", _("TEXT_TRANSLATION")
    CALL_TRANSLATION = "CALL_TRANSLATION", _("CALL_TRANSLATION")
    EBOOK_TRANSLATION = "EBOOK_TRANSLATION", _("EBOOK_TRANSLATION")

    
class TranslationStatus(models.TextChoices):
    """
    Translation status for background tasks
    """
    PENDING = "PENDING", _("Pending")
    PROCESSING = "PROCESSING", _("Processing")
    COMPLETED = "COMPLETED", _("Completed")
    FAILED = "FAILED", _("Failed")


class TranslationMode(models.TextChoices):
    """
    Translation Modes
    """
    SHORT = "SHORT", _("Short (Synchronous)")
    LARGE = "LARGE", _("Large (Asynchronous)")


class SpeechServiceType(models.TextChoices):
    """
    Speech Service Types
    """
    STS = "STS", _("Speech to Speech")
    STT = "STT", _("Speech to Text")
    TTS = "TTS", _("Text to Speech")

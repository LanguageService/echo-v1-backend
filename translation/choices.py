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

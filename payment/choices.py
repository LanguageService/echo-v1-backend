from django.db import models
from django.utils.translation import gettext_lazy as _


class PaymentStatus(models.TextChoices):
    """
    Payment Statuses.
    """

    PENDING = "PENDING", _("PENDING")
    SUCCESS = "SUCCESS", _("SUCCESS")
    FAILED = "FAILED", _("FAILED")


class PaymentType(models.TextChoices):
    """
    Payment Types.
    """

    NEW_SERVICE = "NEW_SERVICE", _("NEW_SERVICE")
    SUBSCRIPTION = "SUBSCRIPTION", _("SUBSCRIPTION")

from django.db import models
from django.utils.translation import gettext_lazy as _


class TransactionType(models.TextChoices):
    """
    Transaction Types.
    """

    TOPUP = "TOPUP", _("TOPUP")
    WITHDRAWAL = "WITHDRAWAL", _("WITHDRAWAL")


class TransactionFlow(models.TextChoices):
    """
    Transaction Flows.
    """

    DEBIT = "DEBIT", _("DEBIT")
    CREDIT = "CREDIT", _("CREDIT")

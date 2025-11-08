from django.db import models
from django.utils.translation import gettext_lazy as _


class TokenType(models.TextChoices):
    """
    Token Types.
    """

    REGISTRATION = "REGISTRATION", _("REGISTRATION")
    RESET_PASSWORD = "RESET PASSWORD", _("RESET PASSWORD")
    LOGIN = "LOGIN", _("LOGIN")

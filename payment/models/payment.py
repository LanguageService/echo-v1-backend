from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models

from core.model import BaseModel
from core.utils import get_random_string, get_current_unix_timestamp
from payment import choices


User = get_user_model()


def generate_random(payment_type):
    return f"{payment_type[:3]}-{get_random_string(15)}{get_current_unix_timestamp()}"


class Payment(BaseModel):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="payments",
    )
    amount = models.DecimalField(
        decimal_places=2,
        default=0.0,
        max_digits=10,
        validators=[MinValueValidator(0)],
    )
    reference = models.CharField(max_length=100, unique=True)
    status = models.CharField(
        choices=choices.PaymentStatus.choices,
        default=choices.PaymentStatus.PENDING,
        max_length=100,
    )
    payment_type = models.CharField(
        choices=choices.PaymentType.choices,
        default=choices.PaymentType.NEW_SERVICE,
        max_length=100,
    )
    payment_channel = models.CharField(blank=True, max_length=100, null=True)
    gateway_charge = models.DecimalField(
        decimal_places=2,
        default=0.0,
        max_digits=10,
        validators=[MinValueValidator(0)],
    )
    service_charge = models.DecimalField(
        decimal_places=2,
        default=0.0,
        max_digits=10,
        validators=[MinValueValidator(0)],
    )


    @classmethod
    def generate_reference(cls, payment_type):
        rand = generate_random(payment_type)
        while cls.objects.filter(reference=rand).exists():
            rand = generate_random(payment_type)

        return rand.upper()

    def clean(self):
        if self.payment_type == choices.PaymentType.WALLET_TOPUP and self.plan:
            raise ValidationError({"plan": "This field must be blank."})
        if self.payment_type == choices.PaymentType.SUBSCRIPTION and not self.plan:
            raise ValidationError({"plan": "This field is required."})
        return super().clean()

    def save(self, *args, **kwargs):
        self.clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.user.first_name}  {self.user.last_name}  ->  {str(self.amount)}"

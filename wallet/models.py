from django.contrib.auth import get_user_model
from django.db import models
from django.core.validators import MinValueValidator

from . import choices


User = get_user_model()


class GlobalConfig(models.Model):
    free_credit = models.IntegerField(default=30, help_text="Initial free credits for new users")

    class Meta:
        verbose_name = "Global Configuration"
        verbose_name_plural = "Global Configuration"

    @classmethod
    def get_config(cls):
        config = cls.objects.first()
        if not config:
            config = cls.objects.create()
        return config

    def __str__(self):
        return f"Global Configuration {self.id}"


class Wallet(models.Model):
    user = models.OneToOneField(User, related_name="wallet", on_delete=models.CASCADE)
    balance = models.DecimalField(max_digits=14, decimal_places=6, default=0)

    @classmethod
    def fetch_for_user(cls, user):
        wallet, _ = cls.objects.get_or_create(user=user)
        return wallet

    def topup(self, amount, created_by=None, notes='', initiated_by_admin=False):
        self.balance += amount
        self.save()

        Transaction.objects.create(
            wallet=self,
            amount=amount,
            withdrawable_amount=amount,
            service_fee=0,
            type=choices.TransactionType.TOPUP,
            flow=choices.TransactionFlow.CREDIT,
            created_by=created_by,
            notes=notes,
            initiated_by_admin=initiated_by_admin,
        )

    def __str__(self):
        return f"{self.user.email} — {self.balance} credits"


class Transaction(models.Model):
    wallet = models.ForeignKey(
        Wallet, related_name="transactions", on_delete=models.CASCADE
    )
    amount = models.DecimalField(max_digits=14, decimal_places=6, validators=[MinValueValidator(0)])
    withdrawable_amount = models.DecimalField(max_digits=14, decimal_places=6, default=0, validators=[MinValueValidator(0)])
    service_fee = models.DecimalField(max_digits=14, decimal_places=6, default=0, validators=[MinValueValidator(0)])
    type = models.CharField(max_length=50, choices=choices.TransactionType.choices)
    flow = models.CharField(max_length=50, choices=choices.TransactionFlow.choices)
    notes = models.TextField(blank=True, default='')
    initiated_by_admin = models.BooleanField(default=False)
    created_by = models.ForeignKey(
        User,
        blank=True,
        null=True,
        related_name="initiated_transactions",
        on_delete=models.SET_NULL,
    )
    created = models.DateTimeField(auto_now_add=True, editable=False, null=True)
    modified = models.DateTimeField(auto_now=True, editable=False, null=True)

    class Meta:
        ordering = ['-created']

    def __str__(self):
        tag = " [ADMIN]" if self.initiated_by_admin else ""
        return f"{self.wallet.user.email} — {self.type} {self.amount}{tag}"

from django.db.models.signals import post_save
from django.dispatch import receiver
import logging

logger = logging.getLogger(__name__)

@receiver(post_save, sender=User)
def issue_signup_credits(sender, instance, created, **kwargs):
    """
    Issue free credits based on global config to a new user upon signup.
    """
    if created:
        try:
            config = GlobalConfig.get_config()
            wallet = Wallet.fetch_for_user(instance)
            wallet.topup(amount=config.free_credit, notes="Signup bonus")
            logger.info(f"Issued {config.free_credit} signup credits to user {instance.email}")
        except Exception as e:
            logger.error(f"Failed to issue signup credits for user {instance.email}: {e}")

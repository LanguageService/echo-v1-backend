from django.contrib.auth import get_user_model
from django.db import models
from django.core.validators import MinValueValidator

from . import choices


User = get_user_model()


class Wallet(models.Model):
    user = models.OneToOneField(User, related_name="wallet", on_delete=models.CASCADE)
    balance = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    # Stripe reusable authorization code
    authorization_code = models.CharField(max_length=200, null=True, blank=True)

    @classmethod
    def fetch_for_user(cls, user):
        wallet, _ = cls.objects.get_or_create(user=user)
        return wallet
    
    #TODO: change this to withdrawal
    def topup(self, amount, created_by=None):
        self.balance += amount
        self.save()

        Transaction.objects.create(
            wallet=self,
            amount=amount,
            type=choices.TransactionType.TOPUP,
            flow=choices.TransactionFlow.CREDIT,
            created_by=None,
        )


class Transaction(models.Model):
    wallet = models.ForeignKey(
        Wallet, related_name="transactions", on_delete=models.CASCADE
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2,validators=[MinValueValidator(0)])
    withdrawable_amount = models.DecimalField(max_digits=10, decimal_places=2,validators=[MinValueValidator(0)])
    service_fee = models.DecimalField(max_digits=10, decimal_places=2,validators=[MinValueValidator(0)])
    type = models.CharField(max_length=50, choices=choices.TransactionType.choices)
    flow = models.CharField(max_length=50, choices=choices.TransactionFlow.choices)
    created = models.DateTimeField(
        auto_now_add=True,
        editable=False,
        null=True,
    )
    modified = models.DateTimeField(
        auto_now=True,
        editable=False,
        null=True,
    )
    created_by = models.OneToOneField(
        User,
        blank=True,
        null=True,
        related_name="transactions",
        on_delete=models.CASCADE,
    )

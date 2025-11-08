from rest_framework import serializers

from . import models


class WalletSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Wallet
        exclude = ("authorization_code",)


class TransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Transaction
        fields = "__all__"

from rest_framework import serializers

from . import models


class WalletSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Wallet
        fields = "__all__"


class TransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Transaction
        fields = "__all__"


class GlobalConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.GlobalConfig
        fields = "__all__"

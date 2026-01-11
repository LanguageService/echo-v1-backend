from decimal import Decimal

from rest_framework import serializers

from .models.payment import Payment
from .models.webhook import KPayWebhookEvent


class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = "__all__"


class TopUpSerializer(serializers.Serializer):
    amount = serializers.DecimalField(
        max_digits=10, decimal_places=2, min_value=Decimal(100)
    )
    callback_url = serializers.URLField()





class KPayWebhookSerializer(serializers.ModelSerializer):
    class Meta:
        model = KPayWebhookEvent
        fields = "__all__"

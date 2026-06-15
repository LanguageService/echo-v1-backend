from decimal import Decimal

from rest_framework import serializers

from .models.payment import Payment
from .models.webhook import PaymentWebhookEvent


class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = "__all__"


class TopUpSerializer(serializers.Serializer):
    amount = serializers.DecimalField(
        max_digits=10, decimal_places=2, min_value=Decimal(5)
    )
    callback_url = serializers.URLField(required=False, allow_null=True, default=None)





class PaymentWebhookSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentWebhookEvent
        fields = "__all__"

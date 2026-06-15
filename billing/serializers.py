from rest_framework import serializers
from .models import PricingConfig

class PricingConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = PricingConfig
        fields = ['id', 'channel', 'translation_type', 'unit_name', 'cost_per_unit']

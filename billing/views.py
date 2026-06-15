from rest_framework import viewsets, permissions
from .models import PricingConfig
from .serializers import PricingConfigSerializer

class PricingViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Public endpoint to view the billing/pricing configuration.
    """
    queryset = PricingConfig.objects.all()
    serializer_class = PricingConfigSerializer
    permission_classes = [permissions.AllowAny]

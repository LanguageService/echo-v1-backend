from django.contrib import admin
from .models import PricingConfig, CurrencyRate, CreditConversion

@admin.register(PricingConfig)
class PricingConfigAdmin(admin.ModelAdmin):
    list_display = ('channel', 'translation_type', 'cost_per_unit', 'unit_name')
    list_filter = ('channel', 'translation_type')
    search_fields = ('translation_type', 'channel')

@admin.register(CurrencyRate)
class CurrencyRateAdmin(admin.ModelAdmin):
    list_display = ('currency_code', 'rate_to_usd', 'is_active', 'updated_at')
    list_filter = ('is_active',)
    search_fields = ('currency_code',)

@admin.register(CreditConversion)
class CreditConversionAdmin(admin.ModelAdmin):
    list_display = ('usd_amount', 'credit_amount')

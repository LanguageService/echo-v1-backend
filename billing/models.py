from django.db import models

class CurrencyRate(models.Model):
    currency_code = models.CharField(max_length=10, unique=True, help_text="e.g., NGN, RWF, EUR")
    rate_to_usd = models.DecimalField(max_digits=14, decimal_places=6, help_text="Amount of this currency that equals 1 USD")
    is_active = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.currency_code} - {self.rate_to_usd}"

class PricingConfig(models.Model):
    class ChannelChoices(models.TextChoices):
        UI = 'UI', 'User Interface (Credits)'
        API = 'API', 'Developer API (Metered USD)'

    class TranslationType(models.TextChoices):
        SPEECH_TO_SPEECH = 'STS', 'Speech to Speech'
        SPEECH_TO_TEXT = 'STT', 'Speech to Text'
        TEXT_TO_TEXT = 'TTT', 'Text to Text'
        TEXT_TO_SPEECH = 'TTS', 'Text to Speech'
        DOCUMENT = 'DOC', 'Document Translation'

    channel = models.CharField(max_length=10, choices=ChannelChoices.choices)
    translation_type = models.CharField(max_length=10, choices=TranslationType.choices)
    
    # Billing logic
    unit_name = models.CharField(max_length=50, help_text="e.g., minute, million_chars, page")
    cost_per_unit = models.DecimalField(max_digits=14, decimal_places=6, help_text="If channel is UI, this is in Credits. If API, this is in USD.")

    class Meta:
        unique_together = ('channel', 'translation_type')

    def __str__(self):
        return f"{self.get_channel_display()} - {self.get_translation_type_display()} - {self.cost_per_unit}/{self.unit_name}"

class CreditConversion(models.Model):
    usd_amount = models.DecimalField(max_digits=10, decimal_places=2, default=1.00)
    credit_amount = models.IntegerField(default=10, help_text="Number of credits given per usd_amount")

    def __str__(self):
        return f"${self.usd_amount} = {self.credit_amount} Credits"

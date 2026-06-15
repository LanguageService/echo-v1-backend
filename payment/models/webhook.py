from django.db import models


class PaymentWebhookEvent(models.Model):
    payment = models.ForeignKey(
        'payment.Payment',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='webhook_events',
    )
    refid = models.CharField(max_length=100, db_index=True)
    transaction_id = models.CharField(max_length=100, null=True, blank=True)
    status_id = models.CharField(max_length=10)
    status_desc = models.TextField(blank=True, default='')
    raw_payload = models.JSONField()
    processed = models.BooleanField(default=False)
    source = models.CharField(max_length=20, default='paystack', help_text="Gateway that sent this event (paystack, kpay, etc.)")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Payment Webhook Event'
        verbose_name_plural = 'Payment Webhook Events'
        indexes = [
            models.Index(fields=['refid']),
        ]

    def __str__(self):
        return f"Webhook({self.source}: {self.refid}, status={self.status_id})"

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models



class KPayWebhookEvent(models.Model):
    refid = models.CharField(max_length=100, db_index=True)
    transaction_id = models.CharField(max_length=100, null=True, blank=True)
    status_id = models.CharField(max_length=10)
    status_desc = models.TextField()
    raw_payload = models.JSONField()

    processed = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["refid"]),
        ]

    def __str__(self):
        return f"KPayWebhook(refid={self.refid}, status={self.status_id})"

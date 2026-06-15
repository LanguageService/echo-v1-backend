from django.db import models
from django.contrib.auth import get_user_model
import uuid
import secrets

User = get_user_model()

class DeveloperApp(models.Model):
    user = models.ForeignKey(User, related_name='developer_apps', on_delete=models.CASCADE)
    name = models.CharField(max_length=255, help_text="Name of the external app using this API")
    client_id = models.CharField(max_length=100, unique=True, editable=False)
    # Storing hashed secrets in production is recommended, but for MVP we store plain to show them once or handle it carefully.
    client_secret = models.CharField(max_length=255, editable=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.client_id:
            self.client_id = f"echo_{secrets.token_urlsafe(16)}"
        if not self.client_secret:
            self.client_secret = f"sk_echo_{secrets.token_urlsafe(32)}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({self.client_id})"

class WebhookEndpoint(models.Model):
    developer_app = models.ForeignKey(DeveloperApp, related_name='webhooks', on_delete=models.CASCADE)
    url = models.URLField()
    secret = models.CharField(max_length=100, blank=True, help_text="Used to sign webhook payloads so the developer can verify it came from us")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.secret:
            self.secret = f"whsec_{secrets.token_hex(16)}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Webhook for {self.developer_app.name} -> {self.url}"

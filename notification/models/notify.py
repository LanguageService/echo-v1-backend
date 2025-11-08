from django.db import models
from .base import Platform
from core.model import BaseModel


# Create your models here.
class NotificationPlatform(BaseModel):
    user = models.ForeignKey(
        "users.User",
        on_delete=models.CASCADE,
        related_name="user_notification_platforms",
    )
    platform = models.CharField(max_length=255, choices=Platform.choices())
    status = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.user.first_name} {self.user.last_name} -> {self.platform} -> {self.status}"

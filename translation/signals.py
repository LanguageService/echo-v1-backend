from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from .models import UserSettings
import logging

logger = logging.getLogger(__name__)

User = get_user_model()

@receiver(post_save, sender=User)
def create_user_settings(sender, instance, created, **kwargs):
    """
    Signal handler to create UserSettings when a new User is created.
    """
    if created:
        try:
            UserSettings.objects.create(user=instance,autoplay=True,voice='Zephyr')
            logger.info(f"Created default settings for user {instance.email}")
        except Exception as e:
            logger.error(f"Failed to create default settings for user {instance.email}: {e}")

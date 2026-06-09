from django.test import TestCase
from django.contrib.auth import get_user_model
from translation.models import UserSettings

User = get_user_model()

class SignalTestCase(TestCase):
    def test_user_settings_created_on_user_creation(self):
        """Test that UserSettings are automatically created when a new User is created"""
        email = "test@example.com"
        password = "testpassword123"
        
        # Create user
        user = User.objects.create_user(email=email, password=password)
        
        # Check if UserSettings exists
        self.assertTrue(UserSettings.objects.filter(user=user).exists())
        
        # Check default values
        settings = UserSettings.objects.get(user=user)
        self.assertEqual(settings.model, 'gemini-2.5-flash')  # default
        self.assertEqual(settings.voice, 'Zephyr')            # default

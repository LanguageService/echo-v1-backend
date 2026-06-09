from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from django.contrib.auth import get_user_model
from translation.models import Translation
from translation.choices import FeatureType

User = get_user_model()

class GeneralTranslationHistoryAPITest(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpassword123',
            username='testuser'
        )
        self.client.force_authenticate(user=self.user)
        self.url = reverse('general_translation_history')

    def test_get_general_history(self):
        # Create test translations
        Translation.objects.create(
            user=self.user,
            original_text="Hello",
            translated_text="Hola",
            original_language="en",
            target_language="es",
            feature_type=FeatureType.TEXT_TRANSLATION
        )
        Translation.objects.create(
            user=self.user,
            original_text="Speech",
            translated_text="Discurso",
            original_language="en",
            target_language="es",
            feature_type=FeatureType.SPEECH_TRANSLATION
        )

        response = self.client.get(self.url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 2)
        
        results = response.data['results']
        self.assertEqual(len(results), 2)
        
        # Verify feature_type is present and correct
        feature_types = [t['feature_type'] for t in results]
        self.assertIn(FeatureType.TEXT_TRANSLATION, feature_types)
        self.assertIn(FeatureType.SPEECH_TRANSLATION, feature_types)

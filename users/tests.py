from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status
from django.urls import reverse
from .models import User, GigSeeker
from .models.client import Client

class GigSeekerProfileViewSetTestCase(TestCase):
    def setUp(self):
        """Set up the test environment for GigSeeker tests."""
        self.client = APIClient()
        self.user = User.objects.create_user(
            email='testseeker@example.com',
            password='password123',
            first_name='Test',
            last_name='Seeker',
            user_type=User.GIG_SEEKER,
            is_verified=True,
            is_active=True
        )
        self.gig_seeker = GigSeeker.objects.get(user=self.user)
        self.gig_seeker.bio = "Test bio"
        self.gig_seeker.skills = "Python, Django"
        self.gig_seeker.hourly_rate = 50.00
        self.gig_seeker.save()

        self.client.force_authenticate(user=self.user)

    def test_get_me_profile(self):
        """
        Ensure an authenticated gig seeker can retrieve their own profile via the 'me' endpoint.
        """
        url = reverse('gig-seekers-me')
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['user']['email'], self.user.email)
        self.assertEqual(response.data['bio'], self.gig_seeker.bio)
        self.assertEqual(response.data['skills'], self.gig_seeker.skills)

    def test_update_me_profile(self):
        """
        Ensure an authenticated gig seeker can update their own profile via the 'me' endpoint.
        """
        url = reverse('gig-seekers-me')
        payload = {
            "bio": "An updated bio.",
            "skills": "Python, Django, REST Framework",
            "user": {
                "first_name": "UpdatedFirst"
            }
        }
        response = self.client.patch(url, payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.gig_seeker.refresh_from_db()
        self.user.refresh_from_db()
        self.assertEqual(self.gig_seeker.bio, "An updated bio.")
        self.assertEqual(self.user.first_name, "UpdatedFirst")


class AuthViewSetTestCase(TestCase):
    def setUp(self):
        """Set up the test environment for Auth tests."""
        self.client = APIClient()

    def test_create_client_user(self):
        """
        Ensure a new client user and profile can be created successfully.
        """
        url = reverse('auth-create-client-user')
        payload = {
            "first_name": "Test",
            "last_name": "Client",
            "email": "newclient@example.com",
            "password": "strongpassword123",
            "client_type": "Individual"
        }
        response = self.client.post(url, payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(User.objects.count(), 1)
        self.assertEqual(Client.objects.count(), 1)

        user = User.objects.get(email="newclient@example.com")
        self.assertEqual(user.user_type, User.CLIENT)
        self.assertTrue(hasattr(user, 'client_profile'))
        self.assertEqual(user.client_profile.client_type, "Individual")

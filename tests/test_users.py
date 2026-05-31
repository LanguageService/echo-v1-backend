from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from django.contrib.auth import get_user_model
from users.models import OneTimePassword
from unittest.mock import patch

User = get_user_model()

class UserAuthTestCase(TestCase):
    """
    Comprehensive tests for User Authentication flows including Registration, 
    OTP Verification, Resend OTP, Password Reset, and Google Login.
    """
    
    def setUp(self):
        self.client = APIClient()

    @patch('notification.services.email.EmailDispatcher.send_verification')
    def test_customer_registration(self, mock_send_verification):
        url = reverse('auth-create-customer-user')
        payload = {
            "first_name": "Test",
            "last_name": "Customer",
            "email": "customer@example.com",
            "password": "strongpassword123"
        }
        response = self.client.post(url, payload, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(User.objects.count(), 1)
        
        user = User.objects.get(email="customer@example.com")
        self.assertEqual(user.user_type, User.CUSTOMER)
        self.assertFalse(user.is_verified)
        
        # Verify that verification email was sent
        mock_send_verification.assert_called_once()
        args, kwargs = mock_send_verification.call_args
        self.assertEqual(args[0], user)
        self.assertIn('otp_code', kwargs)
        
        # Verify OTP was created in DB
        self.assertEqual(OneTimePassword.objects.filter(email=user.email).count(), 1)

    @patch('notification.services.email.EmailDispatcher.send_onboarding')
    def test_verify_otp(self, mock_send_onboarding):
        # Create unverified user
        user = User.objects.create_user(
            email="verify@example.com",
            password="pass",
            active=True
        )
        user.is_active = True
        user.save()
        
        # Generate OTP
        otp_obj = OneTimePassword.generate_otp("verify@example.com")
        
        url = reverse('auth-verify-otp')
        response = self.client.post(url, {
            "email": "verify@example.com",
            "otp_code": otp_obj.token
        }, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        user.refresh_from_db()
        self.assertTrue(user.is_verified)
        
        # Verify onboarding email was sent
        mock_send_onboarding.assert_called_once_with(user)

    @patch('notification.services.email.EmailDispatcher.send_verification')
    def test_resend_otp(self, mock_send_verification):
        user = User.objects.create_user(
            email="resend@example.com",
            password="pass",
            active=True
        )
        user.is_active = True
        user.save()
        
        url = reverse('auth-resend-otp')
        response = self.client.post(url, {
            "email": "resend@example.com"
        }, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        mock_send_verification.assert_called_once()
        args, kwargs = mock_send_verification.call_args
        self.assertEqual(args[0], user)

    @patch('notification.services.email.EmailDispatcher.send_password_reset')
    def test_initiate_reset_password(self, mock_send_reset):
        user = User.objects.create_user(
            email="reset@example.com",
            password="pass",
            active=True
        )
        user.is_active = True
        user.is_verified = True
        user.save()
        
        url = reverse('auth-initiate-reset-password')
        response = self.client.post(url, {
            "email": "reset@example.com"
        }, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        mock_send_reset.assert_called_once()
        args, kwargs = mock_send_reset.call_args
        self.assertEqual(args[0], user)

    @patch('notification.services.email.EmailDispatcher.send_onboarding')
    @patch('google.oauth2.id_token.verify_oauth2_token')
    def test_google_login_new_user(self, mock_verify, mock_send_onboarding):
        # Mock Google token payload
        mock_verify.return_value = {
            "email": "google@example.com",
            "given_name": "Google",
            "family_name": "User"
        }
        
        url = reverse('auth-google-login')
        response = self.client.post(url, {
            "id_token": "fake_token_123"
        }, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Check user was created
        user = User.objects.get(email="google@example.com")
        self.assertTrue(user.is_verified)
        self.assertEqual(user.first_name, "Google")
        self.assertEqual(user.last_name, "User")
        
        # Check onboarding email was sent
        mock_send_onboarding.assert_called_once_with(user)

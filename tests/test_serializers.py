"""
Serializer unit tests for users app.
Tests validation logic, field presence, and serializer create flows.
"""

from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIRequestFactory
from unittest.mock import patch

from users.serializers import (
    CustomerRegistrationSerializer,
    AdminUserRegistrationSerializer,
    OTPVerificationSerializer,
    ResetPasswordSerializer,
    ChangePasswordSerializer,
    GoogleLoginSerializer,
)
from users.serializers.base import EmailSerializer

User = get_user_model()


class CustomerRegistrationSerializerTestCase(TestCase):

    def test_valid_data_creates_user(self):
        data = {
            "first_name": "John",
            "last_name": "Doe",
            "email": "john@example.com",
            "password": "Str0ngP@ss1",
        }
        s = CustomerRegistrationSerializer(data=data)
        self.assertTrue(s.is_valid(), s.errors)
        with patch('notification.models.NotificationPlatform.objects.get_or_create'), \
             patch('wallet.models.Wallet.fetch_for_user'):
            user = s.save()
        self.assertEqual(user.email, "john@example.com")
        self.assertEqual(user.user_type, User.CUSTOMER)
        self.assertFalse(user.is_verified)

    def test_missing_fields_invalid(self):
        s = CustomerRegistrationSerializer(data={"email": "a@b.com"})
        self.assertFalse(s.is_valid())
        self.assertIn("first_name", s.errors)
        self.assertIn("last_name", s.errors)

    def test_duplicate_email_invalid(self):
        u = User.objects.create_user(email="dup@example.com", password="pass")
        data = {
            "first_name": "Jane",
            "last_name": "Doe",
            "email": "dup@example.com",
            "password": "Str0ngP@ss1",
        }
        s = CustomerRegistrationSerializer(data=data)
        self.assertFalse(s.is_valid())
        self.assertIn("email", s.errors)

    def test_weak_password_invalid(self):
        data = {
            "first_name": "Jane",
            "last_name": "Doe",
            "email": "weak@example.com",
            "password": "123",
        }
        s = CustomerRegistrationSerializer(data=data)
        self.assertFalse(s.is_valid())
        self.assertIn("password", s.errors)


class OTPVerificationSerializerTestCase(TestCase):

    def test_valid_otp(self):
        s = OTPVerificationSerializer(data={"otp_code": "123456", "email": "a@b.com"})
        self.assertTrue(s.is_valid(), s.errors)

    def test_invalid_otp_letters(self):
        s = OTPVerificationSerializer(data={"otp_code": "abc123", "email": "a@b.com"})
        self.assertFalse(s.is_valid())

    def test_otp_too_short(self):
        s = OTPVerificationSerializer(data={"otp_code": "12345", "email": "a@b.com"})
        self.assertFalse(s.is_valid())

    def test_missing_otp(self):
        s = OTPVerificationSerializer(data={"email": "a@b.com"})
        self.assertFalse(s.is_valid())


class EmailSerializerTestCase(TestCase):

    def test_existing_active_user_valid(self):
        u = User.objects.create_user(email="exist@example.com", password="pass", active=True)
        u.is_active = True
        u.save()
        s = EmailSerializer(data={"email": "exist@example.com"})
        self.assertTrue(s.is_valid(), s.errors)

    def test_non_existing_user_invalid(self):
        s = EmailSerializer(data={"email": "nobody@example.com"})
        self.assertFalse(s.is_valid())

    def test_inactive_user_invalid(self):
        u = User.objects.create_user(email="inactive@example.com", password="pass")
        u.is_active = False
        u.save()
        s = EmailSerializer(data={"email": "inactive@example.com"})
        self.assertFalse(s.is_valid())


class GoogleLoginSerializerTestCase(TestCase):

    def test_valid(self):
        s = GoogleLoginSerializer(data={"id_token": "sometoken"})
        self.assertTrue(s.is_valid())

    def test_missing_token(self):
        s = GoogleLoginSerializer(data={})
        self.assertFalse(s.is_valid())


class UserSerializerTestCase(TestCase):

    def test_password_not_in_output(self):
        from users.serializers import UserSerializer
        u = User.objects.create_user(email="ser@example.com", password="secret", active=True)
        data = UserSerializer(u).data
        self.assertNotIn("password", data)
        self.assertEqual(data["email"], u.email)

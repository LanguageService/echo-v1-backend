"""
OTP Model tests – covers OneTimePassword class methods that are the
core of the verification / password-reset / login flow.
"""

from unittest.mock import patch
from django.test import TestCase
from django.utils import timezone
from django.contrib.auth import get_user_model

from users.models import OneTimePassword
from users import choices

User = get_user_model()


def _make_active_user(email, password="pass"):
    """Helper – create a user that can be authenticated."""
    user = User.objects.create_user(email=email, password=password, active=True)
    user.is_active = True
    user.save()
    return user


class OTPGenerateTestCase(TestCase):
    """Tests for OneTimePassword.generate_otp."""

    def test_generate_creates_otp(self):
        email = "gen@example.com"
        otp = OneTimePassword.generate_otp(email)
        self.assertIsNotNone(otp)
        self.assertEqual(otp.email, email)
        self.assertFalse(otp.used)
        self.assertEqual(otp.token_type, choices.TokenType.REGISTRATION)

    def test_generate_updates_existing(self):
        email = "update@example.com"
        otp1 = OneTimePassword.generate_otp(email)
        otp2 = OneTimePassword.generate_otp(email)
        # should be the same DB row (update_or_create)
        self.assertEqual(otp1.email, otp2.email)
        self.assertEqual(otp1.token_type, otp2.token_type)

    def test_generate_different_token_types(self):
        email = "types@example.com"
        otp_reg = OneTimePassword.generate_otp(email, choices.TokenType.REGISTRATION)
        otp_reset = OneTimePassword.generate_otp(email, choices.TokenType.RESET_PASSWORD)
        self.assertNotEqual(otp_reg.token_type, otp_reset.token_type)


class OTPVerifyTestCase(TestCase):
    """Tests for OneTimePassword.verify_token."""

    def test_valid_token(self):
        email = "verify@example.com"
        otp = OneTimePassword.generate_otp(email)
        status, msg = OneTimePassword.verify_token(otp.token)
        self.assertTrue(status)

    def test_invalid_token(self):
        status, msg = OneTimePassword.verify_token("000000")
        self.assertFalse(status)

    def test_used_token_rejected(self):
        email = "used@example.com"
        otp = OneTimePassword.generate_otp(email)
        otp.used = True
        otp.save()
        status, msg = OneTimePassword.verify_token(otp.token)
        self.assertFalse(status)

    def test_expired_token_rejected(self):
        email = "exp@example.com"
        otp = OneTimePassword.generate_otp(email)
        # Backdate creation so it's expired (timeout is 3600 hours!)
        past = timezone.now() - timezone.timedelta(hours=3601)
        OneTimePassword.objects.filter(pk=otp.pk).update(created=past)
        otp.refresh_from_db()
        status, msg = OneTimePassword.verify_token(otp.token)
        self.assertFalse(status)


class OTPActivateUserTestCase(TestCase):
    """Tests for OneTimePassword.activate_user."""

    def test_activate_user_success(self):
        user = _make_active_user("act@example.com")
        otp = OneTimePassword.generate_otp(user.email)
        success, result = OneTimePassword.activate_user(token=otp.token, email=user.email)
        self.assertTrue(success)
        user.refresh_from_db()
        self.assertTrue(user.is_verified)

    def test_activate_user_invalid_token(self):
        success, msg = OneTimePassword.activate_user(token="999999", email="nobody@example.com")
        self.assertFalse(success)

    def test_activate_user_no_matching_user(self):
        # OTP exists but no user with that email
        otp = OneTimePassword.generate_otp("ghost@example.com")
        success, msg = OneTimePassword.activate_user(token=otp.token, email="ghost@example.com")
        self.assertFalse(success)


class OTPSetPasswordTestCase(TestCase):
    """Tests for OneTimePassword.set_password."""

    def test_set_password_success(self):
        user = _make_active_user("setpw@example.com")
        otp = OneTimePassword.generate_otp(user.email, choices.TokenType.RESET_PASSWORD)
        success, msg = OneTimePassword.set_password(
            token=otp.token,
            password="Str0ngP@ssword",
            token_type=choices.TokenType.RESET_PASSWORD,
        )
        self.assertTrue(success)
        user.refresh_from_db()
        self.assertTrue(user.check_password("Str0ngP@ssword"))

    def test_set_password_invalid_token(self):
        success, msg = OneTimePassword.set_password(
            token="000000",
            password="whatever",
            token_type=choices.TokenType.RESET_PASSWORD,
        )
        self.assertFalse(success)


class OTPUpdateTokenTestCase(TestCase):
    """Tests for OneTimePassword.update_token."""

    def test_mark_used(self):
        otp = OneTimePassword.generate_otp("mark@example.com")
        OneTimePassword.update_token(otp.token, otp.token_type, is_used=True)
        otp.refresh_from_db()
        self.assertTrue(otp.used)


class OTPGetUserTestCase(TestCase):
    """Tests for OneTimePassword.get_user."""

    def test_get_user_found(self):
        user = _make_active_user("getuser@example.com")
        otp = OneTimePassword.generate_otp(user.email)
        found = OneTimePassword.get_user(otp.token, user.email)
        self.assertEqual(found, user)

    def test_get_user_not_found(self):
        result = OneTimePassword.get_user("000000", "nobody@example.com")
        self.assertIsNone(result)


class OTPUseMethodTestCase(TestCase):
    """Tests for the .use() instance method."""

    def test_use_marks_as_used(self):
        otp = OneTimePassword.generate_otp("use@example.com")
        otp.use()
        otp.refresh_from_db()
        self.assertTrue(otp.used)

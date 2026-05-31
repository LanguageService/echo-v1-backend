from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
from unittest.mock import patch

from users.services import EmailService, UserStatsService, SecurityService

User = get_user_model()


class EmailServiceTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='emailservice@example.com',
            password='testpass123'
        )
        self.user.first_name = 'Email'
        self.user.last_name = 'Service'
        self.user.save()

    @patch('users.services.send_mail')
    def test_send_verification_email(self, mock_send_mail):
        EmailService.send_verification_email(self.user, '123456')
        mock_send_mail.assert_called_once()
        args, kwargs = mock_send_mail.call_args
        self.assertIn('123456', kwargs['message'])
        self.assertEqual(kwargs['recipient_list'], [self.user.email])

    @patch('users.services.send_mail')
    def test_send_password_reset_email(self, mock_send_mail):
        EmailService.send_password_reset_email(self.user, '654321')
        mock_send_mail.assert_called_once()
        args, kwargs = mock_send_mail.call_args
        self.assertIn('654321', kwargs['message'])

    @patch('users.services.send_mail')
    def test_send_welcome_email(self, mock_send_mail):
        EmailService.send_welcome_email(self.user)
        mock_send_mail.assert_called_once()
        args, kwargs = mock_send_mail.call_args
        self.assertIn('Welcome to ECHO', kwargs['message'])

    @patch('users.services.send_mail')
    def test_send_password_changed_email(self, mock_send_mail):
        EmailService.send_password_changed_email(self.user)
        mock_send_mail.assert_called_once()

    @patch('users.services.send_mail')
    def test_send_email_exception(self, mock_send_mail):
        mock_send_mail.side_effect = Exception("SMTP Error")
        result = EmailService._send_email('test@example.com', 'Subject', 'Body')
        self.assertFalse(result)


class SecurityServiceTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='security@example.com',
            password='testpass123'
        )

    def test_handle_failed_login(self):
        self.assertEqual(self.user.login_attempts, 0)
        SecurityService.handle_failed_login(self.user)
        self.user.refresh_from_db()
        self.assertEqual(self.user.login_attempts, 1)

    def test_handle_failed_login_locks_account(self):
        for _ in range(5):
            SecurityService.handle_failed_login(self.user)
        self.user.refresh_from_db()
        self.assertEqual(self.user.login_attempts, 5)
        self.assertIsNotNone(self.user.account_locked_until)

    def test_handle_successful_login(self):
        self.user.login_attempts = 3
        self.user.account_locked_until = timezone.now() + timedelta(minutes=10)
        self.user.save()

        SecurityService.handle_successful_login(self.user)
        self.user.refresh_from_db()
        self.assertEqual(self.user.login_attempts, 0)
        self.assertIsNotNone(self.user.last_login)
        self.assertIsNone(self.user.account_locked_until)

    @patch('users.services.timezone')
    def test_check_account_security(self, mock_timezone):
        from rest_framework.exceptions import PermissionDenied
        
        # Test locked account
        now = timezone.now()
        mock_timezone.now.return_value = now
        
        self.user.account_locked_until = now + timedelta(minutes=10)
        self.user.save()
        
        with self.assertRaises(PermissionDenied):
            SecurityService.check_account_security(self.user, '127.0.0.1', 'Mozilla')
            
        # Test unlocked account
        self.user.account_locked_until = now - timedelta(minutes=10)
        self.user.save()
        SecurityService.check_account_security(self.user, '127.0.0.1', 'Mozilla')

class UserStatsServiceTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='stats@example.com',
            password='testpass123',
            user_type='CUSTOMER'
        )
        self.admin = User.objects.create_user(
            email='admin_stats@example.com',
            password='testpass123',
            user_type='ADMIN'
        )

    @patch('users.services.UserStatsService._get_user_specific_stats')
    def test_get_dashboard_stats_customer(self, mock_get_user_stats):
        mock_get_user_stats.return_value = {'documents': 5}
        stats = UserStatsService.get_dashboard_stats(self.user)
        self.assertEqual(stats, {'documents': 5})
        mock_get_user_stats.assert_called_once_with(self.user)

    @patch('users.services.UserStatsService._get_admin_statistics')
    def test_get_dashboard_stats_admin(self, mock_get_admin_stats):
        mock_get_admin_stats.return_value = {'total_users': 10}
        stats = UserStatsService.get_dashboard_stats(self.admin)
        self.assertEqual(stats, {'total_users': 10})
        mock_get_admin_stats.assert_called_once_with(self.admin)



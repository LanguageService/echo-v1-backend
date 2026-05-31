from django.test import TestCase
from django.core import mail
from django.contrib.auth import get_user_model
from notification.services.email import EmailDispatcher

User = get_user_model()

class EmailDispatcherSmokeTestCase(TestCase):
    """
    Smoke tests for the EmailDispatcher to ensure templates render correctly
    and emails are successfully handed off to Django's outbox.
    """
    
    def setUp(self):
        self.user = User.objects.create_user(
            email='testemail@example.com',
            password='testpass123'
        )
        self.user.first_name = 'John'
        self.user.last_name = 'Doe'
        self.user.save()

    def test_send_onboarding_email(self):
        """Test the onboarding welcome email."""
        EmailDispatcher.send_onboarding(self.user)
        
        self.assertEqual(len(mail.outbox), 1)
        sent_email = mail.outbox[0]
        
        self.assertEqual(sent_email.to, [self.user.email])
        self.assertIn("Welcome to ECHO 🎉", sent_email.subject)
        
        # Verify HTML body is present
        self.assertTrue(len(sent_email.alternatives) > 0)
        html_content = sent_email.alternatives[0][0]
        self.assertIn("Welcome", html_content)
        self.assertIn("John", html_content)

    def test_send_verification_email(self):
        """Test the OTP verification email."""
        EmailDispatcher.send_verification(self.user, "123456")
        
        self.assertEqual(len(mail.outbox), 1)
        sent_email = mail.outbox[0]
        
        self.assertEqual(sent_email.to, [self.user.email])
        self.assertIn("Verify your ECHO email address", sent_email.subject)
        
        html_content = sent_email.alternatives[0][0]
        self.assertIn("123456", html_content)

    def test_send_password_reset_email(self):
        """Test the password reset email."""
        EmailDispatcher.send_password_reset(self.user, "654321")
        
        self.assertEqual(len(mail.outbox), 1)
        sent_email = mail.outbox[0]
        
        self.assertEqual(sent_email.to, [self.user.email])
        self.assertIn("Reset your ECHO password", sent_email.subject)
        
        html_content = sent_email.alternatives[0][0]
        self.assertIn("654321", html_content)

    def test_send_document_done_email(self):
        """Test the document processing complete email."""
        EmailDispatcher.send_document_done(
            user=self.user,
            doc_name="invoice.pdf",
            result_url="https://frontend.com/docs/1",
            page_count=5,
            processing_time=10.5
        )
        
        self.assertEqual(len(mail.outbox), 1)
        sent_email = mail.outbox[0]
        
        self.assertEqual(sent_email.to, [self.user.email])
        self.assertIn("✅ Your document 'invoice.pdf' is ready", sent_email.subject)
        
        html_content = sent_email.alternatives[0][0]
        self.assertIn("invoice.pdf", html_content)
        self.assertIn("10.5", str(html_content))

"""
Email Dispatcher — unified public API for all outbound emails.

Usage
-----
from notification.services.email import EmailDispatcher

EmailDispatcher.send_onboarding(user)
EmailDispatcher.send_verification(user, otp_code="123456")
EmailDispatcher.send_password_reset(user, otp_code="654321")
EmailDispatcher.send_document_done(user, doc_name="contract.pdf", result_url="https://...")
"""

from django.conf import settings
from django.template.loader import render_to_string
from django.core.mail import EmailMultiAlternatives
from loguru import logger


class EmailDispatcher:
    """
    Single entry-point for sending all transactional emails.
    Uses Django's standard email backends (configured via SMTP settings).
    """

    # ── Internal helper ───────────────────────────────────────────────────────

    @classmethod
    def _dispatch(
        cls,
        to: str,
        subject: str,
        template: str,
        context: dict,
    ) -> bool:
        """Render a template and send via standard Django mail backend."""
        try:
            html = render_to_string(template, context)
            plain_text = "Please view this email in an HTML-capable mail client."
            
            from_addr = getattr(settings, "DEFAULT_FROM_EMAIL", getattr(settings, "EMAIL_HOST_USER", ""))
            
            msg = EmailMultiAlternatives(
                subject=subject,
                body=plain_text,
                from_email=from_addr,
                to=[to],
            )
            msg.attach_alternative(html, "text/html")
            msg.send(fail_silently=False)
            logger.info(f"[EmailDispatcher] Email sent → {to} (Subject: {subject})")
            return True
        except Exception as exc:
            logger.error(f"[EmailDispatcher] Failed to send email to {to}: {exc}")
            return False

    # ── Public named senders ──────────────────────────────────────────────────

    @classmethod
    def send_onboarding(cls, user) -> bool:
        """
        Send a welcome / onboarding email after account creation.
        """
        return cls._dispatch(
            to=user.email,
            subject="Welcome to ECHO 🎉",
            template="emails/onboarding.html",
            context={
                "user": user,
                "full_name": user.get_full_name() or user.email,
                "login_url": getattr(settings, "FRONTEND_BASE_URL", "#") + "/login",
            },
        )

    @classmethod
    def send_verification(cls, user, otp_code: str) -> bool:
        """
        Send an email verification OTP.
        """
        return cls._dispatch(
            to=user.email,
            subject="Verify your ECHO email address",
            template="emails/email_verification.html",
            context={
                "user": user,
                "full_name": user.get_full_name() or user.email,
                "otp_code": otp_code,
                "expiry_minutes": getattr(settings, "OTP_EXPIRY_MINUTES", 10),
            },
        )

    @classmethod
    def send_password_reset(cls, user, otp_code: str) -> bool:
        """
        Send a password reset OTP.
        """
        return cls._dispatch(
            to=user.email,
            subject="Reset your ECHO password",
            template="emails/reset_password.html",
            context={
                "user": user,
                "full_name": user.get_full_name() or user.email,
                "otp_code": otp_code,
                "expiry_minutes": getattr(settings, "OTP_EXPIRY_MINUTES", 10),
            },
        )

    @classmethod
    def send_document_done(
        cls,
        user,
        doc_name: str,
        result_url: str | None = None,
        page_count: int | None = None,
        processing_time: float | None = None,
    ) -> bool:
        """
        Notify the user that a heavy document processing job has completed.
        """
        frontend_base = getattr(settings, "FRONTEND_BASE_URL", "#")
        return cls._dispatch(
            to=user.email,
            subject=f"✅ Your document '{doc_name}' is ready",
            template="emails/document_processing_done.html",
            context={
                "user": user,
                "full_name": user.get_full_name() or user.email,
                "doc_name": doc_name,
                "result_url": result_url or frontend_base + "/dashboard",
                "page_count": page_count,
                "processing_time": processing_time,
            },
        )


__all__ = ["EmailDispatcher"]

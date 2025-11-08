import requests
from django.conf import settings
from django.core.mail import send_mail
from loguru import logger


class EmailService:
    def __init__(self, payload):
        self.subject = payload["subject"]
        self.message = payload["message"]
        self.recipient = payload["user_email"]
        self.recipient_list = [self.recipient]

    def send(self):
        """
        Send email to the recipient
        """
        self.send_email_via_internal
        return True

    def send_email_via_internal(self):
        """
        Send email to the recipient
        """
        try:
            send_mail(
                subject=self.subject,
                message=self.message,
                from_email=settings.EMAIL_HOST_USER,
                recipient_list=self.recipient_list,
                fail_silently=False,
            )
        except Exception as e:
            logger.error(f"Error sending email: {e}")
            return False
        return True

    # we could have over email services here
    # def send_email_via_sendgrid(self):
    #     pass
    # def send_email_via_mailgun(self):
    #     pass


def _send_email(recipient, subject="", body_html=""):
    EMAIL_API = "https://api.zeptomail.com/v1.1/email"

    headers = {"Authorization": f"Zoho-enczapikey {settings.EMAIL_HOST_PASSWORD}"}
    paylaod = {
        "from": {"address": settings.EMAIL_FROM},
        "to": [{"email_address": {"address": recipient}}],
        "subject": subject,
        "htmlbody": body_html,
    }

    try:
        res = requests.post(EMAIL_API, json=paylaod, headers=headers)
        logger.info(f"Email API call response >>> {res.status_code} {res.json()}")
    except Exception as e:
        logger.error(f"Error sending email: {e}")


def send_email(enqueue=False, *args, **kwargs):
    if settings.REDIS_ENABLED and enqueue:
        from django_rq import get_queue

        queue = get_queue(settings.RQ_SENDER_QUEUE)
        queue.enqueue(_send_email, *args, **kwargs)

    else:
        _send_email(*args, **kwargs)

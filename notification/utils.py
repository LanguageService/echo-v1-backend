from .models import NotificationPlatform, Platform
from .services import SMSService, EmailService, WhatsAppService
from loguru import logger


class SendNotification:
    def __init__(self, user, payload):
        self.user = user
        self.link = payload["link"]
        self.messages = payload["message"]
        self.subject = payload["subject"]
        self.other_message = self.messages["others"]
        self.email_message = self.messages["email"]

    def get_user_notification_platform_status(self):
        """
        Get user active notification platform status
        """
        user_active_notify_platforms = NotificationPlatform.objects.filter(
            user=self.user, status=True
        ).values_list("platform", flat=True)
        return user_active_notify_platforms

    def send(self):
        logger.info(
            f"Sending notification to {self.user} with message: {self.other_message} via {self.user}"
        )

        matched_platforms = self.get_user_notification_platform_status()
        if not matched_platforms:
            return False, "No active notification platform found"

        # TODO : Wrap each of the send methods  in a background task
        if Platform.SMS.value in matched_platforms:
            # send via SMS
            logger.info(
                f"Sending SMS to {self.user.phone} with message: {self.other_message}"
            )
            sms_service = SMSService(self.user.phone, self.other_message)
            sms_service.send()

        if Platform.EMAIL.value in matched_platforms:
            # send via email
            logger.info(f"Sending Email to {self.user.email}")

            email_payload = {
                "subject": self.subject,
                "user_email": self.user.email,
                "message": self.email_message,
                "user_first_name": self.user.first_name,
                "user_last_name": self.user.last_name,
                "link": self.link,
            }

            email_service = EmailService(email_payload)
            email_service.send()

        if Platform.WHATSAPP.value in matched_platforms:
            # send via whatsapp
            logger.info(
                f"Sending Whatsapp to {self.user.phone} with message: {self.other_message}"
            )
            whatsapp_service = WhatsAppService(self.user.phone, self.other_message)
            whatsapp_service.send()

        return True

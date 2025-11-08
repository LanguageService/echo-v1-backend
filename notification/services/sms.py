from loguru import logger


class SMSService:
    def __init__(self, phone_number, message):
        self.phone_number = phone_number
        self.message = message

    def send(self):
        """
        Send SMS to the phone number
        """
        self.send_via_twilio()

    def send_via_twilio(self):
        """
        Send SMS to the phone number via Twilio
        """
        logger.info(
            f"Sending SMS using Twilio to {self.phone_number} with message: {self.message}"
        )
        pass

    # we could have other SMS services here
    def send_via_termii(self):
        logger.info(
            f"Sending SMS using Termii to {self.phone_number} with message: {self.message}"
        )
        pass

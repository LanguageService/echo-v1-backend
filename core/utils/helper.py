import random
import re
import string
from datetime import datetime
from django.conf import settings

from rest_framework.pagination import PageNumberPagination
from django.core.exceptions import ValidationError

from notification.services.email import send_email


def get_slug(name):
    return name.replace(" ", "-").lower() if name else ""


# This class returns the string needed to generate the key
class generateKey:
    @staticmethod
    def returnValue(phone):
        return f"{phone}{datetime.date(datetime.now())}{settings.SECRET_KEY}"


class CustomPagination(PageNumberPagination):
    page_size = settings.REST_FRAMEWORK['PAGE_SIZE']
    page_size_query_param = settings.REST_FRAMEWORK['PAGE_SIZE_PARAM']
    max_page_size = settings.REST_FRAMEWORK['MAX_PAGE_SIZE']


def get_random_string(length):
    # choose from all letter and digits
    letters = string.ascii_letters + string.digits
    result_str = "".join(random.choice(letters) for i in range(length))
    return result_str


def get_current_unix_timestamp():
    return int(datetime.now().timestamp())


def format_phone_number(phone_number):
    if not phone_number or len(phone_number) < 2:
        return None

    if len(phone_number) > 2 and phone_number[0] == "+":
        return phone_number[1:]

    elif len(phone_number) > 2 and phone_number[:3] == "234":
        return phone_number

    elif len(phone_number) > 2 and phone_number[:3] != "234" and phone_number[0] != "+":
        return f"234{phone_number[1:]}"


def validate_phone(value):
    pattern = re.compile(r"^\+?1?\d{9,15}$")
    if not bool(pattern.match(value)):
        raise ValidationError(
            _(
                "Invalid! Phone number must be entered in the format: '+999999999'. Up to 15 digits allowed."
            ),
            params={"value": value},
        )


def custom_normalize_email(email):
    return email.strip().lower()


def send_token(email, otp_obj, username=None):
    token_type = otp_obj.token_type
    token = otp_obj.token
    salutation = f"Dear {username}" if username else "Good day"

    body = f"""
    {salutation},

    Your {token_type.lower()} code is {token}. Please ignore if you did not request for this. 
    """

    send_email(
        recipient=email, subject=f"{token_type} One Time Password", body_html=body
    )

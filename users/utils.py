import pyotp
import base64
from django.conf import settings
from django.db.models import Q
from .models import User
from core.utils import error_401, error_400, generateKey


def generate_otp(contact, verification=False):

    keygen = generateKey()
    key = base64.b32encode(keygen.returnValue(contact).encode())

    if verification == True:
        hotp = pyotp.HOTP(key)
        user = User.objects.filter(Q(email=contact) | Q(phone=contact)).first()
        otp_data = hotp.at(int(user.id))
        return otp_data

    OTP = pyotp.TOTP(key, interval=settings.PASSWORD_OTP_TIMEOUT)
    otp_data = OTP.now()

    return otp_data


def user_deletion(request, user):

    # Only the user can delete him/herself , or member of the org, or  superadmin

    if user.user_type not in [User.SUPER_ADMIN, User.ADMIN, User.CUSTOMER]:
        if user.deleted_by:
            return False, error_400, "User does not exist"
        user.archive()
        user.deleted_by = request.user.id
        user.save()
        return True, "", ""

    else:
        False, error_401, "You do not have the right permission"

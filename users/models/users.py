import random

from django.db import models
from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from rest_framework_simplejwt.tokens import RefreshToken

from core.model import BaseModel
from ..manager import CustomUserManager
from .. import choices


# Create your models here.
class User(AbstractUser, BaseModel):

    ADMIN = "admin"
    CUSTOMER = "customer"
    SUPER_ADMIN = "super_admin"


    MALE = "male"
    FEMALE = "female"

    GENDER = (
        (MALE, MALE),
        (FEMALE, FEMALE),
    )

    USER_TYPE = (
        (ADMIN, ADMIN),
        (CUSTOMER, CUSTOMER),
        (SUPER_ADMIN, SUPER_ADMIN),
    )

    VISIT_TYPE = (
        ("STUDY", "STUDY"),
        ("BUSINESS", "BUSINESS"),
        ("PERSONAL", "PERSONAL"),
        ("TOURIST", "TOURIST"),
        ("RELOCATION", "RELOCATION"),
        ("OTHER", "OTHER"),

    )

    

    first_name = models.CharField(max_length=255)
    last_name = models.CharField(max_length=255)
    username = models.CharField(max_length=150, null=True, blank=True)
    email = models.EmailField(unique=True)
    gender = models.CharField(max_length=6, choices=GENDER)
    user_type = models.CharField(max_length=15, choices=USER_TYPE)
    phone = models.CharField(max_length=15, null=True, blank=True)
    origin_country = models.CharField(max_length=255, null=True, blank=True)
    resident_country = models.CharField(max_length=255, null=True, blank=True)
    occupation = models.CharField(max_length=255, null=True, blank=True)
    visit_type = models.CharField(max_length=255,choices=VISIT_TYPE, null=True, blank=True)
    city = models.CharField(max_length=255, null=True, blank=True)
    state = models.CharField(max_length=255, null=True, blank=True)
    address = models.TextField(null=True, blank=True)
    profile_picture = models.ImageField(
        upload_to="profile_pictures/", null=True, blank=True
    )
    date_of_birth = models.DateField(null=True, blank=True)
    password = models.CharField(max_length=255)
    address = models.TextField(null=True, blank=True)
    is_active = models.BooleanField(default=False)
    is_verified = models.BooleanField(default=False)
    deleted_by = models.IntegerField(null=True, blank=True)

     # Account security
    login_attempts = models.IntegerField(default=0)
    last_failed_login = models.DateTimeField(blank=True, null=True)
    account_locked_until = models.DateTimeField(blank=True, null=True)


    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = CustomUserManager()

    def __str__(self) -> str:
        return f"{self.last_name} {self.first_name}"

    def token(self):
        refresh = RefreshToken.for_user(self)
        return {"refresh": str(refresh), "access": str(refresh.access_token)}

    # # def has_paid_subscription(self):
    # #     return self.subscriptions.filter(
    # #         next_billing_date__gt=timezone.now(), status=SubscriptionStatus.ACTIVE
    # #     ).exists()
    

    # def has_free_subscription(self):
    #     return not self.article_histories.exists()

    # def has_active_subscription(self):
    #     return self.has_paid_subscription() or self.has_free_subscription()



USER_NOT_FOUND = _("User not found")


class OneTimePassword(BaseModel):
    email = models.EmailField(_("email"))
    token = models.CharField(max_length=250, unique=True)
    token_type = models.CharField(max_length=20, choices=choices.TokenType.choices)
    used = models.BooleanField(default=False)
    created = models.DateTimeField(
        auto_now_add=True,
        editable=False,
        null=True,
        verbose_name=_("created on"),
    )
    modified = models.DateTimeField(
        auto_now=True,
        editable=False,
        null=True,
        verbose_name=_("modified on"),
    )
    has_expired = models.BooleanField(default=False)


    def check_if_expired(self): # <- This is now an instance method
        seconds_elapsed = (timezone.now() - self.created).total_seconds()
        hours_elapsed = seconds_elapsed / 3600

        has_expired = hours_elapsed > settings.VERIFICATION_OTP_TIMEOUT
        if has_expired:
            self.has_expired = True
            self.save()
        return has_expired

    @staticmethod
    def cleanup_expired_otps():
        """Clean up expired OTPs (can be run as a periodic task)"""
        expired_otps = OneTimePassword.objects.filter(
            expires_at__lt=timezone.now()
        )
        count = expired_otps.count()
        expired_otps.delete()
        return count
    
    

    @classmethod
    def generate_otp(cls, email, token_type=choices.TokenType.REGISTRATION):
        otp, _ = cls.objects.update_or_create(
            email=email,
            token_type=token_type,
            defaults={
                "token_type": token_type,
                "token": random.randint(100000, 999999),
                "created": timezone.now(),
                "used": False,
            },
        )
        return otp

    @classmethod
    def verify_token(cls, token, token_type=choices.TokenType.REGISTRATION, email=None):

        q = cls.objects.filter(token=token)

        if email:
            q = q.filter(email=email)

        otp = q.first()
        
        if not otp:
            return False, _("Token is invalid")

        if otp.check_if_expired():
            return False, _("Token has expired")

        if otp.used:
            return False, _("Token already used")

        return True, _("Token verified successfuly")

    @classmethod
    def update_token(cls, token, token_type, is_used):
        cls.objects.filter(token=token, token_type=token_type).update(used=is_used)

    @classmethod
    def get_user(cls, token,email,token_type=None):
        otp = cls.objects.filter(token=token, email=email).first()
        if otp:
            return User.objects.filter(email=otp.email).first()

        return None

    @classmethod
    def activate_user(
        cls, token, token_type=choices.TokenType.REGISTRATION, email=None
    ):

        status, msg = cls.verify_token(token, token_type, email)
        if not status:
            return status, msg

        user = cls.get_user(token=token, email=email)
        if not user:
            return False, USER_NOT_FOUND

        user.is_verified = True
        user.save()

        cls.update_token(token, token_type, is_used=True)

        return True, user.token()

    @classmethod
    def set_password(
        cls,
        token,
        password,
        token_type=choices.TokenType.RESET_PASSWORD,
        email=None,
    ):
        status, msg = cls.verify_token(token, token_type, email)
        if not status:
            return status, msg

        user = cls.get_user(token, token_type)
        if not user:
            return False, USER_NOT_FOUND

        user.set_password(password)
        user.save()

        cls.update_token(token, token_type, is_used=True)
        return True, _("User password set successfully")

    @classmethod
    def verify_login(
        cls,
        token,
        token_type=choices.TokenType.LOGIN,
        email=None,
    ):
        status, msg = cls.verify_token(token, token_type, email)
        if not status:
            return status, msg

        user = cls.get_user(token, token_type)
        if not user:
            return False, USER_NOT_FOUND

        cls.update_token(token, token_type, is_used=True)
        return True, user

    def use(self):
        self.used = True
        self.save()

    @staticmethod
    def cleanup_expired_otps():
        """Clean up expired OTPs (can be run as a periodic task)"""
        expired_otps = EmailVerificationOTP.objects.filter(
            expires_at__lt=timezone.now()
        )
        count = expired_otps.count()
        expired_otps.delete()
        return count

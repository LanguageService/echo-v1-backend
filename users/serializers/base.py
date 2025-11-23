from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.utils.translation import gettext_lazy as _
from rest_framework import exceptions, serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from core.utils import send_token
from ..choices import TokenType
from ..models import OneTimePassword


User = get_user_model()


class LoginSerializer(TokenObtainPairSerializer):
    email = serializers.EmailField()
    password = serializers.CharField()

    def validate(self, attrs):
        data = super().validate(attrs)
        email = attrs.get("email")
        password = attrs.get("password")
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            raise exceptions.AuthenticationFailed(
                _("Account with this email not found."),
                code="authentication",
            )
        if not user.check_password(password):
            raise exceptions.AuthenticationFailed(
                _("Incorrect password."),
                code="authentication",
            )
        
        new_data = {
            "code": 200,
            "message": "User Login",
            "is_verified": user.is_verified,
            "token": {},
            
        }
        # TODO: background task for email sending
        if not user.is_verified:
            otp_obj = OneTimePassword.generate_otp(
                attrs["email"], token_type=TokenType.LOGIN
            )
            print(f"OTP:{otp_obj.token} email: {email}")
            send_token(email, otp_obj)
        
        # Only generate token if verified
        else:
            refresh = self.get_token(user)
            new_data["token"] = {
                "refresh": str(refresh),
                "access": str(refresh.access_token),
            }
            
        return new_data

    # @classmethod
    # def get_token(cls, user):
    #     if not user.is_verified:
    #         return None
            
    #     token = super().get_token(user)
    #     # Add custom data with token[key] = val
    #     return token


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField()
    new_password = serializers.CharField(validators=[validate_password])

    def validate(self, attrs):
        user = self.context.get("request").user
        if not user.check_password(attrs["old_password"]):
            raise serializers.ValidationError({"old_password": _("Wrong password")})

        if attrs["old_password"] == attrs["new_password"]:
            raise serializers.ValidationError(
                {"new_password": _("Same as old password")}
            )

        return super().validate(attrs)


class OTPVerificationSerializer(serializers.Serializer):
    otp_code = serializers.RegexField(regex=r"^\d{6}$")
    email = serializers.EmailField()


class EmailSerializer(serializers.Serializer):
    email = serializers.EmailField(required=False)

    def validate(self, attrs):
        email = attrs["email"]
        user = User.objects.filter(email=email).first()
        if not user:
            raise serializers.ValidationError({"email": "User does not exist"})
        if not user.is_active:  # User account is blocked/deleted
            raise serializers.ValidationError({"email": "Account not found"})

        return super().validate(attrs)


class ResetPasswordSerializer(serializers.Serializer):
    otp_code = serializers.RegexField(regex=r"^\d{6}$")
    password = serializers.CharField(validators=[validate_password])
    confirm_password = serializers.CharField()


class ConfirmResetTokenSerializer(serializers.Serializer):
    otp_code = serializers.CharField()
    email = serializers.EmailField(required=False)

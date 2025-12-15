from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.exceptions import InvalidToken, AuthenticationFailed
from drf_spectacular.utils import extend_schema

from core.utils import error_400, send_token, serializer_errors,error_401
from .. import choices, models, serializers


User = get_user_model()


class HealthCheckView(GenericAPIView):
    permission_classes = [AllowAny]
    serializer_class = []

    def get(self, request):
        return Response(status=status.HTTP_200_OK)


class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = serializers.LoginSerializer

    def post(self, request, *args, **kwargs):
        try:
            return super().post(request, *args, **kwargs)
        except AuthenticationFailed as e:
            return error_401(str(e))
        except InvalidToken as e:
            return error_400(str(e))
        except Exception as e:
            # Handle other potential exceptions
            return error_400(str(e))


@extend_schema(tags=["Auth"])
class AuthViewSet(GenericViewSet):
    queryset = User.objects.all()
    serializer_class = serializers.UserSerializer
    permission_classes = [IsAuthenticated]

    def send_activation_mail(self, user):
        otp_obj = models.OneTimePassword.generate_otp(user.email)
        print(f"OTP: {otp_obj.token}")
        send_token(user.email, otp_obj, user.first_name)
        return otp_obj.token

    @action(
        detail=False,
        methods=["post"],
        authentication_classes=[],
        permission_classes=[AllowAny],
        serializer_class=serializers.CustomerRegistrationSerializer,
        url_path="customer/user",
    )
    @extend_schema(tags=["Auth"])
    def create_customer_user(self, request):
        serializer = self.get_serializer(data=request.data)
        if not serializer.is_valid():
            errors = serializer.errors
            # Check if the error is specifically because the email already exists.
            if 'email' in errors and any('already exist' in e for e in errors['email']):
                try:
                    user = User.objects.get(email=request.data.get('email'))
                    otp = self.send_activation_mail(user) if not user.is_verified else None
                    data = {
                        'is_verified': user.is_verified,
                        'otp': otp  # TODO: remove
                    }
                    return error_400("User already exist", data)
                except User.DoesNotExist:
                    # This is unlikely but handles a race condition.
                    return error_400(serializer_errors(errors))
            
            return error_400(serializer_errors(errors))

        user = serializer.save()
        otp = self.send_activation_mail(user)
        user_data = serializers.UserSerializer(user).data
        return Response(
            {
                "code": status.HTTP_201_CREATED,
                "status": "success",
                "message": "User created successfully, Check email for verification code",
                "data": {
                    "token": user.token(),
                    "otp": otp,  # This is temporary still we have email or sms service up
                    "user": user_data
                }
            }
        )

    @action(
        detail=False,
        methods=["post"],
        permission_classes=[IsAuthenticated],
        serializer_class=serializers.AdminUserRegistrationSerializer,
        url_path="admin/user",
    )
    @extend_schema(tags=["Auth"])
    def create_admin_user(self, request):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            self.send_activation_mail(user)
            return Response(
                {
                    "code": status.HTTP_201_CREATED,
                    "status": "success",
                    "message": "Admin User created successfully, Check email for verification code",
                    "token": user.token(),
                },
                status=status.HTTP_201_CREATED,
            )
        default_errors = serializer.errors
        error_message = serializer_errors(default_errors)

        return error_400(error_message)

    @action(
        detail=False,
        methods=["post"],
        authentication_classes=[],
        permission_classes=[AllowAny],
        serializer_class=serializers.SuperAdminUserRegistrationSerializer,
        url_path="super/user",
    )
    @extend_schema(tags=["Auth"])
    def create_super_admin_user(self, request):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            self.send_activation_mail(user)
            return Response(
                {
                    "code": status.HTTP_201_CREATED,
                    "status": "success",
                    "message": "Super Admin User created successfully, Check email for verification code",
                    "token": user.token(),
                },
                status=status.HTTP_201_CREATED,
            )
        default_errors = serializer.errors
        error_message = serializer_errors(default_errors)

        return error_400(error_message)

    @action(
        methods=["POST"],
        detail=False,
        url_path="resend-otp",
        serializer_class=serializers.EmailSerializer,
        authentication_classes=[],
        permission_classes=[],
    )
    @extend_schema(tags=["Auth"])
    def resend_otp(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            email = serializer.validated_data["email"]
            if not User.objects.filter(email=email, is_verified=False).exists():
                return error_400("User with email does not exist")

            otp = models.OneTimePassword.generate_otp(email)
            # TODO: Send email to user
            send_token(email, otp)
            return Response(
                {
                    "code": status.HTTP_200_OK,
                    "status": "success",
                    "message": "Check email for verification code",
                },
                status=status.HTTP_200_OK,
            )
        return error_400("An error occurred")

    @action(
        methods=["POST"],
        detail=False,
        url_path="change-password",
        serializer_class=serializers.ChangePasswordSerializer,
        permission_classes=[IsAuthenticated],
    )
    @extend_schema(tags=["Auth"])
    def change_password(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            user = request.user
            user.set_password(serializer.validated_data["new_password"])
            user.save()
            return Response(
                {"success": True, "message": _("Password updated successfully.")},
                status=status.HTTP_200_OK,
            )
        default_errors = serializer.errors
        error_message = serializer_errors(default_errors)
        return error_400(error_message)

    @action(
        methods=["post"],
        detail=False,
        url_path="verify-otp",
        serializer_class=serializers.OTPVerificationSerializer,
        authentication_classes=[],
        permission_classes=[],
    )
    @extend_schema(tags=["Auth"])
    def verify_otp(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            email = serializer.validated_data["email"]
            otp_code = serializer.validated_data["otp_code"]
            print(f"email: {email}")
            success, msg = models.OneTimePassword.activate_user(token=otp_code,email=email)
            if not success:
                return error_400(msg)

            return Response(
                {
                    "code": 200,
                    "status": "success",
                    "token": msg,
                },
                status=status.HTTP_200_OK,
            )
        else:
            default_errors = serializer.errors
            error_message = serializer_errors(default_errors)
            return error_400(error_message)

    @action(
        methods=["POST"],
        detail=False,
        url_path="reset-password/initiate",
        authentication_classes=[],
        permission_classes=[],
        serializer_class=serializers.EmailSerializer,
    )
    @extend_schema(tags=["Auth"])
    def initiate_reset_password(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            email = serializer.validated_data["email"]
            otp_obj = models.OneTimePassword.generate_otp(
                email,
                token_type=choices.TokenType.RESET_PASSWORD,
            )

            send_token(email, otp_obj)
            return Response(
                {
                    "code": status.HTTP_200_OK,
                    "status": "Email Sent Successful",
                    "token": otp_obj.token,
                },
                status=status.HTTP_200_OK,
            )

        default_errors = serializer.errors
        error_message = serializer_errors(default_errors)
        return error_400(error_message)

    @action(
        methods=["POST"],
        detail=False,
        url_path="reset-password",
        serializer_class=serializers.ResetPasswordSerializer,
        authentication_classes=[],
        permission_classes=[],
    )
    @extend_schema(tags=["Auth"])
    def reset_password(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():

            success, msg = models.OneTimePassword.set_password(
                token=serializer.validated_data["otp_code"],
                password=serializer.validated_data["password"],
            )
            if not success:
                return error_400(msg)

            return Response(
                {
                    "code": status.HTTP_200_OK,
                    "message": msg,
                },
                status=status.HTTP_200_OK,
            )

        default_errors = serializer.errors
        error_message = serializer_errors(default_errors)
        return error_400(error_message)

    @action(
        methods=["post"],
        detail=False,
        url_path="login/verify",
        serializer_class=serializers.OTPVerificationSerializer,
        authentication_classes=[],
        permission_classes=[],
    )
    @extend_schema(tags=["Auth"])
    def verify_login(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            otp_code = serializer.validated_data["otp_code"]
            success, user = models.OneTimePassword.verify_login(otp_code)
            
            if not success:
                return error_400("Unable to verify token")

            return Response(
                {
                    "code": 200,
                    "status": "success",
                    "token": user.token(),
                },
                status=status.HTTP_200_OK,
            )
        else:
            default_errors = serializer.errors
            error_message = serializer_errors(default_errors)
            return error_400(error_message)

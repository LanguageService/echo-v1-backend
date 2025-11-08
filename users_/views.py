"""
User Views

API views for user authentication, registration, and profile management.
"""

from rest_framework import status, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.generics import RetrieveUpdateAPIView, CreateAPIView, GenericAPIView
from dj_rest_auth.views import LoginView as BaseLoginView, LogoutView as BaseLogoutView
from django.contrib.auth import get_user_model, login as django_login
from django.utils import timezone
from drf_spectacular.utils import extend_schema, OpenApiResponse
from dj_rest_auth.jwt_auth import set_jwt_cookies

from .models import UserProfile
from .serializers import (
    CustomRegisterSerializer, CustomLoginSerializer, EmailVerificationSerializer, ResendOTPSerializer, PasswordResetRequestSerializer,
    PasswordResetConfirmSerializer, ChangePasswordSerializer, UserProfileSerializer,
     UserDetailsSerializer
)
from ..users.services import UserAuthService, UserStatsService, SecurityService

User = get_user_model()


@extend_schema(
    tags=['Authentication'],
    summary='API Health Check',
    description='Check if the authentication API is running properly',
    responses={200: OpenApiResponse(description='API is healthy')}
)
@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def auth_health_check(request):
    """Health check endpoint for authentication API"""
    return Response({
        'status': 'healthy',
        'message': 'Authentication API is running',
        'timestamp': timezone.now(),
        'features': [
            'User Registration with Email Verification',
            'JWT Token Authentication',
            'OTP-based Password Reset',
            'User Profile Management',
            'Account Security Features'
        ]
    })


@extend_schema(
    tags=['Authentication'],
    summary='API Information',
    description='Get information about the authentication API endpoints and features',
    responses={200: OpenApiResponse(description='API information retrieved successfully')}
)
@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def auth_api_info(request):
    """Provide API information and available endpoints"""
    return Response({
        'api_name': 'OCR & Voice Translation Authentication API',
        'version': '1.0.0',
        'description': 'Complete user authentication system with email verification and OTP support',
        'endpoints': {
            'authentication': {
                'register': '/auth/registration/',
                'login': '/auth/login/',
                'logout': '/auth/logout/',
                'verify_email': '/auth/verify-email/',
                'resend_verification': '/auth/resend-verification/',
                'user_details': '/auth/user/',
            },
            'password_management': {
                'change_password': '/auth/password/change/',
                'reset_request': '/auth/password/reset/',
                'reset_confirm': '/auth/password/reset/confirm/',
            },
            'profile': {
                'profile': '/auth/profile/',
            },
            'tokens': {
                'refresh': '/auth/token/refresh/',
                'verify': '/auth/token/verify/',
            }
        },
        'features': [
            'Email-based registration with OTP verification',
            'JWT token authentication with refresh tokens',
            'OTP-based password reset system',
            'User profile management',
            'Account security and rate limiting',
            'API usage tracking',
            'Comprehensive error handling'
        ],
        'authentication': 'JWT Bearer Token',
        'documentation': '/api/schema/swagger-ui/'
    })


class CustomLoginView(GenericAPIView):
    """
    Custom login view that uses a self-contained serializer to authenticate
    and issue JWT tokens, bypassing dj-rest-auth's login flow.
    """
    serializer_class = CustomLoginSerializer
    permission_classes = [permissions.AllowAny]

    @extend_schema(
        tags=['Authentication'],
        summary='User Login',
        description='Authenticate user and return JWT tokens.',
    )
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']
        django_login(request, user)
        SecurityService.handle_successful_login(user, request.META.get('REMOTE_ADDR'))
        response = Response(serializer.data, status=status.HTTP_200_OK)
        from dj_rest_auth.app_settings import api_settings
        if api_settings.USE_JWT:
            set_jwt_cookies(response, serializer.validated_data['access_token'], serializer.validated_data['refresh_token'])
        return response


class CustomRegisterView(CreateAPIView):
    """
    Custom registration view that uses a self-contained serializer and service
    to handle user creation and email verification, independent of dj-rest-auth.
    """
    serializer_class = CustomRegisterSerializer
    permission_classes = [permissions.AllowAny]

    @extend_schema(
        tags=['Authentication'],
        summary='User Registration',
        description='Create a new user account. An email with a verification OTP will be sent.',
    )
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(
            {"detail": f"Verification OTP sent to {user.email}. Please verify your email to activate your account."},
            status=status.HTTP_201_CREATED
        )


class CustomLogoutView(BaseLogoutView):
    """Custom logout view"""
    
    @extend_schema(
        tags=['Authentication'],
        summary='User Logout',
        description='Logout user and invalidate tokens',
    )
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)


class EmailVerificationView(APIView):
    """View for email verification with OTP"""
    permission_classes = [permissions.AllowAny]
    
    @extend_schema(
        tags=['Authentication'],
        summary='Verify Email with OTP',
        description='Verify user email address using OTP code',
        request=EmailVerificationSerializer,
        responses={
            200: OpenApiResponse(description='Email verified successfully'),
            400: OpenApiResponse(description='Invalid OTP or validation error'),
        }
    )
    def post(self, request):
        serializer = EmailVerificationSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.validated_data['user']
            otp = serializer.validated_data['otp']
            
            if UserAuthService.verify_email(user, otp.otp_code):
                return Response({
                    'message': 'Email verified successfully',
                    'user': UserDetailsSerializer(user).data
                }, status=status.HTTP_200_OK)
            else:
                return Response({
                    'error': 'Email verification failed'
                }, status=status.HTTP_400_BAD_REQUEST)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ResendVerificationView(APIView):
    """View for resending verification OTP"""
    permission_classes = [permissions.AllowAny]
    
    @extend_schema(
        tags=['Authentication'],
        summary='Resend Verification OTP',
        description='Resend email verification OTP to user',
        request=ResendOTPSerializer,
        responses={
            200: OpenApiResponse(description='OTP sent successfully'),
            400: OpenApiResponse(description='Email already verified or user not found'),
        }
    )
    def post(self, request):
        serializer = ResendOTPSerializer(data=request.data)
        if serializer.is_valid():
            email = serializer.validated_data['email']
            purpose = serializer.validated_data['purpose']
            
            if purpose == 'verification':
                success, message = UserAuthService.resend_verification_otp(email)
            else:
                success, message = UserAuthService.request_password_reset(email)
            
            if success:
                return Response({'message': message}, status=status.HTTP_200_OK)
            else:
                return Response({'error': message}, status=status.HTTP_400_BAD_REQUEST)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class PasswordResetRequestView(APIView):
    """View for requesting password reset"""
    permission_classes = [permissions.AllowAny]
    
    @extend_schema(
        tags=['Password Management'],
        summary='Request Password Reset',
        description='Request password reset OTP via email',
        request=PasswordResetRequestSerializer,
        responses={
            200: OpenApiResponse(description='Reset code sent successfully'),
            400: OpenApiResponse(description='User not found or email not verified'),
        }
    )
    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        if serializer.is_valid():
            email = serializer.validated_data['email']
            success, message = UserAuthService.request_password_reset(email)
            
            if success:
                return Response({'message': message}, status=status.HTTP_200_OK)
            else:
                return Response({'error': message}, status=status.HTTP_400_BAD_REQUEST)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class PasswordResetConfirmView(APIView):
    """View for confirming password reset with OTP"""
    permission_classes = [permissions.AllowAny]
    
    @extend_schema(
        tags=['Password Management'],
        summary='Confirm Password Reset',
        description='Reset password using OTP code',
        request=PasswordResetConfirmSerializer,
        responses={
            200: OpenApiResponse(description='Password reset successfully'),
            400: OpenApiResponse(description='Invalid OTP or validation error'),
        }
    )
    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.validated_data['user']
            otp = serializer.validated_data['otp']
            new_password = serializer.validated_data['new_password']
            
            if UserAuthService.reset_password(user, otp.otp_code, new_password):
                return Response({
                    'message': 'Password reset successfully'
                }, status=status.HTTP_200_OK)
            else:
                return Response({
                    'error': 'Password reset failed'
                }, status=status.HTTP_400_BAD_REQUEST)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ChangePasswordView(APIView):
    """View for changing password"""
    permission_classes = [permissions.IsAuthenticated]
    
    @extend_schema(
        tags=['Password Management'],
        summary='Change Password',
        description='Change user password (requires authentication)',
        request=ChangePasswordSerializer,
        responses={
            200: OpenApiResponse(description='Password changed successfully'),
            400: OpenApiResponse(description='Invalid current password or validation error'),
        }
    )
    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            user = request.user
            new_password = serializer.validated_data['new_password']
            
            user.set_password(new_password)
            user.save()
            
            return Response({
                'message': 'Password changed successfully'
            }, status=status.HTTP_200_OK)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class UserProfileView(RetrieveUpdateAPIView):
    """View for user profile management"""
    serializer_class = UserProfileSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    @extend_schema(
        tags=['Profile'],
        summary='Get User Profile',
        description='Retrieve user profile information',
        responses={200: OpenApiResponse(description='Profile retrieved successfully')}
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)
    
    @extend_schema(
        tags=['Profile'],
        summary='Update User Profile',
        description='Update user profile information',
        responses={200: OpenApiResponse(description='Profile updated successfully')}
    )
    def put(self, request, *args, **kwargs):
        return super().put(request, *args, **kwargs)
    
    @extend_schema(
        tags=['Profile'],
        summary='Partially Update User Profile',
        description='Partially update user profile information',
        responses={200: OpenApiResponse(description='Profile updated successfully')}
    )
    def patch(self, request, *args, **kwargs):
        return super().patch(request, *args, **kwargs)
    
    def get_object(self):
        profile, created = UserProfile.objects.get_or_create(user=self.request.user)
        return profile

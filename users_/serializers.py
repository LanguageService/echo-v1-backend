"""
User Serializers

Serializers for user authentication, registration, and profile management.
"""

from rest_framework import serializers
from django.contrib.auth import get_user_model, authenticate
from django.contrib.auth.password_validation import validate_password as django_validate_password
from django.core.exceptions import ValidationError
from dj_rest_auth.registration.serializers import RegisterSerializer
from dj_rest_auth.serializers import UserDetailsSerializer as BaseUserDetailsSerializer
from rest_framework_simplejwt.tokens import RefreshToken
from .models import EmailVerificationOTP, UserProfile
import random
import string

User = get_user_model()


class UserDetailsSerializer(BaseUserDetailsSerializer):
    """Custom user details serializer"""
    
    profile_picture = serializers.ImageField(required=False)
    full_name = serializers.CharField(source='get_full_name', read_only=True)
    profile = serializers.SerializerMethodField()
    
    class Meta(BaseUserDetailsSerializer.Meta):
        fields = BaseUserDetailsSerializer.Meta.fields + (
            'first_name', 'last_name', 'phone_number', 'profile_picture',
            'email_verified', 'full_name', 'profile', 'date_joined'
        )
        read_only_fields = ('email', 'date_joined', 'email_verified', 'full_name')
    
    def get_profile(self, obj):
        """Get user profile data"""
        try:
            profile = obj.profile
            return {
                'bio': profile.bio,
                'location': profile.location,
                'website': profile.website,
                'preferred_language': profile.preferred_language,
                'timezone': profile.timezone,
                'email_notifications': profile.email_notifications,
                'sms_notifications': profile.sms_notifications,
            }
        except UserProfile.DoesNotExist:
            return None


class CustomRegisterSerializer(serializers.ModelSerializer):
    """
    Custom registration serializer that handles user creation and validation
    without depending on dj-rest-auth's registration flow.
    """
    password1 = serializers.CharField(
        style={'input_type': 'password'}, write_only=True, required=True
    )
    password2 = serializers.CharField(style={'input_type': 'password'}, write_only=True, required=True)
    first_name = serializers.CharField(max_length=30, required=False)
    last_name = serializers.CharField(max_length=30, required=False)
    phone_number = serializers.CharField(max_length=20, required=False)

    class Meta:
        model = User
        fields = ('email', 'first_name', 'last_name', 'phone_number', 'password1', 'password2')
        extra_kwargs = {
            'password1': {
                'write_only': True,
                'validators': [django_validate_password],
            },
            'email': {'required': True},
        }

    def validate(self, attrs):
        if attrs['password1'] != attrs['password2']:
            raise serializers.ValidationError({"password": "Password fields didn't match."})
        return super().validate(attrs)

    def create(self, validated_data):
        from ..users.services import UserAuthService
        user = UserAuthService.register_user(
            email=validated_data['email'],
            password=validated_data['password1'],
            first_name=validated_data.get('first_name', ''),
            last_name=validated_data.get('last_name', ''),
            phone_number=validated_data.get('phone_number', '')
        )
        return user


class CustomLoginSerializer(serializers.Serializer):
    """
    Custom login serializer that authenticates users with email and password,
    bypassing allauth's default verification checks and using our custom
    `email_verified` field.
    """
    email = serializers.EmailField(required=True)
    password = serializers.CharField(
        style={'input_type': 'password'},
        trim_whitespace=False,
        write_only=True,
        required=True
    )
    access = serializers.CharField(read_only=True, source='access_token', help_text="JWT Access Token")
    refresh = serializers.CharField(read_only=True, source='refresh_token', help_text="JWT Refresh Token")
    user = UserDetailsSerializer(read_only=True)

    def validate(self, attrs):
        email = attrs.get('email')
        password = attrs.get('password')

        if not email or not password:
            raise serializers.ValidationError(
                'Must include "email" and "password".',
                code='authorization'
            )

        request = self.context.get('request')
        user = authenticate(request=request, email=email, password=password)

        if not user:
            raise serializers.ValidationError('Unable to log in with provided credentials.', code='authorization')
        if not user.email_verified:
            raise serializers.ValidationError('E-mail is not verified.', code='authorization')
        if not user.is_active:
            raise serializers.ValidationError('User account is disabled.', code='authorization')

        refresh = RefreshToken.for_user(user)
        attrs['user'] = user
        attrs['access_token'] = str(refresh.access_token)
        attrs['refresh_token'] = str(refresh)
        return attrs


class EmailVerificationSerializer(serializers.Serializer):
    """Serializer for email verification with OTP"""
    
    email = serializers.EmailField()
    otp_code = serializers.CharField(max_length=6, min_length=6)
    
    def validate(self, attrs):
        email = attrs.get('email')
        otp_code = attrs.get('otp_code')
        
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            raise serializers.ValidationError('User with this email does not exist.')
        
        # Find valid OTP
        otp = EmailVerificationOTP.objects.filter(
            user=user,
            otp_code=otp_code,
            purpose='verification',
            is_used=False
        ).first()
        
        if not otp or not otp.is_valid():
            raise serializers.ValidationError('Invalid or expired OTP.')
        
        attrs['user'] = user
        attrs['otp'] = otp
        return attrs


class ResendOTPSerializer(serializers.Serializer):
    """Serializer for resending OTP"""
    
    email = serializers.EmailField()
    purpose = serializers.ChoiceField(choices=[
        ('verification', 'Email Verification'),
        ('password_reset', 'Password Reset'),
    ])
    
    def validate_email(self, value):
        try:
            user = User.objects.get(email=value)
            return value
        except User.DoesNotExist:
            raise serializers.ValidationError('User with this email does not exist.')


class PasswordResetRequestSerializer(serializers.Serializer):
    """Serializer for password reset request"""
    
    email = serializers.EmailField()
    
    def validate_email(self, value):
        try:
            user = User.objects.get(email=value)
            if not user.email_verified:
                raise serializers.ValidationError('Please verify your email first.')
            return value
        except User.DoesNotExist:
            raise serializers.ValidationError('User with this email does not exist.')


class PasswordResetConfirmSerializer(serializers.Serializer):
    """Serializer for password reset confirmation with OTP"""
    
    email = serializers.EmailField()
    otp_code = serializers.CharField(max_length=6, min_length=6)
    new_password = serializers.CharField(write_only=True)
    confirm_password = serializers.CharField(write_only=True)
    
    def validate_new_password(self, value):
        try:
            validate_password(value)
        except ValidationError as e:
            raise serializers.ValidationError(list(e.messages))
        return value
    
    def validate(self, attrs):
        email = attrs.get('email')
        otp_code = attrs.get('otp_code')
        new_password = attrs.get('new_password')
        confirm_password = attrs.get('confirm_password')
        
        if new_password != confirm_password:
            raise serializers.ValidationError('Passwords do not match.')
        
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            raise serializers.ValidationError('User with this email does not exist.')
        
        # Find valid OTP
        otp = EmailVerificationOTP.objects.filter(
            user=user,
            otp_code=otp_code,
            purpose='password_reset',
            is_used=False
        ).first()
        
        if not otp or not otp.is_valid():
            raise serializers.ValidationError('Invalid or expired OTP.')
        
        attrs['user'] = user
        attrs['otp'] = otp
        return attrs


class ChangePasswordSerializer(serializers.Serializer):
    """Serializer for changing password"""
    
    current_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True)
    confirm_password = serializers.CharField(write_only=True)
    
    def validate_current_password(self, value):
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError('Current password is incorrect.')
        return value
    
    def validate_new_password(self, value):
        try:
            validate_password(value)
        except ValidationError as e:
            raise serializers.ValidationError(list(e.messages))
        return value
    
    def validate(self, attrs):
        new_password = attrs.get('new_password')
        confirm_password = attrs.get('confirm_password')
        
        if new_password != confirm_password:
            raise serializers.ValidationError('Passwords do not match.')
        
        return attrs


class UserProfileSerializer(serializers.ModelSerializer):
    """Serializer for user profile"""
    
    user_email = serializers.CharField(source='user.email', read_only=True)
    user_name = serializers.CharField(source='user.get_full_name', read_only=True)
    
    class Meta:
        model = UserProfile
        fields = [
            'user_email', 'user_name', 'bio', 'location', 'birth_date',
            'website', 'preferred_language', 'timezone', 'email_notifications',
            'sms_notifications', 'preferred_translation_service', 'preferred_ai_model',
            'api_calls_today', 'api_calls_this_month', 'last_api_call', 
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'user_email', 'user_name', 'api_calls_today', 'api_calls_this_month',
            'last_api_call', 'created_at', 'updated_at'
        ]


class UserStatsSerializer(serializers.Serializer):
    """Serializer for user statistics"""
    
    total_users = serializers.IntegerField()
    verified_users = serializers.IntegerField()
    active_users_today = serializers.IntegerField()
    total_api_calls = serializers.IntegerField()

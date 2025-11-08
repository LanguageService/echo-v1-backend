from django.contrib.auth import get_user_model
from rest_framework import serializers
from rest_framework.validators import UniqueValidator
from django.contrib.auth.password_validation import validate_password

from notification.models import NotificationPlatform, Platform
from wallet.models import Wallet



User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        exclude = ("password", "is_superuser", "user_permissions", "groups", "username")


class CustomerRegistrationSerializer(serializers.Serializer):
    first_name = serializers.CharField()
    last_name = serializers.CharField()
    email = serializers.EmailField(
        validators=[
            UniqueValidator(queryset=User.objects.all(), message="User already exist")
        ]
    )
    password = serializers.CharField(validators=[validate_password], write_only=True)

    def create(self, validated_data):
        password = validated_data.pop("password")

        user = User.objects.create(**validated_data)

        user.set_password(password)
        user.is_active = True
        user.is_verified = False
        user.user_type = User.CUSTOMER
        user.save()




        # set the default notification platform
        NotificationPlatform.objects.get_or_create(
            user=user, platform=Platform.EMAIL.value, status=True
        )

        Wallet.fetch_for_user(user)

        return user



class AdminUserRegistrationSerializer(serializers.Serializer):
    first_name = serializers.CharField()
    last_name = serializers.CharField()
    email = serializers.EmailField(
        validators=[
            UniqueValidator(queryset=User.objects.all(), message="User already exist")
        ]
    )
    password = serializers.CharField(validators=[validate_password], write_only=True)

    def create(self, validated_data):
        password = validated_data.pop("password")

        user = User.objects.create(**validated_data)

        user.set_password(password)
        user.is_active = True
        user.is_verified = False
        user.user_type = User.ADMIN
        user.save()

        # set the default notification platform
        NotificationPlatform.objects.get_or_create(
            user=user, platform=Platform.EMAIL.value, status=True
        )
        # TODO: Send otp

        return user


class SuperAdminUserRegistrationSerializer(serializers.Serializer):
    first_name = serializers.CharField()
    last_name = serializers.CharField()
    email = serializers.EmailField(
        validators=[
            UniqueValidator(queryset=User.objects.all(), message="User already exist")
        ]
    )
    password = serializers.CharField(validators=[validate_password], write_only=True)

    def create(self, validated_data):
        password = validated_data.pop("password")

        user = User.objects.create(**validated_data)

        user.set_password(password)
        user.is_active = True
        user.is_verified = False
        user.user_type = User.SUPER_ADMIN
        user.save()

        # set the default notification platform
        NotificationPlatform.objects.get_or_create(
            user=user, platform=Platform.EMAIL.value, status=True
        )
        # TODO: Send otp

        return user

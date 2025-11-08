from django.contrib.auth import get_user_model
from rest_framework import filters, mixins
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter
from rest_framework.viewsets import GenericViewSet
from rest_framework.response import Response
from rest_framework import status

from core.utils import error_401, error_400, error_404
from core.viewset import BaseViewSet
from users.utils import user_deletion
from .. import serializers


User = get_user_model()


@extend_schema_view(
    create=extend_schema(exclude=True),
)
class UserViewSet(BaseViewSet):
    queryset = User.objects.filter(archived__isnull=True).filter(archived=None)
    serializer_class = serializers.UserSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = [
        "email",
        "first_name",
        "last_name",
        "user_type",
        "is_active",
        "is_verified",
    ]
    ordering_fields = [
        "email",
        "first_name",
        "last_name",
        "user_type",
        "is_active",
        "is_verified",
        "date_created",
    ]
    pagination_class = None

    def get_queryset(self):

        if self.request.user.user_type == User.SUPER_ADMIN:
            return super().get_queryset()
        if self.request.user.user_type == User.ADMIN:
            return super().get_queryset().filter(user_type=User.CUSTOMER)
        if self.request.user.user_type == User.CUSTOMER:
            return super().get_queryset().filter(id=self.request.user.id)
        return super().get_queryset()

    def retrieve(self, request, *args, **kwargs):
        user = request.user
        instance = self.get_object()

        if user.user_type == User.ADMIN and instance.user_type != User.CUSTOMER:
            return error_401("Unauthorized User")

        if user.user_type == User.CUSTOMER and instance.id != user.id:
            return error_401("Unauthorized User")

        return super().retrieve(request, *args, **kwargs)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="user_type",
                description="Filter users by type (e.g., CUSTOMER, ADMIN, SUPER_ADMIN)",
                required=False,
                type=str,
                enum=["CUSTOMER", "ADMIN", "SUPER_ADMIN"],
            )
        ],
    )
    def list(self, request, *args, **kwargs):

        user_type = request.query_params.get("user_type", None)

        # Ensure user_type is not None before calling .lower()
        if not user_type:
            return error_400("user_type is required")

        user_type = user_type.lower()

        if user_type == User.CUSTOMER:
            return error_401("Unauthorized User")

        if user_type == User.ADMIN:
            if user_type.lower() not in [User.CUSTOMER, User.ADMIN]:
                return error_401("Unauthorized User")
            queryset = self.filter_queryset(
                self.get_queryset().filter(user_type=user_type)
            )

        if user_type == User.SUPER_ADMIN:
            queryset = self.filter_queryset(
                self.get_queryset().filter(user_type=user_type)
            )

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    def update(self, request, *args, **kwargs):
        user = request.user
        instance = self.get_object()

        if user.user_type == User.ADMIN and instance.user_type != User.CUSTOMER:
            return error_401("Unauthorized User")

        if user.user_type == User.CUSTOMER and instance.id != user.id:
            return error_401("Unauthorized User")

        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        user = request.user
        instance = self.get_object()

        if user.user_type == User.ADMIN and instance.user_type != User.CUSTOMER:
            return error_401("Unauthorized User")

        if user.user_type == User.CUSTOMER and instance.id != user.id:
            return error_401("Unauthorized User")

        user_deletion(request, user)

        return super().destroy(request, *args, **kwargs)

    @action(
        detail=False,
        methods=["GET"],
        serializer_class=serializers.UserSerializer,
        permission_classes=[IsAuthenticated],
        url_path="me",
    )
    def me(self, request, *args, **kwargs):
        user = request.user

        if not user:
            return error_401("Invalid User")
        if not user.is_active:
            return error_401("User is not active")

        if not user.is_verified:
            return error_401("User is not verified")

        if user.archived:
            return error_400("User does not exist")

        serializer = self.get_serializer(user)
        return Response(serializer.data)

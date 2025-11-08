from rest_framework.permissions import BasePermission
from .models.users import User


class BlockUnverifiedCustomerPermission(BasePermission):
    message = "You must be an active and verified user to perform this action"

    def has_permission(self, request, view):
        user = User.objects.filter(user=request.user)
        if not user:
            return False
        if not user[0].is_active:
            return False

        if not user[0].is_verified:
            return False

        return True


class AdminDeletePermission(BasePermission):
    message = "You must be an admin to perform this action"

    def has_permission(self, request, view):
        if request.method == "DELETE" and request.user.user_type not in [
            User.SUPER_ADMIN,
            User.ADMIN,
        ]:
            return False
        return True


class AdminCreateDeletePermission(BasePermission):
    message = "You must be an admin to perform this action"

    def has_permission(self, request, view):
        if request.method in ["DELETE", "POST"] and request.user.user_type not in [
            User.SUPER_ADMIN,
            User.ADMIN,
        ]:
            return False
        return True


class IsAdminUser(BasePermission):
    """
    Allows access only to admin users.
    """
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and request.user.user_type in [User.ADMIN, User.SUPER_ADMIN]

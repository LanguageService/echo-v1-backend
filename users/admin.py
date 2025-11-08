from django.contrib import admin
from .models import (
    User,
    OneTimePassword,
)


class UserAdmin(admin.ModelAdmin):
    search_fields = [
        "first_name",
        "last_name",
        "phone",
        "email",
        "user_type",
        "is_active",
    ]

    list_display = (
        "id",
        "first_name",
        "last_name",
        "phone",
        "email",
        "user_type",
        "is_active",
        "is_verified",
        "archived",
        "date_created",
        "last_modified",
    )

    list_filter = (
        "user_type",
        "is_active",
        "is_verified",
        "date_created",
        "last_modified",
    )

class OneTimePasswordAdmin(admin.ModelAdmin):
    search_fields = [
        "email",
        "used",
        "token_type",
    ]

    list_display = ("email", "used", "token_type", "created")

    list_filter = ("used", "token_type", "created")






admin.site.register(User, UserAdmin)
admin.site.register(OneTimePassword, OneTimePasswordAdmin)

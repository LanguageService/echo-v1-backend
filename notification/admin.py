from django.contrib import admin
from .models import NotificationPlatform


class NotificationPlatformAdmin(admin.ModelAdmin):
    search_fields = [
        "user__first_name",
        "user__last_name",
        "platform",
        "status",
    ]

    list_display = (
        "user__first_name",
        "user__last_name",
        "platform",
        "status",
        "date_created",
        "last_modified",
    )

    list_filter = (
        "platform",
        "status",
        "date_created",
        "last_modified",
    )


admin.site.register(NotificationPlatform, NotificationPlatformAdmin)

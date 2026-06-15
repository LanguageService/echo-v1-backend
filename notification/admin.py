from django.contrib import admin
from .models import NotificationPlatform


@admin.register(NotificationPlatform)
class NotificationPlatformAdmin(admin.ModelAdmin):
    list_display = ("get_first_name", "get_last_name", "get_email", "platform", "status", "date_created", "last_modified")
    list_filter = ("platform", "status", "date_created")
    search_fields = ("user__first_name", "user__last_name", "user__email")
    readonly_fields = ("date_created", "last_modified")
    raw_id_fields = ("user",)

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("user")

    @admin.display(description="First Name", ordering="user__first_name")
    def get_first_name(self, obj):
        return obj.user.first_name

    @admin.display(description="Last Name", ordering="user__last_name")
    def get_last_name(self, obj):
        return obj.user.last_name

    @admin.display(description="Email", ordering="user__email")
    def get_email(self, obj):
        return obj.user.email

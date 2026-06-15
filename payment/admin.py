from django.contrib import admin
from .models import Payment, PaymentWebhookEvent
from . import choices


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = (
        "reference", "user", "amount", "payment_type", "status",
        "payment_channel", "gateway_charge", "service_charge", "date_created",
    )
    list_filter = ("status", "payment_type", "payment_channel", "date_created")
    search_fields = ("reference", "user__email", "user__first_name", "user__last_name")
    readonly_fields = ("reference", "date_created", "last_modified")
    raw_id_fields = ("user",)
    ordering = ("-date_created",)

    fieldsets = (
        ("Transaction", {
            "fields": ("user", "reference", "amount", "payment_type", "payment_channel"),
        }),
        ("Status", {
            "fields": ("status",),
        }),
        ("Charges", {
            "fields": ("gateway_charge", "service_charge"),
        }),
        ("Timestamps", {
            "fields": ("date_created", "last_modified"),
            "classes": ("collapse",),
        }),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("user")

    actions = ["mark_success", "mark_failed"]

    @admin.action(description="Mark selected payments as SUCCESS")
    def mark_success(self, request, queryset):
        updated = queryset.update(status=choices.PaymentStatus.SUCCESS)
        self.message_user(request, f"{updated} payment(s) marked as SUCCESS.")

    @admin.action(description="Mark selected payments as FAILED")
    def mark_failed(self, request, queryset):
        updated = queryset.update(status=choices.PaymentStatus.FAILED)
        self.message_user(request, f"{updated} payment(s) marked as FAILED.")


@admin.register(PaymentWebhookEvent)
class PaymentWebhookEventAdmin(admin.ModelAdmin):
    list_display = ("refid", "source", "get_payment_ref", "status_id", "status_desc", "processed", "created_at")
    list_filter = ("processed", "source", "status_id", "created_at")
    search_fields = ("refid", "transaction_id", "status_desc", "payment__reference")
    readonly_fields = ("refid", "transaction_id", "status_id", "status_desc", "raw_payload", "source", "created_at", "updated_at")
    raw_id_fields = ("payment",)
    ordering = ("-created_at",)

    fieldsets = (
        ("Event", {
            "fields": ("payment", "source", "refid", "transaction_id", "status_id", "status_desc", "processed"),
        }),
        ("Raw Payload", {
            "fields": ("raw_payload",),
            "classes": ("collapse",),
        }),
        ("Timestamps", {
            "fields": ("created_at", "updated_at"),
            "classes": ("collapse",),
        }),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("payment")

    @admin.display(description="Payment Ref", ordering="payment__reference")
    def get_payment_ref(self, obj):
        if obj.payment:
            return obj.payment.reference
        return "—"

    actions = ["mark_processed"]

    @admin.action(description="Mark selected webhook events as processed")
    def mark_processed(self, request, queryset):
        updated = queryset.update(processed=True)
        self.message_user(request, f"{updated} webhook event(s) marked as processed.")

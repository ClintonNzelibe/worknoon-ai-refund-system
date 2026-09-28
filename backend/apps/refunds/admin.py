from django.contrib import admin

from .models import RefundAIAssistance, RefundRequest, RefundRequestItem


class RefundRequestItemInline(admin.TabularInline):
    model = RefundRequestItem
    extra = 0
    readonly_fields = (
        "order_item",
        "requested_quantity",
        "decision",
        "decision_reason",
        "created_at",
        "updated_at",
    )
    can_delete = False


@admin.register(RefundRequest)
class RefundRequestAdmin(admin.ModelAdmin):
    list_display = ("id", "order", "status", "reason_code", "requested_amount", "created_at", "resolved_at")
    list_filter = ("status", "reason_code", "is_suspicious")
    search_fields = ("order__reference", "order__customer__email")
    readonly_fields = (
        "order",
        "status",
        "reason_code",
        "reason",
        "is_suspicious",
        "idempotency_key",
        "requested_amount",
        "resolution_note",
        "resolved_at",
        "created_at",
        "updated_at",
    )
    inlines = (RefundRequestItemInline,)


@admin.register(RefundRequestItem)
class RefundRequestItemAdmin(admin.ModelAdmin):
    list_display = ("order_item", "refund_request", "requested_quantity", "decision")
    list_filter = ("decision",)
    search_fields = ("order_item__sku", "refund_request__order__reference")
    readonly_fields = (
        "refund_request",
        "order_item",
        "requested_quantity",
        "decision",
        "decision_reason",
        "created_at",
        "updated_at",
    )


@admin.register(RefundAIAssistance)
class RefundAIAssistanceAdmin(admin.ModelAdmin):
    list_display = ("refund_request", "status", "classification", "risk", "created_at")
    list_filter = ("status", "classification", "risk")
    search_fields = ("refund_request__order__reference",)
    readonly_fields = (
        "refund_request", "status", "provider", "model_identifier", "classification", "risk",
        "summary", "reasoning", "customer_message", "policy_alignment", "created_at", "updated_at",
    )

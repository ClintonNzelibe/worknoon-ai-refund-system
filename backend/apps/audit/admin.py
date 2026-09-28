from django.contrib import admin

from .models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("action", "refund_request", "created_at")
    list_filter = ("action",)
    search_fields = ("refund_request__order__reference", "message")
    readonly_fields = ("refund_request", "action", "message", "metadata", "created_at")

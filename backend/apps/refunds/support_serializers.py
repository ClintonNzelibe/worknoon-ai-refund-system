from rest_framework import serializers

from apps.audit.models import AuditLog

from .models import RefundRequest, RefundRequestItem
from .serializers import OrderItemSerializer


class SupportRefundItemSerializer(serializers.ModelSerializer):
    order_item = OrderItemSerializer(read_only=True)
    requested_amount = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = RefundRequestItem
        fields = (
            "id",
            "order_item",
            "requested_quantity",
            "requested_amount",
            "decision",
            "decision_reason",
        )


class AuditLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = AuditLog
        fields = ("id", "action", "message", "metadata", "created_at")


class SupportRefundRequestSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source="order.customer.full_name", read_only=True)
    customer_email = serializers.EmailField(source="order.customer.email", read_only=True)
    order_reference = serializers.CharField(source="order.reference", read_only=True)
    currency = serializers.CharField(source="order.currency", read_only=True)
    items = SupportRefundItemSerializer(many=True, read_only=True)
    audit_logs = AuditLogSerializer(many=True, read_only=True)

    class Meta:
        model = RefundRequest
        fields = (
            "id",
            "customer_name",
            "customer_email",
            "order_reference",
            "currency",
            "requested_amount",
            "status",
            "reason_code",
            "reason",
            "resolution_note",
            "created_at",
            "resolved_at",
            "items",
            "audit_logs",
        )


class SupportReviewSerializer(serializers.Serializer):
    decision = serializers.ChoiceField(choices=("approved", "rejected"))
    note = serializers.CharField(max_length=1_000, trim_whitespace=True)

    def validate_note(self, value):
        if not value:
            raise serializers.ValidationError("A review note is required.")
        return value

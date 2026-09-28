from rest_framework import serializers

from apps.customers.models import Customer
from apps.orders.models import Order, OrderItem

from .models import RefundRequest, RefundRequestItem


class OrderItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderItem
        fields = (
            "id",
            "sku",
            "product_name",
            "unit_price",
            "quantity",
            "is_final_sale",
        )


class OrderSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = Order
        fields = ("reference", "status", "currency", "total_amount", "ordered_at")


class CustomerLookupSerializer(serializers.ModelSerializer):
    """Order summaries for an ownership-scoped customer lookup."""

    orders = OrderSummarySerializer(many=True, read_only=True)

    class Meta:
        model = Customer
        fields = ("orders",)


class OrderLookupSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)

    class Meta:
        model = Order
        fields = (
            "reference",
            "status",
            "currency",
            "total_amount",
            "ordered_at",
            "items",
        )


class RefundRequestItemInputSerializer(serializers.Serializer):
    order_item_id = serializers.IntegerField(min_value=1)
    requested_quantity = serializers.IntegerField(min_value=1)


class RefundRequestCreateSerializer(serializers.Serializer):
    order_reference = serializers.CharField(max_length=64)
    reason_code = serializers.ChoiceField(choices=RefundRequest.ReasonCode.choices)
    reason = serializers.CharField(max_length=4_000)
    items = RefundRequestItemInputSerializer(many=True, allow_empty=False)

    def validate(self, attrs):
        try:
            order = Order.objects.get(reference=attrs["order_reference"])
        except Order.DoesNotExist:
            raise serializers.ValidationError(
                {"order_reference": "No order exists with this reference."}
            )

        item_ids = [item["order_item_id"] for item in attrs["items"]]
        if len(item_ids) != len(set(item_ids)):
            raise serializers.ValidationError(
                {"items": "Each order item can be requested only once."}
            )

        order_items = OrderItem.objects.filter(order=order, id__in=item_ids)
        if order_items.count() != len(item_ids):
            raise serializers.ValidationError(
                {"items": "Every requested item must belong to the selected order."}
            )

        items_by_id = {item.id: item for item in order_items}
        invalid_quantities = [
            item["order_item_id"]
            for item in attrs["items"]
            if item["requested_quantity"] > items_by_id[item["order_item_id"]].quantity
        ]
        if invalid_quantities:
            raise serializers.ValidationError(
                {"items": "Requested quantities cannot exceed quantities purchased."}
            )

        attrs["order"] = order
        attrs["order_items"] = items_by_id
        return attrs


class RefundRequestItemSerializer(serializers.ModelSerializer):
    order_item = OrderItemSerializer(read_only=True)
    requested_amount = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        read_only=True,
    )

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


class RefundRequestSerializer(serializers.ModelSerializer):
    order_reference = serializers.CharField(source="order.reference", read_only=True)
    customer_id = serializers.IntegerField(source="order.customer_id", read_only=True)
    items = RefundRequestItemSerializer(many=True, read_only=True)
    policy_outcome = serializers.SerializerMethodField()

    class Meta:
        model = RefundRequest
        fields = (
            "id",
            "order_reference",
            "customer_id",
            "status",
            "policy_outcome",
            "reason_code",
            "reason",
            "requested_amount",
            "resolution_note",
            "resolved_at",
            "created_at",
            "items",
        )

    def get_policy_outcome(self, instance):
        if instance.status == RefundRequest.Status.ESCALATED:
            return "escalated"
        if instance.status == RefundRequest.Status.APPROVED:
            return "approved"
        if instance.status == RefundRequest.Status.REJECTED:
            return "rejected"
        return None

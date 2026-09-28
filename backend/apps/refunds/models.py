from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models


class RefundRequest(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        PAID = "paid", "Paid"
        CANCELLED = "cancelled", "Cancelled"
        ESCALATED = "escalated", "Escalated for review"

    class ReasonCode(models.TextChoices):
        DAMAGED = "damaged", "Damaged"
        INCORRECT = "incorrect", "Incorrect item"
        OTHER = "other", "Other"

    order = models.ForeignKey(
        "orders.Order",
        on_delete=models.PROTECT,
        related_name="refund_requests",
    )
    status = models.CharField(max_length=16, choices=Status, default=Status.PENDING)
    reason_code = models.CharField(
        max_length=16,
        choices=ReasonCode,
        default=ReasonCode.OTHER,
    )
    reason = models.TextField()
    is_suspicious = models.BooleanField(default=False)
    idempotency_key = models.CharField(max_length=64, null=True, blank=True)
    requested_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    resolution_note = models.TextField(blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["order", "status", "-created_at"]),
            models.Index(fields=["status", "-created_at"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["idempotency_key"],
                condition=models.Q(idempotency_key__isnull=False),
                name="refund_idempotency_key_unique",
            ),
            models.CheckConstraint(
                condition=models.Q(requested_amount__gt=0),
                name="refund_requested_amount_positive",
            ),
        ]
        ordering = ["-created_at", "-id"]

    def __str__(self) -> str:
        return f"Refund #{self.pk or 'new'} for {self.order.reference}"


class RefundRequestItem(models.Model):
    class Decision(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        ESCALATED = "escalated", "Escalated for review"

    refund_request = models.ForeignKey(
        RefundRequest,
        on_delete=models.PROTECT,
        related_name="items",
    )
    order_item = models.ForeignKey(
        "orders.OrderItem",
        on_delete=models.PROTECT,
        related_name="refund_request_items",
    )
    requested_quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    decision = models.CharField(
        max_length=16,
        choices=Decision,
        default=Decision.PENDING,
    )
    decision_reason = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(
                fields=["order_item", "decision"],
                name="refund_item_decision_idx",
            ),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["refund_request", "order_item"],
                name="refund_request_item_unique",
            ),
            models.CheckConstraint(
                condition=models.Q(requested_quantity__gte=1),
                name="refund_requested_quantity_positive",
            ),
        ]

    @property
    def requested_amount(self):
        return self.order_item.unit_price * self.requested_quantity

    def __str__(self) -> str:
        return f"{self.order_item.product_name} on refund #{self.refund_request_id}"


class RefundAIAssistance(models.Model):
    """Validated, non-authoritative AI assistance for one refund request."""

    class Status(models.TextChoices):
        AVAILABLE = "available", "Available"
        NOT_CONFIGURED = "not_configured", "Not configured"
        PROVIDER_UNAVAILABLE = "provider_unavailable", "Provider unavailable"
        RATE_LIMITED = "rate_limited", "Rate limited"
        TIMED_OUT = "timed_out", "Timed out"
        INVALID_RESPONSE = "invalid_response", "Invalid response"

    class Classification(models.TextChoices):
        CONSISTENT = "consistent", "Consistent"
        CONFLICTING = "conflicting", "Conflicting"
        UNCLEAR = "unclear", "Unclear"

    class Risk(models.TextChoices):
        LOW = "low", "Low"
        MEDIUM = "medium", "Medium"
        HIGH = "high", "High"

    refund_request = models.OneToOneField(
        RefundRequest,
        on_delete=models.PROTECT,
        related_name="ai_assistance",
    )
    status = models.CharField(max_length=32, choices=Status.choices)
    provider = models.CharField(max_length=32, blank=True)
    model_identifier = models.CharField(max_length=128, blank=True)
    classification = models.CharField(max_length=16, choices=Classification.choices, blank=True)
    risk = models.CharField(max_length=16, choices=Risk.choices, blank=True)
    summary = models.CharField(max_length=500, blank=True)
    reasoning = models.TextField(blank=True)
    customer_message = models.TextField(blank=True)
    policy_alignment = models.CharField(max_length=16, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [models.Index(fields=["status", "-created_at"])]

    def __str__(self) -> str:
        return f"AI assistance for refund #{self.refund_request_id}"

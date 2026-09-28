"""Deterministic refund decisions. This module deliberately has no AI dependency."""

from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal
from enum import Enum

from django.utils import timezone

from .models import RefundRequest, RefundRequestItem


REFUND_PERIOD_DAYS = 30
HUMAN_REVIEW_AMOUNT = Decimal("500.00")


class PolicyDecision(str, Enum):
    APPROVED = "approved"
    REJECTED = "rejected"
    ESCALATED = "escalated"


@dataclass(frozen=True)
class ItemPolicyDecision:
    refund_request_item_id: int
    decision: PolicyDecision
    reason: str


@dataclass(frozen=True)
class RefundPolicyResult:
    item_decisions: tuple[ItemPolicyDecision, ...]

    @property
    def outcome(self) -> PolicyDecision:
        if any(item.decision == PolicyDecision.ESCALATED for item in self.item_decisions):
            return PolicyDecision.ESCALATED
        if any(item.decision == PolicyDecision.APPROVED for item in self.item_decisions):
            return PolicyDecision.APPROVED
        return PolicyDecision.REJECTED


def evaluate_refund_request(
    refund_request: RefundRequest,
    *,
    now=None,
) -> RefundPolicyResult:
    """Evaluate each requested item without writing to the database."""
    now = now or timezone.now()
    request_items = list(
        refund_request.items.select_related("order_item", "order_item__order")
    )
    requires_human_review = refund_request.requested_amount > HUMAN_REVIEW_AMOUNT

    decisions = tuple(
        _evaluate_item(
            refund_request,
            request_item,
            now=now,
            requires_human_review=requires_human_review,
        )
        for request_item in request_items
    )
    return RefundPolicyResult(item_decisions=decisions)


def _evaluate_item(
    refund_request: RefundRequest,
    request_item: RefundRequestItem,
    *,
    now,
    requires_human_review: bool,
) -> ItemPolicyDecision:
    item = request_item.order_item
    if item.is_final_sale:
        return _decision(request_item, PolicyDecision.REJECTED, "Final-sale items are not refundable.")
    if item.order.ordered_at + timedelta(days=REFUND_PERIOD_DAYS) < now:
        return _decision(request_item, PolicyDecision.REJECTED, "The 30-day refund period has expired.")
    if request_item.requested_quantity > item.quantity:
        return _decision(request_item, PolicyDecision.REJECTED, "Requested quantity exceeds the purchased quantity.")
    if refund_request.is_suspicious or _has_conflicting_claim(refund_request, item):
        return _decision(request_item, PolicyDecision.ESCALATED, "Conflicting or suspicious claims require human review.")
    if requires_human_review:
        return _decision(request_item, PolicyDecision.ESCALATED, "Refunds above $500 require human review.")
    if refund_request.reason_code in {
        RefundRequest.ReasonCode.DAMAGED,
        RefundRequest.ReasonCode.INCORRECT,
    }:
        return _decision(request_item, PolicyDecision.APPROVED, "Eligible damaged or incorrect item within 30 days.")
    return _decision(request_item, PolicyDecision.REJECTED, "The stated reason is not eligible for a refund.")


def _has_conflicting_claim(refund_request: RefundRequest, order_item) -> bool:
    """An unresolved or previously approved claim for the same item is a conflict."""
    conflicting_statuses = [
        RefundRequest.Status.PENDING,
        RefundRequest.Status.APPROVED,
        RefundRequest.Status.PAID,
        RefundRequest.Status.ESCALATED,
    ]
    return RefundRequestItem.objects.filter(
        order_item=order_item,
        refund_request__status__in=conflicting_statuses,
    ).exclude(refund_request=refund_request).exists()


def _decision(
    request_item: RefundRequestItem,
    decision: PolicyDecision,
    reason: str,
) -> ItemPolicyDecision:
    return ItemPolicyDecision(
        refund_request_item_id=request_item.pk,
        decision=decision,
        reason=reason,
    )

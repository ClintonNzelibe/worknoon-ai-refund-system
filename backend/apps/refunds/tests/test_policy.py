from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from apps.customers.models import Customer
from apps.orders.models import Order, OrderItem
from apps.refunds.models import RefundRequest, RefundRequestItem
from apps.refunds.policy import PolicyDecision, evaluate_refund_request


class RefundPolicyTests(TestCase):
    def setUp(self):
        self.customer = Customer.objects.create(full_name="Policy Tester", email="policy@example.test")

    def make_request(
        self,
        *,
        age_days=5,
        reason_code=RefundRequest.ReasonCode.DAMAGED,
        amount=Decimal("25.00"),
        final_sale=False,
        quantity=1,
        requested_quantity=1,
        suspicious=False,
    ):
        order = Order.objects.create(
            customer=self.customer,
            reference=f"POL-{Order.objects.count() + 1}",
            status=Order.Status.PAID,
            total_amount=amount,
            ordered_at=timezone.now() - timedelta(days=age_days),
        )
        item = OrderItem.objects.create(
            order=order,
            sku=f"SKU-{order.pk}",
            product_name="Policy item",
            unit_price=amount,
            quantity=quantity,
            is_final_sale=final_sale,
        )
        request = RefundRequest.objects.create(
            order=order,
            reason_code=reason_code,
            reason="Policy test request",
            requested_amount=amount,
            is_suspicious=suspicious,
        )
        request_item = RefundRequestItem.objects.create(
            refund_request=request,
            order_item=item,
            requested_quantity=requested_quantity,
        )
        return request, request_item

    def test_damaged_item_within_period_is_approved(self):
        request, request_item = self.make_request()

        result = evaluate_refund_request(request)

        self.assertEqual(result.outcome, PolicyDecision.APPROVED)
        self.assertEqual(result.item_decisions[0].refund_request_item_id, request_item.pk)

    def test_incorrect_item_within_period_is_approved(self):
        request, _ = self.make_request(reason_code=RefundRequest.ReasonCode.INCORRECT)

        self.assertEqual(evaluate_refund_request(request).outcome, PolicyDecision.APPROVED)

    def test_final_sale_item_is_rejected(self):
        request, _ = self.make_request(final_sale=True)

        self.assertEqual(evaluate_refund_request(request).outcome, PolicyDecision.REJECTED)

    def test_order_after_30_days_is_rejected_but_boundary_is_eligible(self):
        expired_request, _ = self.make_request(age_days=31)
        boundary_request, _ = self.make_request(age_days=30)
        now = timezone.now()

        self.assertEqual(evaluate_refund_request(expired_request, now=now).outcome, PolicyDecision.REJECTED)
        self.assertEqual(evaluate_refund_request(boundary_request, now=boundary_request.order.ordered_at + timedelta(days=30)).outcome, PolicyDecision.APPROVED)

    def test_high_value_request_is_escalated(self):
        request, _ = self.make_request(amount=Decimal("500.01"))

        self.assertEqual(evaluate_refund_request(request).outcome, PolicyDecision.ESCALATED)

    def test_suspicious_request_is_escalated(self):
        request, _ = self.make_request(suspicious=True)

        self.assertEqual(evaluate_refund_request(request).outcome, PolicyDecision.ESCALATED)

    def test_conflicting_claim_is_escalated(self):
        request, request_item = self.make_request()
        prior_request = RefundRequest.objects.create(
            order=request.order,
            status=RefundRequest.Status.APPROVED,
            reason_code=RefundRequest.ReasonCode.DAMAGED,
            reason="Earlier approved request",
            requested_amount=Decimal("25.00"),
        )
        RefundRequestItem.objects.create(
            refund_request=prior_request,
            order_item=request_item.order_item,
            requested_quantity=1,
            decision=RefundRequestItem.Decision.APPROVED,
        )

        self.assertEqual(evaluate_refund_request(request).outcome, PolicyDecision.ESCALATED)

    def test_mixed_order_returns_item_level_approval_and_rejection(self):
        request, eligible_request_item = self.make_request()
        final_sale_item = OrderItem.objects.create(
            order=request.order,
            sku="FINAL-SALE",
            product_name="Final-sale item",
            unit_price=Decimal("5.00"),
            quantity=1,
            is_final_sale=True,
        )
        RefundRequestItem.objects.create(
            refund_request=request,
            order_item=final_sale_item,
            requested_quantity=1,
        )

        decisions = {item.refund_request_item_id: item.decision for item in evaluate_refund_request(request).item_decisions}

        self.assertEqual(decisions[eligible_request_item.pk], PolicyDecision.APPROVED)
        self.assertIn(PolicyDecision.REJECTED, decisions.values())

    def test_request_cannot_exceed_purchased_quantity(self):
        request, _ = self.make_request(quantity=1, requested_quantity=2)

        self.assertEqual(evaluate_refund_request(request).outcome, PolicyDecision.REJECTED)

    def test_other_reason_is_rejected(self):
        request, _ = self.make_request(reason_code=RefundRequest.ReasonCode.OTHER)

        self.assertEqual(evaluate_refund_request(request).outcome, PolicyDecision.REJECTED)

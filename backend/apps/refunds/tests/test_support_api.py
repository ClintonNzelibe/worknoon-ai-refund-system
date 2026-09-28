from datetime import timedelta
from decimal import Decimal
import os
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.audit.models import AuditLog
from apps.customers.models import Customer
from apps.orders.models import Order, OrderItem
from apps.refunds.models import RefundAIAssistance, RefundRequest, RefundRequestItem


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
@patch.dict(os.environ, {"OPENAI_API_KEY": ""})
class SupportRefundApiTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.customer_user = user_model.objects.create_user("customer", password="test-password")
        self.staff_user = user_model.objects.create_user(
            "support",
            password="test-password",
            is_staff=True,
        )
        self.customer = Customer.objects.create(
            full_name="Support Test Customer",
            email="support.customer@example.test",
        )
        self.refund_request, self.escalated_item, self.rejected_item = self.make_escalated_request()

    def make_escalated_request(self, suffix="1"):
        order = Order.objects.create(
            customer=self.customer,
            reference=f"SUP-{suffix}",
            status=Order.Status.PAID,
            total_amount=Decimal("550.00"),
            ordered_at=timezone.now() - timedelta(days=2),
        )
        escalated_order_item = OrderItem.objects.create(
            order=order,
            sku=f"ESC-{suffix}",
            product_name="Reviewable item",
            unit_price=Decimal("500.00"),
            quantity=1,
        )
        rejected_order_item = OrderItem.objects.create(
            order=order,
            sku=f"FINAL-{suffix}",
            product_name="Final-sale item",
            unit_price=Decimal("50.00"),
            quantity=1,
            is_final_sale=True,
        )
        refund_request = RefundRequest.objects.create(
            order=order,
            status=RefundRequest.Status.ESCALATED,
            reason_code=RefundRequest.ReasonCode.DAMAGED,
            reason="Damaged delivery.",
            requested_amount=Decimal("550.00"),
        )
        escalated_item = RefundRequestItem.objects.create(
            refund_request=refund_request,
            order_item=escalated_order_item,
            requested_quantity=1,
            decision=RefundRequestItem.Decision.ESCALATED,
            decision_reason="Refunds above $500 require human review.",
        )
        rejected_item = RefundRequestItem.objects.create(
            refund_request=refund_request,
            order_item=rejected_order_item,
            requested_quantity=1,
            decision=RefundRequestItem.Decision.REJECTED,
            decision_reason="Final-sale items are not refundable.",
        )
        AuditLog.objects.create(refund_request=refund_request, action="policy_evaluated")
        return refund_request, escalated_item, rejected_item

    def client_for(self, user):
        client = APIClient()
        client.force_authenticate(user)
        return client

    def test_normal_user_cannot_access_support_list_or_review(self):
        client = self.client_for(self.customer_user)

        list_response = client.get(reverse("support-refund-list"))
        review_response = client.post(
            reverse("support-refund-review", args=[self.refund_request.id]),
            {"decision": "approved", "note": "Looks good."},
            format="json",
        )

        self.assertEqual(list_response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(review_response.status_code, status.HTTP_403_FORBIDDEN)

    def test_staff_can_filter_and_paginate_refund_requests(self):
        for index in range(2, 12):
            self.make_escalated_request(str(index))
        client = self.client_for(self.staff_user)

        response = client.get(reverse("support-refund-list"), {"status": "escalated", "page": 1})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 11)
        self.assertEqual(response.data["page_size"], 10)
        self.assertEqual(len(response.data["results"]), 10)
        self.assertTrue(all(item["status"] == "escalated" for item in response.data["results"]))

    def test_staff_detail_includes_audit_information_and_separate_ai_assistance(self):
        client = self.client_for(self.staff_user)

        response = client.get(reverse("support-refund-detail", args=[self.refund_request.id]))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["customer_email"], self.customer.email)
        self.assertEqual(response.data["audit_logs"][0]["action"], "policy_evaluated")
        self.assertFalse(response.data["ai_assistance"]["available"])

    def test_staff_detail_keeps_full_advisory_ai_fields_available_to_support(self):
        RefundAIAssistance.objects.create(
            refund_request=self.refund_request,
            status=RefundAIAssistance.Status.AVAILABLE,
            provider="openai",
            model_identifier="test-model",
            classification="conflicting",
            risk="high",
            summary="The claim needs review against the available order details.",
            reasoning="The request has conflicting information that support should review.",
            customer_message="Please provide photos and delivery details for support review.",
            policy_alignment="concern",
        )
        client = self.client_for(self.staff_user)

        response = client.get(reverse("support-refund-detail", args=[self.refund_request.id]))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["ai_assistance"]["available"])
        self.assertEqual(response.data["ai_assistance"]["classification"], "conflicting")
        self.assertEqual(response.data["ai_assistance"]["risk"], "high")
        self.assertIn("reasoning", response.data["ai_assistance"])
        self.assertIn("customer_message", response.data["ai_assistance"])

    def test_staff_review_records_audit_and_does_not_override_hard_rejection(self):
        client = self.client_for(self.staff_user)

        response = client.post(
            reverse("support-refund-review", args=[self.refund_request.id]),
            {"decision": "approved", "note": "Confirmed damage during manual review."},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.refund_request.refresh_from_db()
        self.escalated_item.refresh_from_db()
        self.rejected_item.refresh_from_db()
        audit_log = self.refund_request.audit_logs.get(action="human_reviewed")
        self.assertEqual(self.refund_request.status, RefundRequest.Status.APPROVED)
        self.assertEqual(self.escalated_item.decision, RefundRequestItem.Decision.APPROVED)
        self.assertEqual(self.rejected_item.decision, RefundRequestItem.Decision.REJECTED)
        self.assertEqual(audit_log.metadata["reviewer_id"], self.staff_user.id)
        self.assertIn("Confirmed damage", audit_log.message)

    def test_only_escalated_requests_can_be_reviewed(self):
        self.refund_request.status = RefundRequest.Status.REJECTED
        self.refund_request.save(update_fields=["status"])
        client = self.client_for(self.staff_user)

        response = client.post(
            reverse("support-refund-review", args=[self.refund_request.id]),
            {"decision": "approved", "note": "Should not be accepted."},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)

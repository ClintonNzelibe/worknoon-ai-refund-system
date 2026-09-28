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
from apps.refunds.models import RefundRequest, RefundRequestItem


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
@patch.dict(os.environ, {"OPENAI_API_KEY": ""})
class RefundEndToEndTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.customer_user = user_model.objects.create_user("customer", password="test-password")
        self.staff_user = user_model.objects.create_user(
            "staff",
            password="test-password",
            is_staff=True,
        )
        customer = Customer.objects.create(
            user=self.customer_user,
            full_name="End-to-end Customer",
            email="end-to-end@example.test",
        )
        self.order = Order.objects.create(
            customer=customer,
            reference="E2E-1001",
            status=Order.Status.PAID,
            total_amount=Decimal("600.00"),
            ordered_at=timezone.now() - timedelta(days=2),
        )
        self.item = OrderItem.objects.create(
            order=self.order,
            sku="E2E-HIGH",
            product_name="High-value test item",
            unit_price=Decimal("600.00"),
            quantity=1,
        )

    def test_customer_submission_through_staff_review_preserves_policy_and_audit_history(self):
        customer_client = APIClient()
        customer_client.force_authenticate(self.customer_user)

        lookup_response = customer_client.get(
            reverse("customer-lookup"), {"email": "end-to-end@example.test"}
        )
        order_response = customer_client.get(reverse("order-lookup", args=[self.order.reference]))
        payload = {
            "order_reference": self.order.reference,
            "reason_code": "damaged",
            "reason": "The high-value item arrived damaged.",
            "items": [{"order_item_id": self.item.id, "requested_quantity": 1}],
        }
        create_response = customer_client.post(
            reverse("refund-request-list-create"),
            payload,
            format="json",
            HTTP_IDEMPOTENCY_KEY="e2e-refund-request-key",
        )
        retry_response = customer_client.post(
            reverse("refund-request-list-create"),
            payload,
            format="json",
            HTTP_IDEMPOTENCY_KEY="e2e-refund-request-key",
        )

        self.assertEqual(lookup_response.status_code, status.HTTP_200_OK)
        self.assertEqual(order_response.status_code, status.HTTP_200_OK)
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(create_response.data["status"], RefundRequest.Status.ESCALATED)
        self.assertEqual(create_response.data["items"][0]["decision"], "escalated")
        self.assertEqual(retry_response.status_code, status.HTTP_200_OK)
        self.assertEqual(RefundRequest.objects.count(), 1)

        staff_client = APIClient()
        staff_client.force_authenticate(self.staff_user)
        list_response = staff_client.get(reverse("support-refund-list"), {"status": "escalated"})
        review_response = staff_client.post(
            reverse("support-refund-review", args=[create_response.data["id"]]),
            {"decision": "approved", "note": "Confirmed damage during manual review."},
            format="json",
        )
        customer_history_response = customer_client.get(
            reverse("refund-request-list-create"),
            {"order_reference": self.order.reference},
        )

        refund_request = RefundRequest.objects.get(pk=create_response.data["id"])
        refund_item = RefundRequestItem.objects.get(refund_request=refund_request)
        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertEqual(list_response.data["count"], 1)
        self.assertEqual(review_response.status_code, status.HTTP_200_OK)
        self.assertEqual(refund_request.status, RefundRequest.Status.APPROVED)
        self.assertEqual(refund_item.decision, RefundRequestItem.Decision.APPROVED)
        self.assertEqual(customer_history_response.status_code, status.HTTP_200_OK)
        self.assertEqual(customer_history_response.data[0]["status"], RefundRequest.Status.APPROVED)
        self.assertEqual(customer_history_response.data[0]["items"][0]["decision"], "approved")
        self.assertEqual(
            list(AuditLog.objects.values_list("action", flat=True)),
            ["human_reviewed", "ai_assistance_unavailable", "policy_evaluated", "refund_request_created"],
        )

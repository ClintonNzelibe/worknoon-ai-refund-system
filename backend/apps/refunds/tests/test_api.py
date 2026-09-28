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

from apps.customers.models import Customer
from apps.orders.models import Order, OrderItem
from apps.refunds.ai_service import AIRefundAssistance, AIServiceResult
from apps.refunds.models import RefundAIAssistance, RefundRequest


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
@patch.dict(os.environ, {"OPENAI_API_KEY": ""})
class RefundApiTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user(
            username="support-agent",
            password="not-used-in-this-test",
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.customer = Customer.objects.create(
            user=self.user,
            full_name="API Customer",
            email="api.customer@example.test",
        )
        self.request_number = 0

    def make_order(self, *, age_days=5, item_specs=(("SKU-1", "Item", "25.00", False),)):
        total = sum((Decimal(price) for _, _, price, _ in item_specs), Decimal("0.00"))
        order = Order.objects.create(
            customer=self.customer,
            reference=f"API-{Order.objects.count() + 1}",
            status=Order.Status.PAID,
            total_amount=total,
            ordered_at=timezone.now() - timedelta(days=age_days),
        )
        items = [
            OrderItem.objects.create(
                order=order,
                sku=sku,
                product_name=name,
                unit_price=Decimal(price),
                quantity=1,
                is_final_sale=is_final_sale,
            )
            for sku, name, price, is_final_sale in item_specs
        ]
        return order, items

    def create_refund(self, order, items, *, reason_code="damaged", idempotency_key=None):
        self.request_number += 1
        return self.client.post(
            reverse("refund-request-list-create"),
            {
                "order_reference": order.reference,
                "reason_code": reason_code,
                "reason": "Testing the deterministic policy.",
                "items": [
                    {"order_item_id": item.id, "requested_quantity": 1} for item in items
                ],
            },
            format="json",
            HTTP_IDEMPOTENCY_KEY=idempotency_key or f"test-request-key-{self.request_number}",
        )

    def test_authenticated_customer_lookup_returns_only_refund_flow_data(self):
        order, items = self.make_order()

        customer_response = self.client.get(
            reverse("customer-lookup"), {"email": self.customer.email}
        )
        order_response = self.client.get(reverse("order-lookup", args=[order.reference]))

        self.assertEqual(customer_response.status_code, status.HTTP_200_OK)
        self.assertEqual(customer_response.data["orders"][0]["reference"], order.reference)
        self.assertEqual(set(customer_response.data), {"orders"})
        self.assertEqual(order_response.status_code, status.HTTP_200_OK)
        self.assertEqual(order_response.data["items"][0]["id"], items[0].id)
        self.assertNotIn("customer", order_response.data)
        self.assertNotIn("id", order_response.data)

    def test_lookup_requires_a_customer_session_before_policy_submission(self):
        order, items = self.make_order()
        self.client.force_authenticate(user=None)

        self.assertEqual(
            self.client.get(reverse("customer-lookup"), {"email": self.customer.email}).status_code,
            status.HTTP_403_FORBIDDEN,
        )
        self.assertEqual(
            self.client.get(reverse("order-lookup", args=[order.reference])).status_code,
            status.HTTP_403_FORBIDDEN,
        )

        self.client.force_authenticate(self.user)
        response = self.create_refund(order, items)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["policy_outcome"], "approved")

    def test_unauthenticated_requests_are_rejected(self):
        self.client.force_authenticate(user=None)

        response = self.client.get(reverse("refund-request-list-create"))

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_damaged_item_is_approved_with_policy_reason(self):
        order, items = self.make_order()

        response = self.create_refund(order, items)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["status"], RefundRequest.Status.APPROVED)
        self.assertEqual(response.data["policy_outcome"], "approved")
        self.assertEqual(response.data["items"][0]["decision"], "approved")
        self.assertIn("Eligible damaged", response.data["items"][0]["decision_reason"])

    @patch("apps.refunds.ai_service.generate_refund_assistance")
    def test_customer_refund_response_exposes_only_safe_ai_guidance(self, mock_assistance):
        mock_assistance.return_value = AIServiceResult(assistance=AIRefundAssistance(
            classification="consistent",
            risk="low",
            summary="The item was reported damaged.",
            reasoning="The claim matches the selected reason.",
            customer_message="Your claim has been recorded.",
        ))
        order, items = self.make_order()

        response = self.create_refund(order, items)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["status"], RefundRequest.Status.APPROVED)
        self.assertEqual(response.data["ai_assistance"]["available"], True)
        self.assertEqual(response.data["ai_assistance"]["customer_message"], "Your claim has been recorded.")
        self.assertEqual(set(response.data["ai_assistance"]), {"available", "customer_message"})
        self.assertEqual(RefundAIAssistance.objects.get().risk, "low")
        history_response = self.client.get(
            reverse("refund-request-list-create"), {"order_reference": order.reference}
        )
        self.assertEqual(
            history_response.data[0]["ai_assistance"]["customer_message"],
            "Your claim has been recorded.",
        )

    def test_final_sale_item_is_denied(self):
        order, items = self.make_order(item_specs=(("FS-1", "Final sale", "25.00", True),))

        response = self.create_refund(order, items)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["status"], RefundRequest.Status.REJECTED)
        self.assertEqual(response.data["items"][0]["decision"], "rejected")
        self.assertIn("Final-sale", response.data["items"][0]["decision_reason"])

    def test_expired_order_is_denied(self):
        order, items = self.make_order(age_days=31)

        response = self.create_refund(order, items)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["policy_outcome"], "rejected")
        self.assertIn("30-day", response.data["items"][0]["decision_reason"])

    def test_high_value_request_is_escalated(self):
        order, items = self.make_order(item_specs=(("HIGH-1", "High value", "500.01", False),))

        response = self.create_refund(order, items)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["status"], RefundRequest.Status.ESCALATED)
        self.assertIn("above $500", response.data["items"][0]["decision_reason"])

    def test_mixed_item_request_returns_separate_decisions(self):
        order, items = self.make_order(
            item_specs=(
                ("ELIGIBLE-1", "Eligible item", "25.00", False),
                ("FINAL-1", "Final-sale item", "15.00", True),
            )
        )

        response = self.create_refund(order, items)

        decisions = {item["order_item"]["id"]: item["decision"] for item in response.data["items"]}
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["policy_outcome"], "approved")
        self.assertEqual(decisions[items[0].id], "approved")
        self.assertEqual(decisions[items[1].id], "rejected")

    def test_history_filters_by_order_and_rejects_items_from_another_order(self):
        order, items = self.make_order()
        other_order, other_items = self.make_order()
        self.create_refund(order, items)

        history_response = self.client.get(
            reverse("refund-request-list-create"), {"order_reference": order.reference}
        )
        invalid_response = self.create_refund(order, other_items)

        self.assertEqual(history_response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(history_response.data), 1)
        self.assertEqual(history_response.data[0]["order_reference"], order.reference)
        self.assertEqual(invalid_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("items", invalid_response.data)

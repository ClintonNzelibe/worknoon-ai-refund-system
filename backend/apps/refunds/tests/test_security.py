from datetime import timedelta
from decimal import Decimal
import os
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.audit.models import AuditLog
from apps.customers.models import Customer
from apps.orders.models import Order, OrderItem
from apps.refunds.models import RefundRequest


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
@patch.dict(os.environ, {"OPENAI_API_KEY": ""})
class RefundSecurityTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.owner = user_model.objects.create_user("owner", password="test-password")
        self.other_user = user_model.objects.create_user("other", password="test-password")
        self.staff = user_model.objects.create_user("staff", password="test-password", is_staff=True)
        self.owner_customer = Customer.objects.create(
            user=self.owner,
            full_name="Order Owner",
            email="owner@example.test",
        )
        self.other_customer = Customer.objects.create(
            user=self.other_user,
            full_name="Other Customer",
            email="other@example.test",
        )
        self.owner_order, self.owner_item = self.make_order(self.owner_customer, "SEC-OWNER", quantity=2)
        self.second_owner_order, self.second_owner_item = self.make_order(
            self.owner_customer,
            "SEC-OWNER-SECOND",
        )
        self.other_order, self.other_item = self.make_order(self.other_customer, "SEC-OTHER")
        self.client = APIClient()
        self.client.force_authenticate(self.owner)

    def make_order(self, customer, reference, *, quantity=1):
        order = Order.objects.create(
            customer=customer,
            reference=reference,
            status=Order.Status.PAID,
            total_amount=Decimal("25.00"),
            ordered_at=timezone.now() - timedelta(days=2),
        )
        item = OrderItem.objects.create(
            order=order,
            sku=f"{reference}-SKU",
            product_name="Security test item",
            unit_price=Decimal("25.00"),
            quantity=quantity,
        )
        return order, item

    def create_payload(self, order, item, quantity=1):
        return {
            "order_reference": order.reference,
            "reason_code": "damaged",
            "reason": "The item arrived damaged.",
            "items": [{"order_item_id": item.id, "requested_quantity": quantity}],
        }

    def test_customer_lookup_rejects_another_customers_email_with_generic_response(self):
        customer_response = self.client.get(
            reverse("customer-lookup"), {"email": self.other_customer.email}
        )
        self.assertEqual(customer_response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(customer_response.data, {"detail": "Order not found or unavailable."})

    def test_customer_cannot_lookup_another_customers_order_or_items(self):
        response = self.client.get(reverse("order-lookup", args=[self.other_order.reference]))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data, {"detail": "Order not found or unavailable."})
        self.assertNotIn("items", response.data)
        self.assertNotIn("total_amount", response.data)

    def test_owner_can_lookup_only_their_own_email_and_order(self):
        customer_response = self.client.get(reverse("customer-lookup"), {"email": self.owner_customer.email})
        order_response = self.client.get(reverse("order-lookup", args=[self.owner_order.reference]))
        self.assertEqual(customer_response.status_code, status.HTTP_200_OK)
        self.assertIn(
            self.owner_order.reference,
            [order["reference"] for order in customer_response.data["orders"]],
        )
        self.assertEqual(order_response.status_code, status.HTTP_200_OK)
        self.assertEqual(order_response.data["items"][0]["id"], self.owner_item.id)

    def test_manipulated_customer_id_and_order_reference_do_not_bypass_history_scope(self):
        self.client.post(
            reverse("refund-request-list-create"), self.create_payload(self.owner_order, self.owner_item),
            format="json", HTTP_IDEMPOTENCY_KEY="security-own-history-key",
        )
        response = self.client.get(
            reverse("refund-request-list-create"),
            {"customer_id": self.other_customer.id, "order_reference": self.other_order.reference},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, [])

    def test_customer_cannot_submit_a_refund_for_another_customers_order(self):
        response = self.client.post(
            reverse("refund-request-list-create"),
            self.create_payload(self.other_order, self.other_item),
            format="json",
            HTTP_IDEMPOTENCY_KEY="security-cross-order-key",
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data, {"detail": "Order not found or unavailable."})
        self.assertEqual(RefundRequest.objects.count(), 0)

    def test_customer_cannot_inject_another_orders_item_id_into_their_request(self):
        response = self.client.post(
            reverse("refund-request-list-create"),
            self.create_payload(self.owner_order, self.other_item),
            format="json",
            HTTP_IDEMPOTENCY_KEY="security-cross-item-key",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("items", response.data)
        self.assertEqual(RefundRequest.objects.count(), 0)

    def test_staff_retains_legitimate_cross_customer_lookup_access(self):
        staff_client = APIClient()
        staff_client.force_authenticate(self.staff)
        customer_response = staff_client.get(
            reverse("customer-lookup"), {"email": self.other_customer.email}
        )
        order_response = staff_client.get(reverse("order-lookup", args=[self.other_order.reference]))
        self.assertEqual(customer_response.status_code, status.HTTP_200_OK)
        self.assertEqual(order_response.status_code, status.HTTP_200_OK)
        self.assertEqual(order_response.data["reference"], self.other_order.reference)

    def test_idempotency_key_prevents_duplicate_requests_and_audit_events(self):
        payload = self.create_payload(self.owner_order, self.owner_item)
        key = "security-duplicate-key"

        first_response = self.client.post(
            reverse("refund-request-list-create"),
            payload,
            format="json",
            HTTP_IDEMPOTENCY_KEY=key,
        )
        second_response = self.client.post(
            reverse("refund-request-list-create"),
            payload,
            format="json",
            HTTP_IDEMPOTENCY_KEY=key,
        )

        refund_request = RefundRequest.objects.get()
        self.assertEqual(first_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(second_response.status_code, status.HTTP_200_OK)
        self.assertEqual(RefundRequest.objects.count(), 1)
        self.assertEqual(refund_request.audit_logs.count(), 3)
        self.assertEqual(second_response.data["id"], first_response.data["id"])

    def test_reused_idempotency_key_for_another_order_is_rejected(self):
        key = "security-key-reuse"
        self.client.post(
            reverse("refund-request-list-create"),
            self.create_payload(self.owner_order, self.owner_item),
            format="json",
            HTTP_IDEMPOTENCY_KEY=key,
        )

        response = self.client.post(
            reverse("refund-request-list-create"),
            self.create_payload(self.second_owner_order, self.second_owner_item),
            format="json",
            HTTP_IDEMPOTENCY_KEY=key,
        )

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)

    def test_oversized_requested_quantity_is_rejected_before_policy_evaluation(self):
        response = self.client.post(
            reverse("refund-request-list-create"),
            self.create_payload(self.owner_order, self.owner_item, quantity=3),
            format="json",
            HTTP_IDEMPOTENCY_KEY="security-quantity-key",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("items", response.data)
        self.assertEqual(RefundRequest.objects.count(), 0)

    def test_missing_or_short_idempotency_keys_are_rejected(self):
        response = self.client.post(
            reverse("refund-request-list-create"),
            self.create_payload(self.owner_order, self.owner_item),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("idempotency_key", response.data)

    def test_audit_log_is_created_for_request_and_policy_evaluation(self):
        response = self.client.post(
            reverse("refund-request-list-create"),
            self.create_payload(self.owner_order, self.owner_item),
            format="json",
            HTTP_IDEMPOTENCY_KEY="security-audit-key",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(
            set(AuditLog.objects.values_list("action", flat=True)),
            {"refund_request_created", "policy_evaluated", "ai_assistance_unavailable"},
        )


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
@patch.dict(os.environ, {"OPENAI_API_KEY": ""})
class DiegoSeededOwnershipRegressionTests(TestCase):
    """Regression coverage for the concrete browser-testing seed scenario."""

    def setUp(self):
        call_command("seed_synthetic_refunds")
        self.diego = Customer.objects.select_related("user").get(
            email="diego.ramos@example.test",
        )
        self.unauthorized_order = Order.objects.get(reference="SYN-004")
        self.owned_order = Order.objects.get(reference="SYN-005")
        self.client = APIClient()
        self.client.force_authenticate(self.diego.user)

    def test_diego_can_only_retrieve_syn_005_and_syn_004_is_generic_not_found(self):
        denied = self.client.get(reverse("order-lookup", args=["SYN-004"]))
        allowed = self.client.get(reverse("order-lookup", args=["SYN-005"]))

        self.assertEqual(self.diego.user_id, self.owned_order.customer.user_id)
        self.assertNotEqual(self.diego.user_id, self.unauthorized_order.customer.user_id)
        self.assertEqual(denied.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(denied.data, {"detail": "Order not found or unavailable."})
        self.assertNotIn("items", denied.data)
        self.assertNotIn("total_amount", denied.data)
        self.assertEqual(allowed.status_code, status.HTTP_200_OK)
        self.assertEqual(allowed.data["reference"], "SYN-005")

    def test_diego_cannot_bypass_scope_with_reference_casing_encoding_or_query_parameters(self):
        for reference in ("SYN-004", "syn-004", "SYN%2D004"):
            response = self.client.get(
                f"{reverse('order-lookup', args=[reference])}?customer_id={self.unauthorized_order.customer_id}&order_id={self.unauthorized_order.id}",
            )
            self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
            self.assertEqual(response.data, {"detail": "Order not found or unavailable."})

    def test_diego_cannot_create_or_retrieve_refunds_for_syn_004(self):
        requests_before = RefundRequest.objects.count()
        create_response = self.client.post(
            reverse("refund-request-list-create"),
            {
                "order_reference": "SYN-004",
                "reason_code": "damaged",
                "reason": "Attempting an unauthorized request.",
                "items": [{"order_item_id": self.unauthorized_order.items.get().id, "requested_quantity": 1}],
            },
            format="json",
            HTTP_IDEMPOTENCY_KEY="diego-cross-customer-key",
        )
        history_response = self.client.get(
            reverse("refund-request-list-create"),
            {"order_reference": "SYN-004", "customer_id": self.unauthorized_order.customer_id},
        )

        self.assertEqual(create_response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(create_response.data, {"detail": "Order not found or unavailable."})
        self.assertEqual(RefundRequest.objects.count(), requests_before)
        self.assertEqual(history_response.status_code, status.HTTP_200_OK)
        self.assertEqual(history_response.data, [])

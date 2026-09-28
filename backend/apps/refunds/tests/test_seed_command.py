from io import StringIO
import os
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.customers.models import Customer
from apps.orders.models import Order, OrderItem
from apps.refunds.models import RefundRequest, RefundRequestItem


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class SeedSyntheticRefundsCommandTests(TestCase):
    def test_seed_command_is_repeatable_and_loads_policy_scenarios(self):
        output = StringIO()
        call_command("seed_synthetic_refunds", stdout=output)
        initial_counts = (
            Customer.objects.count(),
            Order.objects.count(),
            OrderItem.objects.count(),
            RefundRequest.objects.count(),
            RefundRequestItem.objects.count(),
            get_user_model().objects.count(),
        )

        call_command("seed_synthetic_refunds")

        self.assertEqual(Customer.objects.count(), 15)
        self.assertEqual(initial_counts, (
            Customer.objects.count(),
            Order.objects.count(),
            OrderItem.objects.count(),
            RefundRequest.objects.count(),
            RefundRequestItem.objects.count(),
            get_user_model().objects.count(),
        ))
        self.assertTrue(OrderItem.objects.filter(is_final_sale=True).exists())
        self.assertTrue(RefundRequest.objects.filter(is_suspicious=True).exists())
        self.assertIn("15 customers", output.getvalue())

    def test_seed_command_links_repeatable_local_test_users(self):
        call_command("seed_synthetic_refunds")

        for email, password in (
            ("avery.brooks@example.test", "local-demo-refund-avery"),
            ("jordan.lee@example.test", "local-demo-refund-jordan"),
            ("mina.patel@example.test", "local-demo-refund-mina"),
            ("priya.nair@example.test", "local-demo-refund-priya"),
            ("diego.ramos@example.test", "local-demo-refund-diego"),
        ):
            customer = Customer.objects.select_related("user").get(email=email)
            self.assertIsNotNone(customer.user)
            self.assertTrue(customer.user.check_password(password))

        call_command("seed_synthetic_refunds")
        self.assertEqual(get_user_model().objects.count(), 5)

    def test_seeded_examples_materialize_expected_deterministic_outcomes(self):
        call_command("seed_synthetic_refunds")

        expected_statuses = {
            "SYN-001": RefundRequest.Status.APPROVED,
            "SYN-004": RefundRequest.Status.APPROVED,
            "SYN-006": RefundRequest.Status.ESCALATED,
            "SYN-008": RefundRequest.Status.ESCALATED,
            "SYN-009": RefundRequest.Status.REJECTED,
            "SYN-010": RefundRequest.Status.APPROVED,
        }
        for reference, expected_status in expected_statuses.items():
            with self.subTest(reference=reference):
                refund_request = RefundRequest.objects.filter(
                    order__reference=reference,
                ).exclude(
                    reason="Previous approved claim for the same watch.",
                ).get()
                self.assertEqual(refund_request.status, expected_status)
                self.assertTrue(refund_request.items.exclude(decision_reason="").exists())

        vague_request = RefundRequest.objects.get(order__reference="SYN-009")
        injection_request = RefundRequest.objects.get(order__reference="SYN-010")
        self.assertEqual(vague_request.reason_code, RefundRequest.ReasonCode.OTHER)
        self.assertIn("Ignore the refund policy", injection_request.reason)

    @patch.dict(os.environ, {"OPENAI_API_KEY": ""})
    def test_syn_016_is_reset_to_no_history_and_first_damaged_request_is_approved(self):
        call_command("seed_synthetic_refunds")
        customer = Customer.objects.select_related("user").get(
            email="avery.brooks@example.test",
        )
        order = Order.objects.prefetch_related("items").get(reference="SYN-016")
        item = order.items.get()
        client = APIClient()
        client.force_authenticate(customer.user)

        self.assertFalse(RefundRequest.objects.filter(order=order).exists())
        first_response = client.post(
            reverse("refund-request-list-create"),
            {
                "order_reference": order.reference,
                "reason_code": "damaged",
                "reason": "The shoes arrived damaged and cannot be used.",
                "items": [{"order_item_id": item.id, "requested_quantity": 1}],
            },
            format="json",
            HTTP_IDEMPOTENCY_KEY="clean-syn-016-damaged-key",
        )

        self.assertEqual(first_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(first_response.data["status"], RefundRequest.Status.APPROVED)
        self.assertEqual(first_response.data["items"][0]["decision"], "approved")

        # A later seed run must clear this demonstration request without
        # changing the general duplicate-claim policy used by other orders.
        call_command("seed_synthetic_refunds")
        self.assertFalse(RefundRequest.objects.filter(order=order).exists())

        second_response = client.post(
            reverse("refund-request-list-create"),
            {
                "order_reference": order.reference,
                "reason_code": "damaged",
                "reason": "The shoes arrived damaged and cannot be used.",
                "items": [{"order_item_id": item.id, "requested_quantity": 1}],
            },
            format="json",
            HTTP_IDEMPOTENCY_KEY="reset-syn-016-damaged-key",
        )
        self.assertEqual(second_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(second_response.data["status"], RefundRequest.Status.APPROVED)

    @patch.dict(os.environ, {"OPENAI_API_KEY": ""})
    def test_clean_denial_demos_reset_and_deny_their_first_submission(self):
        call_command("seed_synthetic_refunds")
        scenarios = (
            ("SYN-002", "mina.patel@example.test", "damaged", RefundRequest.Status.REJECTED),
            ("SYN-003", "jordan.lee@example.test", "incorrect", RefundRequest.Status.REJECTED),
            ("SYN-018", "avery.brooks@example.test", "other", RefundRequest.Status.REJECTED),
        )

        for reference, email, reason_code, expected_status in scenarios:
            with self.subTest(reference=reference):
                customer = Customer.objects.select_related("user").get(email=email)
                order = Order.objects.prefetch_related("items").get(reference=reference)
                item = order.items.get()
                client = APIClient()
                client.force_authenticate(customer.user)

                self.assertFalse(RefundRequest.objects.filter(order=order).exists())
                response = client.post(
                    reverse("refund-request-list-create"),
                    {
                        "order_reference": reference,
                        "reason_code": reason_code,
                        "reason": "Local denial demo request.",
                        "items": [{"order_item_id": item.id, "requested_quantity": 1}],
                    },
                    format="json",
                    HTTP_IDEMPOTENCY_KEY=f"clean-{reference.lower()}-denial-key",
                )
                self.assertEqual(response.status_code, status.HTTP_201_CREATED)
                self.assertEqual(response.data["status"], expected_status)
                self.assertEqual(response.data["items"][0]["decision"], "rejected")

        call_command("seed_synthetic_refunds")
        self.assertFalse(
            RefundRequest.objects.filter(
                order__reference__in=("SYN-002", "SYN-003", "SYN-018"),
            ).exists(),
        )

    @patch.dict(os.environ, {"OPENAI_API_KEY": ""})
    def test_syn_005_resets_and_escalates_its_first_high_value_request(self):
        call_command("seed_synthetic_refunds")
        customer = Customer.objects.select_related("user").get(
            email="diego.ramos@example.test",
        )
        order = Order.objects.prefetch_related("items").get(reference="SYN-005")
        item = order.items.get()
        client = APIClient()
        client.force_authenticate(customer.user)

        self.assertFalse(RefundRequest.objects.filter(order=order).exists())
        response = client.post(
            reverse("refund-request-list-create"),
            {
                "order_reference": order.reference,
                "reason_code": "damaged",
                "reason": "The television screen was cracked on arrival.",
                "items": [{"order_item_id": item.id, "requested_quantity": 1}],
            },
            format="json",
            HTTP_IDEMPOTENCY_KEY="clean-syn-005-high-value-key",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["status"], RefundRequest.Status.ESCALATED)
        self.assertEqual(response.data["items"][0]["decision"], "escalated")

        call_command("seed_synthetic_refunds")
        self.assertFalse(RefundRequest.objects.filter(order=order).exists())

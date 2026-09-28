from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from django.test import TestCase
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.customers.models import Customer
from apps.orders.models import Order, OrderItem
from apps.refunds.models import RefundRequest


class RefundDataModelTests(TestCase):
    def setUp(self):
        self.customer = Customer.objects.create(
            full_name="Avery Smith",
            email="avery@example.com",
        )
        self.order = Order.objects.create(
            customer=self.customer,
            reference="ORD-1001",
            status=Order.Status.PAID,
            total_amount=Decimal("24.00"),
            ordered_at=timezone.now() - timedelta(days=1),
        )

    def test_customer_order_refund_and_audit_relationships(self):
        item = OrderItem.objects.create(
            order=self.order,
            sku="SKU-1",
            product_name="Example item",
            unit_price=Decimal("12.00"),
            quantity=2,
        )
        refund = RefundRequest.objects.create(
            order=self.order,
            reason="Item arrived damaged.",
            requested_amount=Decimal("12.00"),
        )
        audit_log = AuditLog.objects.create(
            refund_request=refund,
            action="created",
            metadata={"source": "customer"},
        )

        self.assertEqual(list(self.customer.orders.all()), [self.order])
        self.assertEqual(list(self.order.items.all()), [item])
        self.assertEqual(list(self.order.refund_requests.all()), [refund])
        self.assertEqual(list(refund.audit_logs.all()), [audit_log])
        self.assertEqual(item.line_total, Decimal("24.00"))

    def test_database_constraints_reject_invalid_amounts_and_quantities(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Order.objects.create(
                customer=self.customer,
                reference="ORD-NEGATIVE",
                total_amount=Decimal("-1.00"),
                ordered_at=timezone.now(),
            )

        with self.assertRaises(IntegrityError), transaction.atomic():
            OrderItem.objects.create(
                order=self.order,
                sku="SKU-INVALID",
                product_name="Invalid quantity",
                unit_price=Decimal("1.00"),
                quantity=0,
            )

        with self.assertRaises(IntegrityError), transaction.atomic():
            RefundRequest.objects.create(
                order=self.order,
                reason="Invalid request.",
                requested_amount=Decimal("0.00"),
            )

    def test_protected_relations_preserve_refund_history(self):
        refund = RefundRequest.objects.create(
            order=self.order,
            reason="No longer needed.",
            requested_amount=Decimal("10.00"),
        )
        AuditLog.objects.create(refund_request=refund, action="created")

        with self.assertRaises(ProtectedError):
            self.order.delete()

        with self.assertRaises(ProtectedError):
            refund.delete()

    def test_customer_email_and_order_reference_are_unique(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Customer.objects.create(full_name="Duplicate", email=self.customer.email)

        with self.assertRaises(IntegrityError), transaction.atomic():
            Order.objects.create(
                customer=self.customer,
                reference=self.order.reference,
                total_amount=Decimal("1.00"),
                ordered_at=timezone.now(),
            )

    def test_audit_logs_cannot_be_changed_or_deleted(self):
        refund = RefundRequest.objects.create(
            order=self.order,
            reason="Damaged item.",
            requested_amount=Decimal("12.00"),
        )
        audit_log = AuditLog.objects.create(refund_request=refund, action="created")

        audit_log.message = "Changed"
        with self.assertRaises(ValidationError):
            audit_log.save()
        with self.assertRaises(ValidationError):
            audit_log.delete()
        with self.assertRaises(ValidationError):
            AuditLog.objects.filter(pk=audit_log.pk).update(message="Changed")

from decimal import Decimal

from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.audit.models import AuditLog
from apps.customers.models import Customer
from apps.orders.models import Order

from .ai_service import customer_assistance_as_dict, ensure_refund_assistance
from .models import RefundRequest, RefundRequestItem
from .permissions import can_access_customer
from .policy import PolicyDecision, evaluate_refund_request
from .serializers import (
    CustomerLookupSerializer,
    OrderLookupSerializer,
    RefundRequestCreateSerializer,
    RefundRequestSerializer,
)


class CustomerLookupAPIView(APIView):
    """Return order summaries only for the authenticated customer's account."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        email = request.query_params.get("email")
        if not email:
            return Response(
                {"detail": "The email query parameter is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        customer = _accessible_customers(request).prefetch_related("orders").filter(
            email__iexact=email,
        ).first()
        if customer is None:
            return _order_unavailable_response()
        return Response(CustomerLookupSerializer(customer).data)


class OrderLookupAPIView(APIView):
    """Return an order only when it belongs to the authenticated customer."""

    permission_classes = [IsAuthenticated]

    def get(self, request, reference):
        order = _accessible_orders(request).prefetch_related("items").filter(
            reference=reference,
        ).first()
        if order is None:
            return _order_unavailable_response()
        return Response(OrderLookupSerializer(order).data)


class RefundRequestListCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        queryset = _refund_queryset(request)
        order_reference = request.query_params.get("order_reference")
        customer_id = request.query_params.get("customer_id")
        if order_reference:
            queryset = queryset.filter(order__reference=order_reference)
        if customer_id:
            queryset = queryset.filter(order__customer_id=customer_id)
        return Response([_serialized_refund(refund_request) for refund_request in queryset])

    @transaction.atomic
    def post(self, request):
        # Resolve against an ownership-scoped queryset before serializer
        # validation so an attacker cannot use this endpoint to probe orders.
        order_reference = request.data.get("order_reference")
        if isinstance(order_reference, str) and order_reference.strip():
            if not _accessible_orders(request).filter(reference=order_reference.strip()).exists():
                return _order_unavailable_response()
        serializer = RefundRequestCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data
        order = validated_data["order"]
        order_items = validated_data["order_items"]
        if not can_access_customer(request.user, order.customer):
            raise PermissionDenied("You cannot create a refund request for this order.")

        idempotency_key = request.headers.get("Idempotency-Key", "").strip()
        if not 8 <= len(idempotency_key) <= 64:
            return Response(
                {"idempotency_key": "Provide an Idempotency-Key between 8 and 64 characters."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        existing_request = RefundRequest.objects.filter(idempotency_key=idempotency_key).first()
        if existing_request:
            if existing_request.order_id != order.id:
                return Response(
                    {"detail": "This idempotency key is already associated with another request."},
                    status=status.HTTP_409_CONFLICT,
                )
            return _refund_response(existing_request, status.HTTP_200_OK)

        requested_amount = sum(
            (
                order_items[item["order_item_id"]].unit_price
                * item["requested_quantity"]
                for item in validated_data["items"]
            ),
            Decimal("0.00"),
        )

        try:
            # A savepoint lets a concurrent repeat request return the original safely.
            with transaction.atomic():
                refund_request = RefundRequest.objects.create(
                    order=order,
                    reason_code=validated_data["reason_code"],
                    reason=validated_data["reason"],
                    requested_amount=requested_amount,
                    idempotency_key=idempotency_key,
                )
        except IntegrityError:
            return _refund_response(
                RefundRequest.objects.get(idempotency_key=idempotency_key),
                status.HTTP_200_OK,
            )
        request_items = [
            RefundRequestItem(
                refund_request=refund_request,
                order_item=order_items[item["order_item_id"]],
                requested_quantity=item["requested_quantity"],
            )
            for item in validated_data["items"]
        ]
        RefundRequestItem.objects.bulk_create(request_items)

        # The policy remains pure; this API layer persists its deterministic result.
        policy_result = evaluate_refund_request(refund_request)
        decisions = {item.refund_request_item_id: item for item in policy_result.item_decisions}
        persisted_items = list(refund_request.items.all())
        for request_item in persisted_items:
            policy_item = decisions[request_item.id]
            request_item.decision = policy_item.decision.value
            request_item.decision_reason = policy_item.reason
        RefundRequestItem.objects.bulk_update(
            persisted_items,
            ["decision", "decision_reason"],
        )

        refund_request.status = _status_for(policy_result.outcome)
        refund_request.resolution_note = _resolution_note(policy_result)
        if policy_result.outcome != PolicyDecision.ESCALATED:
            refund_request.resolved_at = timezone.now()
        refund_request.save(update_fields=["status", "resolution_note", "resolved_at", "updated_at"])
        AuditLog.objects.create(refund_request=refund_request, action="refund_request_created")
        AuditLog.objects.create(
            refund_request=refund_request,
            action="policy_evaluated",
            metadata={"outcome": policy_result.outcome.value},
        )

        return _refund_response(refund_request, status.HTTP_201_CREATED)


def _refund_queryset(request):
    queryset = RefundRequest.objects.select_related("order__customer", "ai_assistance").prefetch_related(
        "items__order_item"
    )
    if not request.user.is_staff:
        queryset = queryset.filter(order__customer__user=request.user)
    return queryset


def _accessible_customers(request):
    queryset = Customer.objects.all()
    if request.user.is_staff:
        return queryset
    return queryset.filter(user=request.user)


def _accessible_orders(request):
    queryset = Order.objects.all()
    if request.user.is_staff:
        return queryset
    return queryset.filter(customer__user=request.user)


def _order_unavailable_response():
    return Response(
        {"detail": "Order not found or unavailable."},
        status=status.HTTP_404_NOT_FOUND,
    )


def _refund_response(refund_request, response_status):
    refund_request = (
        RefundRequest.objects.select_related("order__customer", "ai_assistance")
        .prefetch_related("items__order_item")
        .get(pk=refund_request.pk)
    )
    return Response(_serialized_refund(refund_request), status=response_status)


def _serialized_refund(refund_request):
    response_data = RefundRequestSerializer(refund_request).data
    response_data["ai_assistance"] = customer_assistance_as_dict(
        ensure_refund_assistance(refund_request)
    )
    return response_data


def _status_for(outcome: PolicyDecision) -> str:
    if outcome == PolicyDecision.APPROVED:
        return RefundRequest.Status.APPROVED
    if outcome == PolicyDecision.ESCALATED:
        return RefundRequest.Status.ESCALATED
    return RefundRequest.Status.REJECTED


def _resolution_note(policy_result) -> str:
    counts = {decision: 0 for decision in PolicyDecision}
    for item in policy_result.item_decisions:
        counts[item.decision] += 1
    return (
        f"Deterministic policy: {counts[PolicyDecision.APPROVED]} approved, "
        f"{counts[PolicyDecision.REJECTED]} rejected, "
        f"{counts[PolicyDecision.ESCALATED]} escalated."
    )

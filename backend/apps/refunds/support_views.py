from django.core.paginator import EmptyPage, Paginator
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.audit.models import AuditLog

from .ai_service import assistance_as_dict, ensure_refund_assistance
from .models import RefundRequest, RefundRequestItem
from .permissions import IsSupportUser
from .support_serializers import SupportRefundRequestSerializer, SupportReviewSerializer


PAGE_SIZE = 10


class SupportRefundRequestListAPIView(APIView):
    permission_classes = [IsSupportUser]

    def get(self, request):
        queryset = _support_queryset()
        status_filter = request.query_params.get("status")
        customer_email = request.query_params.get("customer_email")
        order_reference = request.query_params.get("order_reference")

        if status_filter:
            if status_filter not in RefundRequest.Status.values:
                return Response(
                    {"status": "Use a valid refund status."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            queryset = queryset.filter(status=status_filter)
        if customer_email:
            queryset = queryset.filter(order__customer__email__icontains=customer_email)
        if order_reference:
            queryset = queryset.filter(order__reference__icontains=order_reference)

        page_number = _page_number(request.query_params.get("page"))
        paginator = Paginator(queryset, PAGE_SIZE)
        if paginator.count == 0:
            return Response(
                {"count": 0, "page": 1, "page_size": PAGE_SIZE, "total_pages": 0, "results": []}
            )
        try:
            page = paginator.page(page_number)
        except EmptyPage:
            return Response(
                {"detail": "That page does not exist."},
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response(
            {
                "count": paginator.count,
                "page": page.number,
                "page_size": PAGE_SIZE,
                "total_pages": paginator.num_pages,
                "results": SupportRefundRequestSerializer(page.object_list, many=True).data,
            }
        )


class SupportRefundRequestDetailAPIView(APIView):
    permission_classes = [IsSupportUser]

    def get(self, request, refund_request_id):
        refund_request = get_object_or_404(_support_queryset(), pk=refund_request_id)
        response_data = SupportRefundRequestSerializer(refund_request).data
        # AI assistance remains supplementary and is never persisted as a policy decision.
        response_data["ai_assistance"] = assistance_as_dict(ensure_refund_assistance(refund_request))
        return Response(response_data)


class SupportRefundReviewAPIView(APIView):
    permission_classes = [IsSupportUser]

    @transaction.atomic
    def post(self, request, refund_request_id):
        refund_request = get_object_or_404(
            RefundRequest.objects.select_for_update().select_related("order__customer"),
            pk=refund_request_id,
        )
        serializer = SupportReviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        if refund_request.status != RefundRequest.Status.ESCALATED:
            return Response(
                {"detail": "Only escalated refund requests can be reviewed."},
                status=status.HTTP_409_CONFLICT,
            )

        reviewable_items = list(refund_request.items.select_for_update().filter(
            decision=RefundRequestItem.Decision.ESCALATED
        ))
        if not reviewable_items:
            return Response(
                {"detail": "This request has no items awaiting human review."},
                status=status.HTTP_409_CONFLICT,
            )

        decision = serializer.validated_data["decision"]
        note = serializer.validated_data["note"]
        item_decision = (
            RefundRequestItem.Decision.APPROVED
            if decision == "approved"
            else RefundRequestItem.Decision.REJECTED
        )
        for item in reviewable_items:
            item.decision = item_decision
            item.decision_reason = f"Human review: {note}"
        RefundRequestItem.objects.bulk_update(reviewable_items, ["decision", "decision_reason"])

        # Fetch fresh values because bulk_update does not refresh prefetched relations.
        remaining_items = list(RefundRequestItem.objects.filter(refund_request=refund_request))
        refund_request.status = _status_after_review(remaining_items)
        refund_request.resolution_note = f"Human review ({decision}): {note}"
        refund_request.resolved_at = timezone.now()
        refund_request.save(update_fields=["status", "resolution_note", "resolved_at", "updated_at"])
        AuditLog.objects.create(
            refund_request=refund_request,
            action="human_reviewed",
            message=note,
            metadata={
                "decision": decision,
                "reviewer_id": request.user.id,
                "reviewed_item_ids": [item.id for item in reviewable_items],
            },
        )

        refund_request = get_object_or_404(_support_queryset(), pk=refund_request.pk)
        return Response(SupportRefundRequestSerializer(refund_request).data)


def _support_queryset():
    return RefundRequest.objects.select_related("order__customer", "ai_assistance").prefetch_related(
        "items__order_item",
        "audit_logs",
    )


def _page_number(value):
    try:
        return max(1, int(value or 1))
    except ValueError:
        return 1


def _status_after_review(items):
    if any(item.decision == RefundRequestItem.Decision.ESCALATED for item in items):
        return RefundRequest.Status.ESCALATED
    if any(item.decision == RefundRequestItem.Decision.APPROVED for item in items):
        return RefundRequest.Status.APPROVED
    return RefundRequest.Status.REJECTED

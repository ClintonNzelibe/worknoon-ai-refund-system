from django.urls import path

from apps.customers.views import (
    CustomerCsrfAPIView,
    CustomerLoginAPIView,
    CustomerLogoutAPIView,
    CustomerSessionAPIView,
    StaffLoginAPIView,
    StaffSessionAPIView,
)

from .views import (
    CustomerLookupAPIView,
    OrderLookupAPIView,
    RefundRequestListCreateAPIView,
)
from .support_views import (
    SupportRefundRequestDetailAPIView,
    SupportRefundRequestListAPIView,
    SupportRefundReviewAPIView,
)


urlpatterns = [
    path("auth/csrf/", CustomerCsrfAPIView.as_view(), name="customer-auth-csrf"),
    path("auth/login/", CustomerLoginAPIView.as_view(), name="customer-login"),
    path("auth/session/", CustomerSessionAPIView.as_view(), name="customer-session"),
    path("auth/logout/", CustomerLogoutAPIView.as_view(), name="customer-logout"),
    path("auth/staff/login/", StaffLoginAPIView.as_view(), name="staff-login"),
    path("auth/staff/session/", StaffSessionAPIView.as_view(), name="staff-session"),
    path("customers/lookup/", CustomerLookupAPIView.as_view(), name="customer-lookup"),
    path("orders/<str:reference>/", OrderLookupAPIView.as_view(), name="order-lookup"),
    path("refund-requests/", RefundRequestListCreateAPIView.as_view(), name="refund-request-list-create"),
    path("support/refund-requests/", SupportRefundRequestListAPIView.as_view(), name="support-refund-list"),
    path("support/refund-requests/<int:refund_request_id>/", SupportRefundRequestDetailAPIView.as_view(), name="support-refund-detail"),
    path("support/refund-requests/<int:refund_request_id>/review/", SupportRefundReviewAPIView.as_view(), name="support-refund-review"),
]

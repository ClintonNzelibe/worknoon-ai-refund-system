from rest_framework.permissions import BasePermission


class IsSupportUser(BasePermission):
    """Support endpoints are restricted to Django staff users."""

    message = "Support staff access is required."

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_staff)


def can_access_customer(user, customer):
    """Staff may assist all customers; customer accounts may access only their own data."""
    return bool(user.is_staff or customer.user_id == user.id)

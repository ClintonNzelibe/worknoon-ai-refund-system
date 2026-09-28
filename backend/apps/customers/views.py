"""Session authentication endpoints for the customer-facing application."""

from django.contrib.auth import authenticate, login, logout
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Customer


class CustomerCsrfAPIView(APIView):
    """Set the CSRF cookie before a browser submits customer credentials."""

    permission_classes = [AllowAny]

    @method_decorator(ensure_csrf_cookie)
    def get(self, request):
        return Response(status=status.HTTP_204_NO_CONTENT)


@method_decorator(csrf_protect, name="dispatch")
class CustomerLoginAPIView(APIView):
    """Authenticate a linked customer and establish Django's normal session."""

    permission_classes = [AllowAny]

    def post(self, request):
        email = str(request.data.get("email", "")).strip()
        password = str(request.data.get("password", ""))
        customer = (
            Customer.objects.select_related("user")
            .filter(email__iexact=email, user__isnull=False)
            .first()
        )
        user = (
            authenticate(request, username=customer.user.get_username(), password=password)
            if customer else None
        )
        if user is None:
            return Response(
                {"detail": "Invalid email or password."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        login(request, user)
        return Response({"email": customer.email, "full_name": customer.full_name})


class CustomerSessionAPIView(APIView):
    """Return the linked customer identity for the current Django session."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        customer = Customer.objects.filter(user=request.user).first()
        if customer is None:
            return Response(
                {"detail": "Customer session unavailable."},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response({"email": customer.email, "full_name": customer.full_name})


@method_decorator(csrf_protect, name="dispatch")
class StaffLoginAPIView(APIView):
    """Establish the normal Django session only for an authenticated staff user."""

    permission_classes = [AllowAny]

    def post(self, request):
        username = str(request.data.get("username", "")).strip()
        password = str(request.data.get("password", ""))
        user = authenticate(request, username=username, password=password)
        if user is None or not user.is_staff:
            return Response(
                {"detail": "Invalid staff credentials."},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        login(request, user)
        return Response({"username": user.get_username()})


class StaffSessionAPIView(APIView):
    """Return the active staff session without exposing any customer data."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not request.user.is_staff:
            return Response(
                {"detail": "Support staff access is required."},
                status=status.HTTP_403_FORBIDDEN,
            )
        return Response({"username": request.user.get_username()})


@method_decorator(csrf_protect, name="dispatch")
class CustomerLogoutAPIView(APIView):
    """End the current Django session so a local tester can switch accounts."""

    def post(self, request):
        logout(request)
        return Response(status=status.HTTP_204_NO_CONTENT)

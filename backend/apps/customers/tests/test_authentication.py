from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.customers.models import Customer


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class CustomerSessionAuthenticationTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.owner = user_model.objects.create_user("customer-owner", password="local-test-password")
        self.other = user_model.objects.create_user("customer-other", password="other-test-password")
        self.staff = user_model.objects.create_user("support", password="staff-test-password", is_staff=True)
        self.customer = Customer.objects.create(
            user=self.owner, full_name="Customer Owner", email="owner@example.test"
        )
        self.other_customer = Customer.objects.create(
            user=self.other, full_name="Other Customer", email="other@example.test"
        )
        self.client = APIClient(enforce_csrf_checks=True)

    def test_customer_login_scopes_lookup_to_the_authenticated_customer(self):
        csrf_response = self.client.get(reverse("customer-auth-csrf"))
        csrf_token = csrf_response.cookies["csrftoken"].value
        login_response = self.client.post(
            reverse("customer-login"),
            {"email": self.customer.email, "password": "local-test-password"},
            format="json",
            HTTP_X_CSRFTOKEN=csrf_token,
        )

        own_response = self.client.get(reverse("customer-lookup"), {"email": self.customer.email})
        session_response = self.client.get(reverse("customer-session"))
        other_response = self.client.get(
            reverse("customer-lookup"), {"email": self.other_customer.email}
        )
        self.assertEqual(login_response.status_code, status.HTTP_200_OK)
        self.assertIn("sessionid", login_response.cookies)
        self.assertEqual(own_response.status_code, status.HTTP_200_OK)
        self.assertEqual(session_response.status_code, status.HTTP_200_OK)
        self.assertEqual(session_response.data, {"email": self.customer.email, "full_name": self.customer.full_name})
        self.assertEqual(other_response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(set(own_response.data), {"orders"})
        self.assertEqual(other_response.data["detail"], "Order not found or unavailable.")

    def test_login_rejects_invalid_credentials_and_requires_csrf(self):
        csrf_response = self.client.get(reverse("customer-auth-csrf"))
        csrf_token = csrf_response.cookies["csrftoken"].value
        invalid_response = self.client.post(
            reverse("customer-login"),
            {"email": self.customer.email, "password": "wrong-password"},
            format="json",
            HTTP_X_CSRFTOKEN=csrf_token,
        )
        csrf_failure = self.client.post(
            reverse("customer-login"),
            {"email": self.customer.email, "password": "local-test-password"},
            format="json",
        )

        self.assertEqual(invalid_response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(csrf_failure.status_code, status.HTTP_403_FORBIDDEN)

    def test_customer_session_requires_authentication(self):
        response = self.client.get(reverse("customer-session"))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_staff_login_and_refreshable_session_allow_support_access(self):
        csrf_response = self.client.get(reverse("customer-auth-csrf"))
        csrf_token = csrf_response.cookies["csrftoken"].value
        login_response = self.client.post(
            reverse("staff-login"),
            {"username": self.staff.username, "password": "staff-test-password"},
            format="json",
            HTTP_X_CSRFTOKEN=csrf_token,
        )
        session_response = self.client.get(reverse("staff-session"))
        queue_response = self.client.get(reverse("support-refund-list"))

        self.assertEqual(login_response.status_code, status.HTTP_200_OK)
        self.assertIn("sessionid", login_response.cookies)
        self.assertEqual(session_response.data, {"username": self.staff.username})
        self.assertEqual(queue_response.status_code, status.HTTP_200_OK)

    def test_non_staff_cannot_create_or_use_a_support_session(self):
        csrf_response = self.client.get(reverse("customer-auth-csrf"))
        csrf_token = csrf_response.cookies["csrftoken"].value
        login_response = self.client.post(
            reverse("staff-login"),
            {"username": self.owner.username, "password": "local-test-password"},
            format="json",
            HTTP_X_CSRFTOKEN=csrf_token,
        )
        session_response = self.client.get(reverse("staff-session"))

        self.assertEqual(login_response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(session_response.status_code, status.HTTP_403_FORBIDDEN)
